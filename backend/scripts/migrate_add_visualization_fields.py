"""Migration script to add visualization fields to event_logs table.

This script adds the following columns to the event_logs table:
- parent_id (String, nullable, indexed)
- file_path (String, nullable, indexed)
- code_diff (Text, nullable)
- execution_result (Text, nullable)
- visual_type (Enum, nullable, indexed)

Run this script once to update existing databases.
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from app.core.db import engine, Base
from app.core.config import settings
from app.models.event_log import VisualType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_visualtype_enum():
    """Create VisualType enum in PostgreSQL if it doesn't exist."""
    if not settings.is_postgresql:
        logger.info("Skipping enum creation for SQLite (enums not supported)")
        return
    
    with engine.connect() as conn:
        # Check if enum already exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'visualtype'
            )
        """))
        enum_exists = result.scalar()
        
        if not enum_exists:
            logger.info("Creating VisualType enum...")
            # Create enum type
            conn.execute(text("""
                CREATE TYPE visualtype AS ENUM ('MESSAGE', 'CODE', 'DIFF', 'EXECUTION', 'DEBUG')
            """))
            conn.commit()
            logger.info("✅ VisualType enum created")
        else:
            logger.info("VisualType enum already exists")


def add_columns():
    """Add new columns to event_logs table."""
    inspector = inspect(engine)
    
    # Check existing columns
    if 'event_logs' not in inspector.get_table_names():
        logger.error("❌ event_logs table does not exist. Run init_db() first.")
        return False
    
    columns = [col['name'] for col in inspector.get_columns('event_logs')]
    logger.info(f"Existing columns: {', '.join(sorted(columns))}")
    
    # Columns to add
    columns_to_add = {
        'parent_id': {
            'type': 'VARCHAR' if settings.is_postgresql else 'VARCHAR(255)',
            'nullable': True,
            'index': True
        },
        'file_path': {
            'type': 'VARCHAR' if settings.is_postgresql else 'VARCHAR(255)',
            'nullable': True,
            'index': True
        },
        'code_diff': {
            'type': 'TEXT',
            'nullable': True,
            'index': False
        },
        'execution_result': {
            'type': 'TEXT',
            'nullable': True,
            'index': False
        },
        'visual_type': {
            'type': 'visualtype' if settings.is_postgresql else 'VARCHAR(20)',
            'nullable': True,
            'index': True
        }
    }
    
    # Filter out columns that already exist
    missing_columns = {name: config for name, config in columns_to_add.items() 
                      if name not in columns}
    
    if not missing_columns:
        logger.info("✅ All visualization columns already exist!")
        return True
    
    logger.info(f"Adding {len(missing_columns)} new columns...")
    
    with engine.begin() as conn:
        # Create enum first (for PostgreSQL)
        if settings.is_postgresql:
            create_visualtype_enum()
        
        # Add columns
        for col_name, col_config in missing_columns.items():
            try:
                if settings.is_postgresql:
                    # PostgreSQL syntax
                    if col_name == 'visual_type':
                        alter_sql = f"ALTER TABLE event_logs ADD COLUMN {col_name} {col_config['type']}"
                    else:
                        alter_sql = f"ALTER TABLE event_logs ADD COLUMN {col_name} {col_config['type']}"
                    
                    if col_config['nullable']:
                        alter_sql += " NULL"
                    else:
                        alter_sql += " NOT NULL"
                    
                    logger.info(f"Adding column {col_name}...")
                    conn.execute(text(alter_sql))
                    
                    # Create index if needed
                    if col_config['index']:
                        index_name = f"ix_event_logs_{col_name}"
                        logger.info(f"Creating index {index_name}...")
                        try:
                            conn.execute(text(f"CREATE INDEX {index_name} ON event_logs ({col_name})"))
                        except Exception as e:
                            if "already exists" in str(e).lower():
                                logger.info(f"Index {index_name} already exists")
                            else:
                                raise
                else:
                    # SQLite syntax
                    # SQLite doesn't support adding columns with ALTER TABLE easily
                    # We'll use a workaround: create new table, copy data, drop old, rename
                    logger.warning("SQLite detected. For SQLite, it's recommended to:")
                    logger.warning("1. Backup your data")
                    logger.warning("2. Delete the database file")
                    logger.warning("3. Run init_db() to recreate with new schema")
                    logger.warning("Or use a migration tool like Alembic")
                    return False
                
                logger.info(f"✅ Added column {col_name}")
                
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info(f"Column {col_name} already exists, skipping...")
                else:
                    logger.error(f"❌ Failed to add column {col_name}: {e}")
                    raise
    
    logger.info("✅ All columns added successfully!")
    return True


def verify_migration():
    """Verify that all columns were added successfully."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('event_logs')]
    
    required_columns = ['parent_id', 'file_path', 'code_diff', 'execution_result', 'visual_type']
    missing = [col for col in required_columns if col not in columns]
    
    if missing:
        logger.error(f"❌ Missing columns after migration: {missing}")
        return False
    
    logger.info("✅ Migration verification passed!")
    logger.info(f"All columns present: {', '.join(sorted(columns))}")
    return True


def main():
    """Run migration."""
    logger.info("=" * 60)
    logger.info("Migration: Add visualization fields to event_logs")
    logger.info("=" * 60)
    logger.info(f"Database: {'PostgreSQL' if settings.is_postgresql else 'SQLite'}")
    
    try:
        # Add columns
        if add_columns():
            # Verify
            if verify_migration():
                logger.info("=" * 60)
                logger.info("✅ Migration completed successfully!")
                logger.info("=" * 60)
                return 0
            else:
                logger.error("❌ Migration verification failed")
                return 1
        else:
            logger.error("❌ Migration failed")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Migration error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

