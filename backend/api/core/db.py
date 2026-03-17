from collections.abc import Generator
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from api.core.config import get_settings


settings = get_settings()

engine = create_engine(
	settings.database_url,
	pool_pre_ping=True,
	pool_size=settings.database_pool_size,
	max_overflow=settings.database_max_overflow,
	pool_timeout=settings.database_pool_timeout,
	pool_recycle=settings.database_pool_recycle_seconds,
	connect_args={
		"sslmode": settings.database_ssl_mode,
		"connect_timeout": settings.database_connect_timeout,
	},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


class Base(DeclarativeBase):
	pass


def get_db() -> Generator[Session, None, None]:
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()


def check_database_connection(retries: int = 0, retry_delay_seconds: float = 1.0) -> None:
	"""Validate database reachability with bounded retries; raise RuntimeError on failure."""
	attempts = max(0, int(retries)) + 1
	for attempt in range(1, attempts + 1):
		try:
			with engine.connect() as conn:
				conn.execute(text("SELECT 1"))
			return
		except SQLAlchemyError as exc:
			if attempt >= attempts:
				raise RuntimeError(f"Database connection failed: {exc}") from exc
			delay = max(0.0, float(retry_delay_seconds))
			if delay > 0:
				time.sleep(delay)

