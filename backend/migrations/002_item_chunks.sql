BEGIN;

CREATE TABLE IF NOT EXISTS item_chunks (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	item_id UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
	user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
	chunk_id TEXT NOT NULL,
	chunk_index INTEGER NOT NULL,
	chunk_text TEXT NOT NULL,
	token_count INTEGER NOT NULL DEFAULT 0,
	metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
	embedding vector(1536),
	content_tsv tsvector GENERATED ALWAYS AS (
		to_tsvector('english', coalesce(chunk_text, ''))
	) STORED,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT uq_item_chunks_item_chunk_index UNIQUE (item_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_item_chunks_item_id ON item_chunks(item_id);
CREATE INDEX IF NOT EXISTS idx_item_chunks_user_item ON item_chunks(user_id, item_id);
CREATE INDEX IF NOT EXISTS idx_item_chunks_user_created ON item_chunks(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_item_chunks_content_tsv ON item_chunks USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS idx_item_chunks_embedding_ivfflat
	ON item_chunks USING ivfflat (embedding vector_cosine_ops)
	WITH (lists = 100)
	WHERE embedding IS NOT NULL;

COMMIT;