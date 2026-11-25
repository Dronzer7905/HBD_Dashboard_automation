import os
from dotenv import load_dotenv
from datetime import timedelta
import urllib.parse  # Added for password encoding

_env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(_env_path, override=False)
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")  

    # --- Database configuration (FIXED for special characters and drivers) ---
    _explicit_db_uri = os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI')
    DB_USER = os.getenv('DB_USER')
    # Use unquote first then quote_plus to safely handle raw '@' and pre-encoded '%40'
    DB_PASSWORD = urllib.parse.quote_plus(urllib.parse.unquote(os.getenv('DB_PASSWORD', '')))
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME')

    if _explicit_db_uri:
        if _explicit_db_uri.startswith('postgresql://'):
            _explicit_db_uri = _explicit_db_uri.replace('postgresql://', 'postgresql+psycopg2://', 1)
        SQLALCHEMY_DATABASE_URI = _explicit_db_uri
    elif str(DB_PORT) in ('5432', '5433', '15432') or 'postgres' in os.getenv('DB_DRIVER', '').lower() or os.getenv('DB_TYPE') == 'postgresql':
        _ssl_suffix = '?sslmode=disable' if 'sslmode=disable' in os.getenv('DB_PARAMS', '') or os.getenv('DB_SSLMODE') == 'disable' else ''
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}{_ssl_suffix}"
        )
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )

    # Determine connection engine options based on dialect
    if 'postgres' in SQLALCHEMY_DATABASE_URI.lower():
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 20,
            "max_overflow": 10,
            "pool_recycle": 280,
            "pool_pre_ping": True,
            "connect_args": {
                "connect_timeout": 60
            }
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 20,
            "max_overflow": 10,
            "pool_recycle": 280,
            "pool_pre_ping": True,
            "connect_args": {
                "connect_timeout": 60,
                "read_timeout": 300,
                "write_timeout": 300,
                "ssl": {"ssl_disabled": True}
            }
        }

    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- JWT CONFIGURATION ---
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    if not JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY must be set in .env file")
    
    # 1. Store token in headers and cookies
    JWT_TOKEN_LOCATION = ['headers', 'cookies']

    # 2. Set to False for local development (allow cookies over HTTP)
    JWT_COOKIE_SECURE = False
    # 2. Set to True because your live site uses HTTPS (auto-detects and disables on local runs)
    JWT_COOKIE_SECURE = os.getenv("JWT_COOKIE_SECURE", "False" if os.getenv("DB_HOST") in ("localhost", "127.0.0.1") else "True").lower() == "true" 

    # 3. Disable CSRF for now
    JWT_COOKIE_CSRF_PROTECT = False

    # 4. Session Timeout: 30 DAYS
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30) 
    # Explicit existing user IDs allowed to approve BG-1.11 mappings; deny by default.
    MAPPING_APPROVER_IDS = os.getenv('MAPPING_APPROVER_IDS', '')
    MAPPING_ADMIN_IDS = os.getenv('MAPPING_ADMIN_IDS', '')
    MAPPING_POSTGRES_ASSOCIATIONS_ENABLED = os.getenv('MAPPING_POSTGRES_ASSOCIATIONS_ENABLED', 'false').lower() == 'true'
    MAPPING_DEPLOYMENT_ENV = os.getenv('MAPPING_DEPLOYMENT_ENV', '')
    MAPPING_POSTGRES_DATABASE = os.getenv('MAPPING_POSTGRES_DATABASE', '')
    # Provisional junction storage is opt-in and additionally restricted to SQLite.
    MAPPING_LOCAL_ASSOCIATIONS_ENABLED = os.getenv('MAPPING_LOCAL_ASSOCIATIONS_ENABLED', 'false').lower() == 'true'

    # Mail configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

    # Add ETL/Google Drive/Batch config for Celery tasks
    SERVICE_ACCOUNT_FILE = os.getenv(
        "SERVICE_ACCOUNT_FILE",
        os.path.join(os.getcwd(), "model", "honey-bee-digital-d96daf6e6faf.json")
    )
    # Define a single source for the database URI to avoid confusion and errors
    DATABASE_URI = SQLALCHEMY_DATABASE_URI
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
    ETL_VERSION = os.getenv("ETL_VERSION", "2.0.0")
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "2000"))

# Instantiate config for import convenience
config = Config()
