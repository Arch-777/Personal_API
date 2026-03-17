BEGIN;

-- Query-path index: enforce user-first lookups on feed/document retrieval.
CREATE INDEX IF NOT EXISTS idx_items_user_type_created
	ON items(user_id, type, created_at DESC);

-- Prefer HNSW for vector similarity at larger scale while keeping existing indexes intact.
CREATE INDEX IF NOT EXISTS idx_items_embedding_hnsw
	ON items USING hnsw (embedding vector_cosine_ops)
	WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_item_chunks_embedding_hnsw
	ON item_chunks USING hnsw (embedding vector_cosine_ops)
	WHERE embedding IS NOT NULL;

-- Database-level tenant isolation.
ALTER TABLE items ENABLE ROW LEVEL SECURITY;
ALTER TABLE item_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS items_user_isolation ON items;
CREATE POLICY items_user_isolation ON items
	USING (
		user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
	);

DROP POLICY IF EXISTS item_chunks_user_isolation ON item_chunks;
CREATE POLICY item_chunks_user_isolation ON item_chunks
	USING (
		user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
	);

COMMIT;
