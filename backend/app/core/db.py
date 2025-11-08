"""Database connection and session management."""
import logging
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import OperationalError
from app.core.config import settings

logger = logging.getLogger(__name__)

# Determine database type and configure connection
is_postgresql = settings.is_postgresql
is_sqlite = settings.is_sqlite

# Configure connection arguments based on database type
connect_args = {}
if is_sqlite:
    connect_args = {"check_same_thread": False}
elif is_postgresql:
    # For PostgreSQL, we can add connection pool settings
    # Supabase has connection limits, so we use a small pool
    connect_args = {}

# Create database engine with retry logic
def create_db_engine_with_retry(max_retries: int = 3, retry_delay: float = 2.0):
    """
    Create database engine with connection retry logic.
    
    Args:
        max_retries: Maximum number of connection retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        SQLAlchemy engine
    """
    db_url = settings.database_url
    
    # Configure engine based on database type
    if is_postgresql:
        # For PostgreSQL/Supabase, ensure we use a compatible driver
        # If URL doesn't specify a driver, try to use psycopg3 or asyncpg
        if "+" not in db_url:
            # No driver specified, try to use psycopg3 (synchronous) or asyncpg
            try:
                import psycopg
                db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
                logger.debug("Using psycopg3 driver for PostgreSQL")
            except ImportError:
                try:
                    import asyncpg
                    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
                    logger.debug("Using asyncpg driver for PostgreSQL")
                except ImportError:
                    logger.warning("No PostgreSQL driver found. Install psycopg or asyncpg.")
                    raise ImportError("Please install psycopg or asyncpg: pip install psycopg[binary] or pip install asyncpg")
        
        # For PostgreSQL/Supabase, use connection pooling
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_size=5,  # Small pool for Supabase free tier
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set to True for SQL query logging
        )
    else:
        # For SQLite, simpler configuration
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            echo=False  # Set to True for SQL query logging
        )
    
    # Test connection with retries
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                # Test query based on database type
                if is_postgresql:
                    conn.execute(text("SELECT 1"))
                else:
                    conn.execute(text("SELECT 1"))
            logger.info(f"✅ Database connection successful (attempt {attempt})")
            return engine
        except OperationalError as e:
            if attempt < max_retries:
                logger.warning(
                    f"⚠️  Database connection failed (attempt {attempt}/{max_retries}): {e}"
                )
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ Database connection failed after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during database connection: {e}")
            raise
    
    return engine

# Create engine
engine = create_db_engine_with_retry()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables initialized successfully")
        
        # Log database type
        if is_postgresql:
            logger.info("📊 Using PostgreSQL (Supabase)")
        else:
            logger.info("📊 Using SQLite (local)")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database tables: {e}")
        raise

