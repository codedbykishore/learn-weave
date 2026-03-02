import os
from contextlib import contextmanager
from sqlalchemy.ext.declarative import declarative_base

# Always define Base so SQLAlchemy model imports don't crash
Base = declarative_base()

# Check if we should use Firestore or MySQL
USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").lower() == "true"

if USE_FIRESTORE:
    # Use Firestore adapter
    from .firestore_adapter import FirestoreAdapter
    
    # Create a global Firestore adapter instance
    firestore_adapter = FirestoreAdapter()
    
    def get_db():
        """
        Generator that yields the Firestore adapter.
        Compatible with FastAPI dependency injection.
        """
        yield firestore_adapter
    
    @contextmanager
    def get_db_context():
        """Context manager that yields the Firestore adapter."""
        yield firestore_adapter
    
    # Placeholders - not used in Firestore mode
    engine = None
    SessionLocal = None
    
else:
    # Use MySQL with SQLAlchemy
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from ..config import settings
    
    engine = create_engine(
        settings.SQLALCHEMY_DATABASE_URL,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        connect_args={"connect_timeout": settings.DB_CONNECT_TIMEOUT}
    )
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @contextmanager
    def get_db_context():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()