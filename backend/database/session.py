from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
import os
import sys

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import config

# Base class for all models
Base = declarative_base()

# Database URL and options from central config
DATABASE_URL = config.SQLALCHEMY_DATABASE_URI
engine_options = getattr(config, "SQLALCHEMY_ENGINE_OPTIONS", {
    "pool_size": 10,
    "max_overflow": 5,
    "pool_recycle": 1800,
    "pool_pre_ping": True,
})

print(f"[Session] Initializing engine with: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

# Engine creation
engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    **engine_options
)

# Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Scoped session (thread-safe)
db_session = scoped_session(SessionLocal)

# Utility function to get a session
def get_db_session():
    """
    Returns a new database session.
    In Flask routes you must close() manually after use.
    """
    return SessionLocal()
