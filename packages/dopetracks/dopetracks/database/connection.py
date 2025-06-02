"""
Database connection and session management for Dopetracks.
Supports SQLite for development and PostgreSQL for production.
"""
import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from ..config import settings
from .models import Base

logger = logging.getLogger(__name__)

# Database engine (global)
engine = None
SessionLocal = None

def create_database_engine() -> Engine:
    """Create database engine with appropriate configuration."""
    global engine
    
    if engine is not None:
        return engine
    
    database_url = settings.DATABASE_URL
    connect_args = {}
    
    # SQLite-specific configuration
    if database_url.startswith("sqlite"):
        # Enable foreign key constraints for SQLite
        connect_args = {
            "check_same_thread": False,
            "poolclass": StaticPool,
        }
        
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Enable foreign key constraints and optimize SQLite."""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=1000")
            cursor.execute("PRAGMA temp_store=memory")
            cursor.close()
    
    # PostgreSQL-specific configuration
    elif database_url.startswith("postgresql"):
        connect_args = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
    
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        echo=settings.DEBUG,  # Log SQL queries in debug mode
    )
    
    logger.info(f"Database engine created for: {database_url.split('@')[0] if '@' in database_url else database_url}")
    return engine

def create_session_factory() -> sessionmaker:
    """Create session factory."""
    global SessionLocal
    
    if SessionLocal is not None:
        return SessionLocal
    
    engine = create_database_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return SessionLocal

def create_tables():
    """Create all database tables."""
    engine = create_database_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.
    Use with FastAPI Depends().
    """
    SessionLocal = create_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Use for non-FastAPI code.
    """
    SessionLocal = create_session_factory()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_database():
    """Initialize database for the application."""
    try:
        create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def check_database_health() -> bool:
    """Check if database is accessible."""
    try:
        with get_db_session() as db:
            # Simple query to test connection
            db.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

# Initialize database on module import (for development)
if not settings.is_production():
    try:
        init_database()
    except Exception as e:
        logger.warning(f"Could not auto-initialize database: {e}")
        logger.warning("You may need to run database migrations manually") 