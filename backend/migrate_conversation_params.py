"""
Migration script to add conversation parameters
Run this script to add temperature, top_p, max_tokens, quantize, and custom_prompt columns to the conversations table
"""

import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine, get_db
from sqlalchemy.orm import Session

def migrate_conversation_parameters():
    """Add parameter columns to conversations table"""
    
    # SQL commands to add new columns
    migration_commands = [
        "ALTER TABLE conversations ADD COLUMN temperature REAL DEFAULT 0.2;",
        "ALTER TABLE conversations ADD COLUMN top_p REAL DEFAULT 0.5;", 
        "ALTER TABLE conversations ADD COLUMN max_tokens INTEGER DEFAULT 1024;",
        "ALTER TABLE conversations ADD COLUMN quantize BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE conversations ADD COLUMN custom_prompt TEXT DEFAULT '';",
    ]
    
    db = Session(bind=engine)
    
    try:
        for command in migration_commands:
            try:
                db.execute(text(command))
                print(f"✓ Executed: {command}")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"⚠ Column already exists: {command}")
                else:
                    print(f"✗ Error executing {command}: {e}")
                    raise
        
        db.commit()
        print("\n✓ Migration completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting conversation parameters migration...")
    migrate_conversation_parameters()
