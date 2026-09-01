"""
SQLAlchemy async session factory and database initialization.

Provides:
    - Async engine connected to PostgreSQL via asyncpg.
    - AsyncSession factory (async_session_factory) for dependency injection.
    - init_db(): auto-creates all tables on application startup.
    - get_db(): FastAPI dependency yielding an AsyncSession per request.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Base

# ---------------------------------------------------------------------------
# Engine: created once at module import using the DATABASE_URL from settings.
# ---------------------------------------------------------------------------
_settings = get_settings()
engine = create_async_engine(
    _settings.database_url,
    echo=False,          # Set to True for SQL query logging during development
    pool_pre_ping=True,  # Checks connection liveness before using it from pool
    pool_size=5,
    max_overflow=10,
)

# ---------------------------------------------------------------------------
# Session factory: used to create AsyncSession instances per request.
# ---------------------------------------------------------------------------
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """
    Creates all database tables defined in Base.metadata.

    Called once during application lifespan startup. Safe to call on an
    already-initialized database (uses CREATE TABLE IF NOT EXISTS semantics).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an AsyncSession per request.

    Yields an async database session and guarantees it is closed after
    the request completes, even if an exception is raised.

    Usage:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        yield session
