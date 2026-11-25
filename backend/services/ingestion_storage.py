"""Shared staged-file storage. No Flask, config, database, or Celery imports."""
import csv
import hashlib
import itertools
import json
import math
import re
import tempfile
import uuid
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from werkzeug.utils import secure_filename


class IngestionError(ValueError):
    def __init__(self, message, status=400, code='invalid_request'):
        super().__init__(message)
        self.status, self.code = status, code


FIELDS = {'business_name', 'phone', 'email', 'address', 'city', 'state', 'country',
          'pincode', 'category', 'latitude', 'longitude'}
CATEGORY_TYPES = {'dining', 'retail', 'services', 'healthcare', 'tourism',
                  'itineraries', 'hotels', 'play-areas'}


def storage_root(settings):
    base = settings.get('INGESTION_UPLOAD_DIR')
    return Path(base or Path(tempfile.gettempdir()) / 'hbd-ingestion' / 'staging').resolve()


def checked_id(value, name='file_id'):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise IngestionError(f'{name} must be a server-issued identifier')
    return value


def staged_path(settings, file_id, suffix):
    root = storage_root(settings)
    path = root / (checked_id(file_id) + suffix)
    if path.is_symlink() or path.resolve().parent != root:
        raise IngestionError('Staged file is unavailable', 404, 'file_not_found')
    return path


def cell_text(value):
    if value is None:
        return ''
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def file_rows(path):
    """Yield rows lazily; never load a whole workbook or CSV into memory."""
    if path.suffix == '.xlsx':
        from openpyxl import load_workbook
        try:
            with zipfile.ZipFile(path) as archive:
                if sum(entry.file_size for entry in archive.infolist()) > 512 * 1024 * 1024:
                    raise IngestionError('Expanded workbook exceeds 512 MiB', 413)
            workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
            try:
                sheet = workbook.worksheets[0]
                # Spreadsheet dimension metadata may be stale or malicious.
                sheet.reset_dimensions()
                for row in sheet.iter_rows(values_only=True):
                    yield [cell_text(value) for value in row]
            finally:
                workbook.close()
        except IngestionError:
            raise
        except Exception:
            raise IngestionError('Unable to read the XLSX workbook') from None
    else:
        try:
            with path.open('r', encoding='utf-8-sig', newline='') as source:
                yield from csv.reader(source, delimiter='\t' if path.suffix == '.tsv' else ',', strict=True)
        except (UnicodeError, csv.Error):
            raise IngestionError('Malformed file; CSV/TSV must use UTF-8 encoding') from None


def data_rows(path):
    rows = file_rows(path)
    try:
        next(rows, None)
        yield from (row for row in rows if any(value.strip() for value in row))
    finally:
        rows.close()


def save_upload(upload, owner_id, settings):
    filename = secure_filename(upload.filename or '')
    suffix = Path(filename).suffix.lower()
    if suffix not in {'.csv', '.tsv', '.xlsx'}:
        raise IngestionError('Supported file types are CSV, TSV and XLSX; convert XLS to XLSX', 415)
    root = storage_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    path = staged_path(settings, file_id, suffix)
    manifest_path = staged_path(settings, file_id, '.json')
    digest, size = hashlib.sha256(), 0
    maximum = int(settings.get('INGESTION_MAX_UPLOAD_BYTES', 100 * 1024 * 1024))
    try:
        with path.open('xb') as target:
            while True:
                chunk = upload.stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > maximum:
                    raise IngestionError('Upload exceeds the configured size limit', 413, 'upload_too_large')
                digest.update(chunk)
                target.write(chunk)
        rows = file_rows(path)
        try:
            headers = next(rows, [])
            if (not headers or len(headers) > 200 or any(not h.strip() or len(h) > 255 for h in headers)
                    or len(set(headers)) != len(headers)):
                raise IngestionError('File requires 1..200 unique, non-empty headers of at most 255 characters')
            sample = list(itertools.islice((row for row in rows if any(v.strip() for v in row)), 5))
        finally:
            rows.close()
        manifest = dict(file_id=file_id, owner_id=owner_id, filename=filename, extension=suffix,
                        size_bytes=size, sha256=digest.hexdigest(), headers=headers,
                        created_at=datetime.now(timezone.utc).isoformat())
        with manifest_path.open('x', encoding='utf-8') as target:
            json.dump(manifest, target)
        return dict(file_id=file_id, filename=filename, headers=headers, sample_rows=sample,
                    size_bytes=size, supported_target_fields=sorted(FIELDS))
    except Exception:
        path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise


def load_upload(file_id, owner_id, settings, verify=False):
    manifest_path = staged_path(settings, file_id, '.json')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise IngestionError('Staged upload not found', 404, 'file_not_found') from None
    if manifest.get('owner_id') != owner_id:
        raise IngestionError('Staged upload not found', 404, 'file_not_found')
    if manifest.get('extension') not in {'.csv', '.tsv', '.xlsx'}:
        raise IngestionError('Staged upload metadata is invalid', 409, 'file_changed')
    path = staged_path(settings, file_id, manifest['extension'])
    if not path.is_file():
        raise IngestionError('Staged upload not found', 404, 'file_not_found')
    if verify:
        with path.open('rb') as source:
            checksum = hashlib.file_digest(source, 'sha256').hexdigest()
        if checksum != manifest['sha256']:
            raise IngestionError('Staged file has changed; upload it again', 409, 'file_changed')
    return manifest, path


def validate_mapping(mapping, headers):
    if not isinstance(mapping, dict) or not mapping or len(mapping) > len(headers):
        raise IngestionError('column_mapping must map uploaded headers to target fields')
    targets = []
    cleaned = {}
    for source, target in mapping.items():
        if source not in headers or not isinstance(target, str) or target not in FIELDS | {''}:
            raise IngestionError('Unknown header or target field in column_mapping')
        if target:
            targets.append(target)
            cleaned[source] = target
    if len(targets) != len(set(targets)):
        raise IngestionError('Multiple headers cannot map to the same target field')
    if 'business_name' not in targets:
        raise IngestionError('A business_name column mapping is required')
    return cleaned


def normalize_row(row, headers, mapping):
    if len(row) != len(headers):
        return None, 'Column count does not match headers'
    values = {mapping[h]: value.strip() for h, value in zip(headers, row) if h in mapping}
    if not values.get('business_name'):
        return None, 'Missing business_name'
    if any('\x00' in value or len(value) > 10000 for value in values.values()):
        return None, 'Field contains a NUL character or exceeds 10000 characters'
    limits = {'business_name': 255, 'phone': 100, 'email': 255, 'city': 255,
              'state': 255, 'country': 100, 'pincode': 20, 'category': 255}
    for field, limit in limits.items():
        if len(values.get(field, '')) > limit:
            return None, f'{field} exceeds {limit} characters'
    for field, lower, upper in [('latitude', -90, 90), ('longitude', -180, 180)]:
        value = values.get(field, '')
        if value == '':
            values[field] = None
            continue
        try:
            number = float(value)
        except (ValueError, TypeError):
            return None, f'Invalid {field}'
        if not math.isfinite(number) or not lower <= number <= upper:
            return None, f'Invalid {field}; expected {lower}..{upper}'
        values[field] = number
    if (values.get('latitude') is None) != (values.get('longitude') is None):
        return None, 'Latitude and longitude must be supplied together'
    return values, None
