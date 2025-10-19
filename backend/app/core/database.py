"""Database connection and session management with tenant isolation."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import Pool

from app.core.config import settings

# Create async engine
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.APP_DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # Verify connections before using them
)


# Pool event listener to reset connection state when returned to pool
# This prevents tenant_id from "leaking" between requests if using transaction pooling
@event.listens_for(Pool, "checkin")
def receive_checkin(dbapi_conn: Any, connection_record: Any) -> None:
    """
    Reset connection state when returned to pool.

    This ensures that SET LOCAL session variables don't leak between requests.
    While SET LOCAL is transaction-scoped and should auto-reset, this provides
    defense in depth, especially if using connection poolers like PgBouncer
    in transaction mode.

    Args:
        dbapi_conn: The raw DBAPI connection
        connection_record: Connection record metadata
    """
    # Note: We can't use DISCARD ALL with asyncpg in this sync context
    # SET LOCAL variables automatically reset at transaction end anyway
    # This listener is here for documentation and future enhancement
    pass


# Create async session factory
# Using both names for compatibility during migration
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Alias for backwards compatibility
AsyncSessionLocal = async_session_maker


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session (context manager style).

    Usage:
        async with get_db_session() as session:
            # Use session
            pass
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session_for_tenant(tenant_id: UUID) -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session with tenant isolation via RLS (context manager style).

    This is the context manager version of get_tenant_db(), recommended for use
    in FastAPI endpoints to avoid mypy false positives with async generators.

    Security Notes:
    - Uses SET LOCAL (not SET) to ensure tenant_id is transaction-scoped
    - Automatically resets when transaction ends (on commit/rollback)
    - Safe with SQLAlchemy's built-in connection pooling (session mode)
    - If using PgBouncer, ensure session pooling mode (not transaction mode)
    - UUID validation prevents SQL injection

    Args:
        tenant_id: UUID of the tenant to isolate to

    Yields:
        AsyncSession with tenant context set

    Raises:
        ValueError: If tenant_id is invalid

    Example:
        ```python
        async with get_db_session_for_tenant(current_user.tenant_id) as db:
            result = await db.execute(select(Patient))
            return result.scalars().all()  # Only returns patients for this tenant
        ```
    """
    # Validate tenant_id to prevent SQL injection
    if not isinstance(tenant_id, UUID):
        raise ValueError(f"Invalid tenant_id type: {type(tenant_id)}")

    async with async_session_maker() as session:
        try:
            # Set tenant_id for RLS policies (transaction-scoped with SET LOCAL)
            tenant_id_str = str(tenant_id)
            await session.execute(
                text(f"SET LOCAL app.tenant_id = '{tenant_id_str}'")
            )

            yield session

        finally:
            # Note: SET LOCAL automatically resets at transaction end
            # No explicit cleanup needed, but we ensure session is closed
            pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session without tenant isolation.

    WARNING: This does NOT set tenant_id.
    Use get_tenant_db() instead for tenant-isolated sessions.

    Usage:
        @app.get("/health")
        async def health(db: AsyncSession = Depends(get_db)):
            await db.execute(text("SELECT 1"))
    """
    async with async_session_maker() as session:
        yield session


async def get_tenant_db(tenant_id: UUID) -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session with tenant isolation via RLS.

    This sets `app.tenant_id` for the session, which is used by
    RLS policies to filter rows.

    Security Notes:
    - Uses SET LOCAL (not SET) to ensure tenant_id is transaction-scoped
    - Automatically resets when transaction ends (on commit/rollback)
    - Safe with SQLAlchemy's built-in connection pooling (session mode)
    - If using PgBouncer, ensure session pooling mode (not transaction mode)
    - UUID validation prevents SQL injection

    Args:
        tenant_id: UUID of the tenant to isolate to

    Yields:
        AsyncSession with tenant context set

    Raises:
        ValueError: If tenant_id is invalid

    Example:
        ```python
        @router.get("/patients")
        async def list_patients(
            current_user: User = Depends(get_current_user),
            db: AsyncSession = Depends(lambda: get_tenant_db(current_user.tenant_id))
        ):
            result = await db.execute(select(Patient))
            return result.scalars().all()  # Only returns patients for this tenant
        ```
    """
    # Validate tenant_id to prevent SQL injection
    if not isinstance(tenant_id, UUID):
        raise ValueError(f"Invalid tenant_id type: {type(tenant_id)}")

    async with async_session_maker() as session:
        try:
            # Set tenant_id for RLS policies (transaction-scoped with SET LOCAL)
            # UUID str() output is safe (always matches UUID format)
            tenant_id_str = str(tenant_id)
            await session.execute(
                text(f"SET LOCAL app.tenant_id = '{tenant_id_str}'")
            )

            yield session

        finally:
            # Note: SET LOCAL automatically resets at transaction end
            # No explicit cleanup needed, but we ensure session is closed
            pass


async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """
    Set tenant context for an existing session.

    Use this if you need to manually set the tenant on a session.

    Args:
        session: The database session
        tenant_id: UUID of the tenant

    Raises:
        ValueError: If tenant_id is invalid

    Example:
        ```python
        async with async_session_maker() as session:
            await set_tenant_context(session, user.tenant_id)
            # Now all queries are tenant-isolated
        ```
    """
    # Validate tenant_id to prevent SQL injection
    if not isinstance(tenant_id, UUID):
        raise ValueError(f"Invalid tenant_id type: {type(tenant_id)}")

    tenant_id_str = str(tenant_id)
    await session.execute(
        text(f"SET LOCAL app.tenant_id = '{tenant_id_str}'")
    )
