import uuid
import logging
from celery_app import celery
from database.session import SessionLocal
from model.item_csv_model import ItemData
from sqlalchemy import func
from tasks.duplicate_helpers import get_duplicate_group_keys, get_group_members

logger = logging.getLogger(__name__)
BATCH_SIZE = 100

@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def compute_duplicates(self):
    db = SessionLocal()
    try:
        # Reset flags
        db.query(ItemData).update(
            {ItemData.is_duplicate: False, ItemData.duplicate_group_id: None},
            synchronize_session=False,
        )
        db.commit()
        logger.info("Reset all duplicate flags")

        # Stream rows ordered by duplicate key columns
        rows = (
            db.query(
                ItemData.id,
                ItemData.name,
                ItemData.category,
                ItemData.sub_category,
                ItemData.email,
                ItemData.city,
                ItemData.area,
                ItemData.address,
            )
            .filter(ItemData.name.isnot(None), func.trim(ItemData.name) != '', ItemData.address.isnot(None), func.trim(ItemData.address) != '')
            .order_by(
                ItemData.name,
                ItemData.category,
                ItemData.sub_category,
                ItemData.email,
                ItemData.city,
                ItemData.area,
                ItemData.address,
            )
            .yield_per(1000)
        )

        processed = 0
        current_key = None
        group_members = []

        for row in rows:
            key = (row.name, row.category, row.sub_category, row.email, row.city, row.area, row.address)
            if key != current_key:
                # Finish previous group
                if current_key and len(group_members) > 1:
                    group_id = str(uuid.uuid4())
                    dup_ids = [member.id for member in group_members[1:]]
                    db.query(ItemData).filter(ItemData.id.in_(dup_ids)).update(
                        {ItemData.is_duplicate: True, ItemData.duplicate_group_id: group_id},
                        synchronize_session=False,
                    )
                    processed += 1
                    if processed % BATCH_SIZE == 0:
                        db.commit()
                        logger.info("Committed %d groups", processed)
                # Start new group
                current_key = key
                group_members = [row]
            else:
                group_members.append(row)

        # Process final group
        if current_key and len(group_members) > 1:
            group_id = str(uuid.uuid4())
            dup_ids = [member.id for member in group_members[1:]]
            db.query(ItemData).filter(ItemData.id.in_(dup_ids)).update(
                {ItemData.is_duplicate: True, ItemData.duplicate_group_id: group_id},
                synchronize_session=False,
            )
            processed += 1

        # Final commit for any remaining updates
        db.commit()
        logger.info("Done: %d groups processed", processed)
        return f"Processed {processed} groups"
    except Exception as exc:
        db.rollback()
        logger.exception("compute_duplicates failed")
        raise self.retry(exc=exc)
    finally:
        db.close()
