"""
Database connection for Dopetracks application.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base

# Use a simple local SQLite database
DB_PATH = Path.home() / ".dopetracks" / "local.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine with connection pooling for SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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
