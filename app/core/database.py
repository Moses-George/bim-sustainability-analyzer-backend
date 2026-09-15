# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, declarative_base
# from backend.app.core.config import settings

# engine = create_engine(settings.DATABASE_URL, future=True,
#     connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {})
# SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
# Base = declarative_base()

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# async_url = settings.DATABASE_URL.replace("postgresql", "postgresql+asyncpg")
# async_engine = create_async_engine(
#     async_url,
#     echo=True,
# )
# AsyncSessionLocal = async_sessionmaker(
#     bind=async_engine, expire_on_commit=False, autoflush=False, autocommit=False
# )


class Base(DeclarativeBase):
    pass


# Sync — used by Celery workers (swap postgresql+asyncpg → postgresql+psycopg2)
sync_url = settings.DATABASE_URL.replace("postgresql", "postgresql+psycopg2")
sync_engine = create_engine(sync_url)
SyncSessionLocal = sessionmaker(
    expire_on_commit=False, bind=sync_engine, autoflush=False, autocommit=False
)


# async def get_async_db() -> AsyncSession:  # type: ignore
#     async with AsyncSessionLocal() as session:
#         try:
#             yield session
#         finally:
#             await session.close()


def get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


