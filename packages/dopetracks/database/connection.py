"""
Database connection for Dopetracks application.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base
from ..config import settings

# Use DATABASE_URL from settings, with fallback to local path
DATABASE_URL = settings.DATABASE_URL

# For SQLite, ensure directory exists if using file path
if DATABASE_URL.startswith("sqlite:///"):
    # Extract file path from SQLite URL
    db_path_str = DATABASE_URL.replace("sqlite:///", "")
    if not db_path_str.startswith(":memory:"):
        db_path = Path(db_path_str)
        db_path.parent.mkdir(parents=True, exist_ok=True)

# Create engine with connection pooling for SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if DATABASE_URL.startswith("sqlite") else None,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

def check_database_health() -> bool:
    """Check if database is accessible."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Database health check error: {e}")
        return False
