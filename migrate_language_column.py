"""
Migration script to add language column to episodes table.
Run this script to update your database schema.
"""
import asyncio
import os
from sqlalchemy import text
from app.core.database import engine
from app.core.config import settings


async def migrate():
    """Add language column to episodes table."""
    print("🔄 Starting migration: Adding language column to episodes table...")
    
    async with engine.begin() as conn:
        try:
            # Check if column already exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'episodes' AND column_name = 'language'
            """)
            result = await conn.execute(check_query)
            exists = result.fetchone() is not None
            
            if exists:
                print("✅ Language column already exists. Skipping migration.")
                return
            
            # Add language column
            print("📝 Adding language column...")
            await conn.execute(text("""
                ALTER TABLE episodes 
                ADD COLUMN language VARCHAR(10) DEFAULT 'en' NOT NULL
            """))
            
            # Update existing rows
            print("📝 Updating existing rows with default language...")
            await conn.execute(text("""
                UPDATE episodes 
                SET language = 'en' 
                WHERE language IS NULL
            """))
            
            print("✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise


if __name__ == "__main__":
    print(f"🔗 Connecting to database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'local'}")
    asyncio.run(migrate())

