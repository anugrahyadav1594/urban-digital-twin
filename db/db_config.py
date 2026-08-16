import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text # Make sure this is at the top of your file

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Database Connection Environment Variables with defaults
DB_HOST = os.getenv("POSTGIS_HOST", "localhost")
DB_PORT = os.getenv("POSTGIS_PORT", "5432")
DB_NAME = os.getenv("POSTGIS_DB", "nagar_x_db")
DB_USER = os.getenv("POSTGIS_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGIS_PASSWORD", "2415")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine

def get_session():
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def test_db_connection():
    try:
        engine = get_engine()
        # 1. We name the connection variable 'conn'
        with engine.connect() as conn:
            # 2. We must use 'conn' to execute the text, and it must be indented properly
            result = conn.execute(text("SELECT PostGIS_Full_Version();"))
            version = result.fetchone()
            print(f"[SUCCESS] Connected to PostGIS successfully: {version[0]}")
            return True
    except Exception as e:
        print(f"[WARNING] Could not connect to PostgreSQL/PostGIS at {DATABASE_URL}: {e}")
        print("Tip: Make sure PostgreSQL server is running and PostGIS extension is enabled.")
        return False