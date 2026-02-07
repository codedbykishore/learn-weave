"""
Migration script to update file_data and image_data columns from BLOB to LONGBLOB
This allows storing files up to 4GB instead of 64KB

Run this script once to update your database schema:
python migrate_file_columns.py
"""

from sqlalchemy import create_engine, text
from src.config import settings
import sys

def migrate_columns():
    """Migrate BLOB columns to LONGBLOB for handling larger files"""
    
    # Create engine
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            print("Starting migration...")
            
            # Check if documents table exists
            result = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'documents'"
            ))
            if result.scalar() > 0:
                print("Altering 'documents' table: file_data column to LONGBLOB...")
                conn.execute(text(
                    "ALTER TABLE documents MODIFY COLUMN file_data LONGBLOB"
                ))
                conn.commit()
                print("✓ Successfully altered documents.file_data to LONGBLOB")
            else:
                print("⚠ documents table does not exist, skipping...")
            
            # Check if images table exists
            result = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'images'"
            ))
            if result.scalar() > 0:
                print("Altering 'images' table: image_data column to LONGBLOB...")
                conn.execute(text(
                    "ALTER TABLE images MODIFY COLUMN image_data LONGBLOB"
                ))
                conn.commit()
                print("✓ Successfully altered images.image_data to LONGBLOB")
            else:
                print("⚠ images table does not exist, skipping...")
            
            print("\n✅ Migration completed successfully!")
            print("Your database can now handle files up to 4GB in size.")
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration: BLOB -> LONGBLOB")
    print("=" * 60)
    migrate_columns()
