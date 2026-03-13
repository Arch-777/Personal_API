import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.core.auth import get_current_user
from api.core.db import get_db
from api.main import app
from rag.chunker import chunk_text
from rag.context import ContextBuilder
from rag.embedder import DeterministicEmbedder, cosine_similarity
from rag.engine import RAGEngine
from rag.retriever import HybridRetriever, RetrievedItem


class _FakeScalarResult:
	def __init__(self, rows):
		self._rows = rows

	def all(self):
		return self._rows


class _FakeResult:
	def __init__(self, rows):
		self._rows = rows

	def scalars(self):
		return _FakeScalarResult(self._rows)


class FakeRetrieverDb:
	def __init__(self, rows):
		self.rows = rows

	def execute(self, _stmt):
		return _FakeResult(self.rows)


def test_chunk_text_builds_overlapping_windows():
	text = " ".join([f"token{i}" for i in range(0, 120)])
	chunks = chunk_text(text=text, max_tokens=40, overlap_tokens=10, chunk_id_prefix="doc")

	assert len(chunks) >= 3
	assert chunks[0].chunk_id == "doc:0"
	assert chunks[0].token_count == 40
	assert chunks[1].metadata["token_start"] == 30


def test_deterministic_embedder_is_stable():
	embedder = DeterministicEmbedder(dimensions=32)
	first = embedder.embed_text("meeting notes")
	second = embedder.embed_text("meeting notes")
	third = embedder.embed_text("different content")

	assert len(first) == 32
	assert first == second
	assert first != third


def test_cosine_similarity_for_same_and_different_vectors():
	embedder = DeterministicEmbedder(dimensions=32)
	a = embedder.embed_text("alpha")
	b = embedder.embed_text("alpha")
	c = embedder.embed_text("beta")

	assert cosine_similarity(a, b) > 0.99
	assert cosine_similarity(a, c) < 0.99


def test_hybrid_retriever_ranks_relevant_items_first():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="drive",
			title="Quarterly meeting agenda",
			summary="Agenda and follow-ups",
			content="Meeting agenda details",
			metadata_json={"file_path": "/users/u/data/drive/doc1.json"},
			item_date=now,
			file_path="/users/u/data/drive/doc1.json",
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Shopping list",
			summary="Groceries",
			content="Milk and eggs",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="meeting agenda", top_k=5)

	assert len(results) == 1
	assert results[0].source == "drive"
	assert results[0].score > 0


def test_context_builder_collects_sources_and_links():
	builder = ContextBuilder()
	retrieved = [
		RetrievedItem(
			id="1",
			type="document",
			source="drive",
			title="Plan",
			content="Project plan body",
			summary="Project plan",
			metadata={"web_view_link": "https://example.com/doc"},
			item_date=None,
			file_path="/users/u/data/drive/plan.json",
			score=1.2,
		)
	]
	built = builder.build(query="project plan", retrieved=retrieved)

	assert len(built.sources) == 1
	assert built.sources[0]["id"] == "1"
	assert built.file_links == ["https://example.com/doc"]
	assert "drive/document" in built.context_text


def test_rag_engine_returns_answer_with_sources():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Roadmap",
			summary="Roadmap summary",
			content="Q1 objectives and timeline",
			metadata_json={"file_path": "/users/u/data/notion/roadmap.json"},
			item_date=now,
			file_path="/users/u/data/notion/roadmap.json",
			embedding=None,
			created_at=now,
		)
	]
	db = FakeRetrieverDb(rows)
	engine = RAGEngine(db=db, user_id=uuid.uuid4())
	result = engine.query("roadmap", top_k=5)

	assert "answer" in result
	assert len(result["sources"]) == 1
	assert len(result["documents"]) == 1
	assert len(result["file_links"]) == 1


class FakeChatDb:
	def __init__(self):
		self.added = []

	def add(self, obj):
		if getattr(obj, "id", None) is None:
			obj.id = uuid.uuid4()
		self.added.append(obj)

	def commit(self):
		return None

	def refresh(self, _obj):
		return None


def _override_user():
	return SimpleNamespace(id=uuid.uuid4())


def test_chat_endpoint_returns_rag_payload(monkeypatch):
	from api.routers import chat as chat_router

	fake_db = FakeChatDb()
	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = _override_user

	monkeypatch.setattr(
		chat_router.RAGEngine,
		"query",
		lambda self, query, top_k=8, type_filter=None: {
			"answer": "Synthetic answer",
			"sources": [
				{
					"id": "doc-1",
					"type": "document",
					"source": "notion",
					"score": 0.9,
					"preview": "preview",
				}
			],
			"documents": ["Roadmap"],
			"file_links": ["/users/u/data/notion/roadmap.json"],
		},
	)

	client = TestClient(app)
	response = client.post("/v1/chat/message", json={"message": "What is in my roadmap?"})

	assert response.status_code == 200
	body = response.json()
	assert body["answer"] == "Synthetic answer"
	assert len(body["sources"]) == 1
	assert body["documents"] == ["Roadmap"]

	app.dependency_overrides.clear()

