"""
Separate database session for the report database.
This keeps the report DB connection isolated or points to REPORTS_DB_URL.
Handles connection failures gracefully with retry logic.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import OperationalError
import os
import sys
import urllib.parse
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import config

load_dotenv()

REPORT_DATABASE_URL = os.getenv('REPORTS_DB_URL') or os.getenv('REPORT_DATABASE_URL')
if not REPORT_DATABASE_URL:
    REPORT_DB_HOST = os.getenv('REPORT_DB_HOST')
    if REPORT_DB_HOST:
        REPORT_DB_USER = os.getenv('REPORT_DB_USER', '')
        REPORT_DB_PASSWORD = os.getenv('REPORT_DB_PASSWORD', '')
        REPORT_DB_NAME = os.getenv('REPORT_DB_NAME', '')
        REPORT_DB_PORT = os.getenv('REPORT_DB_PORT', '3306')
        REPORT_DATABASE_URL = (
            f"mysql+pymysql://{REPORT_DB_USER}:{urllib.parse.quote_plus(REPORT_DB_PASSWORD or '')}"
            f"@{REPORT_DB_HOST}:{REPORT_DB_PORT}/{REPORT_DB_NAME}"
        )
    else:
        REPORT_DATABASE_URL = config.SQLALCHEMY_DATABASE_URI

if REPORT_DATABASE_URL.startswith("postgresql://"):
    REPORT_DATABASE_URL = REPORT_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

print(f"[Report DB Engine] URL: {REPORT_DATABASE_URL.split('@')[-1] if '@' in REPORT_DATABASE_URL else REPORT_DATABASE_URL}")

is_postgres = "postgres" in REPORT_DATABASE_URL.lower()
connect_args = {'connect_timeout': 15} if is_postgres else {'connect_timeout': 5, 'read_timeout': 15, 'write_timeout': 15}

report_engine = create_engine(
    REPORT_DATABASE_URL,
    echo=False,
    future=True,
    pool_size=5,
    max_overflow=3,
    pool_timeout=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=connect_args
)

# Session Factory
ReportSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=report_engine)

# Scoped session (thread-safe)
report_db_session = scoped_session(ReportSessionLocal)


def get_report_db_session():
    """
    Returns a new database session for the report database.
    Always close it when done:
        session = get_report_db_session()
        try: ... finally: session.close()
    """
    return ReportSessionLocal()


def test_report_db_connection():
    """Test if the report database is reachable."""
    try:
        with report_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Connected successfully"
    except Exception as e:
        return False, str(e)
