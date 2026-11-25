"""Create, test and stop an owned disposable PostgreSQL cluster. No shared DB DSN.

Requires existing PostgreSQL binaries, psycopg2, and the project's test packages.
Never uses .env, existing servers, the Cloudflare tunnel or company credentials.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / 'scripts'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgres-bin', type=Path, required=True)
    args = parser.parse_args()
    suffix = '.exe' if os.name == 'nt' else ''
    binaries = {name: args.postgres_bin / (name + suffix) for name in ['initdb','pg_ctl']}
    if not all(path.is_file() for path in binaries.values()):
        parser.error('--postgres-bin must contain existing initdb and pg_ctl binaries')
    directory = Path(tempfile.mkdtemp(prefix='bg113-owned-pg-')).resolve()
    temp_parent = Path(tempfile.gettempdir()).resolve()
    if directory.parent != temp_parent or not directory.name.startswith('bg113-owned-pg-'):
        raise RuntimeError('Disposable cluster path did not pass the ownership check')
    data = directory / 'data'
    owner = 'bg113_test_owner'
    database = 'bg113_test_' + uuid.uuid4().hex[:10]
    password = secrets.token_urlsafe(32)
    password_file = directory / 'init-password'
    password_file.write_text(password + '\n', encoding='utf-8')
    password_file.chmod(0o600)
    passfile = directory / 'pgpass'
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    env = {k:v for k,v in os.environ.items() if not k.startswith('PG')}
    started = False
    def run(command, **kwargs):
        return subprocess.run([str(item) for item in command], env=env,
                              creationflags=creationflags, **kwargs)
    try:
        initialized = run([binaries['initdb'],'-D',data,'-U',owner,'--encoding=UTF8','--locale=C',
                           '--auth-host=scram-sha-256','--auth-local=scram-sha-256','--pwfile',password_file],
                          capture_output=True,text=True,timeout=45)
        if initialized.returncode:
            print('Disposable cluster initialization failed:',initialized.stderr[-1600:])
            return 1
        password_file.unlink()
        with socket.socket() as port_probe:
            port_probe.bind(('127.0.0.1',0))
            port = port_probe.getsockname()[1]
        if port in (5432,5433,15432,15434):
            raise RuntimeError('Refusing a reserved/shared PostgreSQL port')
        passfile.write_text(f'127.0.0.1:{port}:*:{owner}:{password}\n',encoding='utf-8')
        passfile.chmod(0o600)
        env.update(PGHOST='127.0.0.1',PGPORT=str(port),PGUSER=owner,PGDATABASE=database,
                   PGPASSFILE=str(passfile),PGSSLMODE='disable')
        options = f'-h 127.0.0.1 -p {port} -c max_connections=20'
        # On Windows, postmaster can inherit pg_ctl pipe handles. Real files
        # and DEVNULL stdin avoid communicate() waiting for the server to exit.
        started = True  # Also run ownership-scoped cleanup after partial startup.
        with (directory/'controller.log').open('wb') as controller_log:
            started_process = run([binaries['pg_ctl'],'-D',data,'-l',directory/'server.log','-o',options,'-w','start'],
                                  stdout=controller_log,stderr=controller_log,stdin=subprocess.DEVNULL,timeout=45)
        if started_process.returncode:
            print('Disposable PostgreSQL startup failed; controller exit',started_process.returncode)
            return 1
        import psycopg2
        import psycopg2.sql
        # Explicit connection parameters come ONLY from the just-created cluster.
        params = dict(host='127.0.0.1',port=port,user=owner,passfile=str(passfile),sslmode='disable',connect_timeout=5)
        admin=psycopg2.connect(dbname='postgres',**params)
        try:
            admin.autocommit = True
            with admin.cursor() as cursor:
                cursor.execute(psycopg2.sql.SQL('CREATE DATABASE {}').format(psycopg2.sql.Identifier(database)))
        finally:
            admin.close()
        profile={'owned_cluster':True,'host':'127.0.0.1','port':port,'user':owner,'database':database,
                 'passfile':str(passfile),'cluster_directory':str(directory),'backend':str(BACKEND)}
        profile_path=directory/'profile.json'
        profile_path.write_text(json.dumps(profile),encoding='utf-8')
        env['INGESTION_TEST_PG_PROFILE']=str(profile_path)
        print(f'Running synthetic PostgreSQL tests in owned local database {database} on loopback port {port}',flush=True)
        result=run([sys.executable,'-m','unittest','discover','-s',BACKEND/'tests','-p','test_ingestion*.py','-v'],
                   cwd=ROOT,capture_output=True,text=True,timeout=180)
        if result.stdout: print(result.stdout,flush=True)
        if result.stderr: print(result.stderr,file=sys.stderr,flush=True)
        return result.returncode
    finally:
        if started:
            status=run([binaries['pg_ctl'],'-D',data,'status'],stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,timeout=10)
            if status.returncode==0:
                stop=run([binaries['pg_ctl'],'-D',data,'-m','fast','-w','stop'],stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,timeout=45)
                if stop.returncode:
                    raise RuntimeError('Owned test PostgreSQL shutdown failed; inspect '+str(directory))
            print('Owned test PostgreSQL server stopped.',flush=True)
        # Remove only this verified, self-created temporary cluster; never a supplied path.
        if directory.parent==temp_parent and directory.name.startswith('bg113-owned-pg-'):
            shutil.rmtree(directory)
            print('Owned test cluster and temporary authentication files removed.',flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
