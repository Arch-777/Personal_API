from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import exists, func, select, text

from api.core.db import SessionLocal, engine
from api.models.item import Item
from api.models.item_chunk import ItemChunk
from api.models.user import User  # noqa: F401
from rag.indexer import index_item_chunks


EXPECTED_DATABASE_NAME = "personalapi"
MIGRATION_FILE = Path(__file__).resolve().parents[1] / "migrations" / "002_item_chunks.sql"


def main() -> int:
	parser = argparse.ArgumentParser(description="Backfill item_chunks for existing items safely.")
	parser.add_argument("--batch-size", type=int, default=100)
	parser.add_argument("--limit", type=int, default=None)
	parser.add_argument(
		"--mode",
		choices=["append", "reindex"],
		default="append",
		help="append: only process items without chunks (safe default); reindex: rebuild chunks for all items",
	)
	args = parser.parse_args()

	database_name = _get_current_database_name()
	print(f"Connected database: {database_name}")
	if database_name != EXPECTED_DATABASE_NAME:
		raise SystemExit(
			f"Refusing to run backfill because current database is '{database_name}', expected '{EXPECTED_DATABASE_NAME}'."
		)

	if not _item_chunks_table_exists():
		print("item_chunks table missing; applying migration 002_item_chunks.sql")
		_apply_chunk_migration()

	with SessionLocal() as db:
		total_items = db.scalar(select(func.count()).select_from(Item)) or 0
		existing_chunks = db.scalar(select(func.count()).select_from(ItemChunk)) or 0
		chunked_items = db.scalar(select(func.count(func.distinct(ItemChunk.item_id))).select_from(ItemChunk)) or 0
		print(f"Items in database: {total_items}")
		print(f"Existing chunks: {existing_chunks}")
		print(f"Items already chunked: {chunked_items}")
		print(f"Backfill mode: {args.mode}")

	processed = 0
	indexed_items = 0
	indexed_chunks = 0
	last_item_id = None
	batch_size = max(1, int(args.batch_size))
	remaining_limit = args.limit

	while True:
		with SessionLocal() as db:
			stmt = select(Item).order_by(Item.id.asc()).limit(batch_size)
			if args.mode == "append":
				stmt = stmt.where(
					~exists(select(ItemChunk.id).where(ItemChunk.item_id == Item.id))
				)
			if last_item_id is not None:
				stmt = stmt.where(Item.id > last_item_id)
			if remaining_limit is not None:
				stmt = stmt.limit(min(batch_size, remaining_limit))

			items = db.execute(stmt).scalars().all()
			if not items:
				break

			batch_indexed_items = 0
			batch_chunks = 0
			for item in items:
				result = index_item_chunks(db=db, item=item)
				metadata = dict(item.metadata_json or {})
				metadata["embedding_status"] = "completed"
				metadata["chunk_count"] = result.chunk_count
				item.metadata_json = metadata
				batch_indexed_items += 1
				batch_chunks += result.chunk_count
				last_item_id = item.id

			db.commit()

		processed += len(items)
		indexed_items += batch_indexed_items
		indexed_chunks += batch_chunks
		if remaining_limit is not None:
			remaining_limit -= len(items)
		print(
			f"Processed {processed} items total | indexed this batch: {batch_indexed_items} | "
			f"chunks this batch: {batch_chunks}"
		)
		if remaining_limit is not None and remaining_limit <= 0:
			break

	print(f"Backfill completed. Indexed items: {indexed_items}; chunk rows written: {indexed_chunks}")
	return 0


def _get_current_database_name() -> str:
	with engine.connect() as conn:
		return str(conn.execute(text("SELECT current_database()")).scalar_one())


def _item_chunks_table_exists() -> bool:
	with engine.connect() as conn:
		return conn.execute(text("SELECT to_regclass('public.item_chunks')")).scalar_one() is not None


def _apply_chunk_migration() -> None:
	sql_text = MIGRATION_FILE.read_text(encoding="utf-8")
	with engine.raw_connection() as raw_conn:
		with raw_conn.cursor() as cursor:
			cursor.execute(sql_text)
		raw_conn.commit()


if __name__ == "__main__":
	raise SystemExit(main())