"""
Database connection and session management.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

from app.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Check and add language column if missing (migration)
        try:
            from sqlalchemy import text
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'episodes' AND column_name = 'language'
            """)
            result = await conn.execute(check_query)
            exists = result.fetchone() is not None
            
            if not exists:
                print("🔄 Adding language column to episodes table...")
                await conn.execute(text("""
                    ALTER TABLE episodes 
                    ADD COLUMN language VARCHAR(10) DEFAULT 'en' NOT NULL
                """))
                await conn.execute(text("""
                    UPDATE episodes 
                    SET language = 'en' 
                    WHERE language IS NULL
                """))
                print("✅ Language column added successfully")
        except Exception as e:
            print(f"⚠️  Warning: Could not add language column automatically: {e}")
            print("   Please run the migration script manually: python migrate_language_column.py")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
