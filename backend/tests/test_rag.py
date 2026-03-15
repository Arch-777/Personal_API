import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.core.auth import get_current_user
from api.core.db import get_db
from api.main import app
from rag.chunker import chunk_text
from rag.context import ContextBuilder
from rag.embedder import DeterministicEmbedder, cosine_similarity
from rag.engine import RAGEngine, _compose_retrieval_query
from rag.generator import OllamaGenerator
from rag.query_rewriter import QueryRewriter
from rag.reranker import LightweightReranker
from rag.retriever import HybridRetriever, RetrievedItem, _apply_rank_fusion, _mmr_select


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


class _FakeChunkResult:
	def __init__(self, rows):
		self._rows = rows

	def all(self):
		return self._rows


class FakeChunkFirstRetrieverDb:
	def __init__(self, chunk_rows, item_rows):
		self.chunk_rows = chunk_rows
		self.item_rows = item_rows

	def execute(self, stmt):
		if "item_chunks" in str(stmt):
			return _FakeChunkResult(self.chunk_rows)
		return _FakeResult(self.item_rows)


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


def test_hybrid_retriever_prioritizes_title_matches_over_body_only_matches():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="drive",
			title="Quarterly risk register",
			summary="Risk review",
			content="General planning notes",
			metadata_json={},
			item_date=now,
			file_path="/users/u/data/drive/risk-register.json",
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Project planning",
			summary="General summary",
			content="This document contains risk register notes in the body",
			metadata_json={},
			item_date=now,
			file_path="/users/u/data/notion/planning.json",
			embedding=None,
			created_at=now,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="risk register", top_k=5)

	assert len(results) == 2
	assert results[0].source == "drive"
	assert "risk register" in (results[0].title or "").lower()


def test_hybrid_retriever_prefers_more_recent_item_when_relevance_is_equal():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="drive",
			title="Team roadmap",
			summary="Quarterly roadmap",
			content="Objectives and timeline",
			metadata_json={},
			item_date=now - timedelta(days=2),
			file_path="/users/u/data/drive/roadmap-new.json",
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Team roadmap",
			summary="Quarterly roadmap",
			content="Objectives and timeline",
			metadata_json={},
			item_date=now - timedelta(days=140),
			file_path="/users/u/data/notion/roadmap-old.json",
			embedding=None,
			created_at=now,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="team roadmap", top_k=5)

	assert len(results) == 2
	assert results[0].item_date > results[1].item_date


def test_hybrid_retriever_handles_mixed_naive_and_aware_item_dates_in_sorting():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="drive",
			title="Team retrospective",
			summary="Sprint notes",
			content="Retrospective outcomes",
			metadata_json={},
			item_date=now,
			file_path="/users/u/data/drive/retro.json",
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Team retrospective",
			summary="Sprint notes",
			content="Retrospective outcomes",
			metadata_json={},
			item_date=(now - timedelta(days=1)).replace(tzinfo=None),
			file_path="/users/u/data/notion/retro.json",
			embedding=None,
			created_at=now,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="team retrospective", top_k=5)

	assert len(results) == 2
	assert results[0].source == "drive"


def test_hybrid_retriever_ignores_stopword_noise_for_mail_queries():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="email",
			source="gmail",
			title="LinkedIn security alert",
			summary="We detected a new login to your LinkedIn account",
			content="LinkedIn sent a sign-in alert email",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="track",
			source="spotify",
			title="If We Have Each Other",
			summary="Popular song",
			content="Song metadata",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="any linkedin mail for me", top_k=5)

	assert len(results) == 1
	assert results[0].source == "gmail"
	assert results[0].type == "email"


def test_hybrid_retriever_dedupes_and_prefers_favorite_spotify_tracks():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="track",
			source="spotify",
			source_id="track-1",
			title="Where'd All the Time Go?",
			summary="Indie track",
			content="Where'd All the Time Go? by Dr. Dog",
			metadata_json={"track_id": "track-1", "popularity": 40, "liked": False},
			item_date=now,
			file_path=None,
			embedding=None,
			sender_name="Dr. Dog",
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="track",
			source="spotify",
			source_id="track-1",
			title="Where'd All the Time Go?",
			summary="Duplicate variant",
			content="Where'd All the Time Go? by Dr. Dog",
			metadata_json={"track_id": "track-1", "popularity": 90, "liked": True, "top_rank": 1},
			item_date=now,
			file_path=None,
			embedding=None,
			sender_name="Dr. Dog",
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="email",
			source="gmail",
			source_id="msg-1",
			title="Your Spotify login code",
			summary="Security email",
			content="Spotify login code inside",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			sender_name=None,
			created_at=now,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="spotify all time favourite songs", top_k=5)

	assert len(results) >= 1
	assert results[0].source == "spotify"
	assert results[0].type == "track"
	assert results[0].source_id == "track-1"
	assert len([result for result in results if result.source_id == "track-1"]) == 1


def test_hybrid_retriever_routes_last_mail_query_to_recent_gmail_only():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="track",
			source="spotify",
			source_id="trk-11",
			title="Golden Brown",
			summary="song",
			content="Golden Brown by The Stranglers",
			metadata_json={"track_id": "trk-11"},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
			sender_name="The Stranglers",
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="email",
			source="gmail",
			source_id="msg-10",
			title="Latest payroll update",
			summary="Payroll has been processed",
			content="Your payroll for this month is complete",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
			sender_name=None,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="email",
			source="gmail",
			source_id="msg-09",
			title="Meeting reminder",
			summary="Reminder",
			content="Please join the review call",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
			sender_name=None,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="last 5mails", top_k=8)

	assert len(results) == 2
	assert all(result.source == "gmail" for result in results)
	assert all(result.type == "email" for result in results)


def test_hybrid_retriever_routes_slack_message_query_to_slack_only():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="message",
			source="slack",
			source_id="slack-1",
			title="standup update",
			summary="Daily sync",
			content="Deploy completed in #engineering",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
			sender_name="dev-user",
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="email",
			source="gmail",
			source_id="msg-1",
			title="newsletter",
			summary="Weekly update",
			content="A long email body",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
			sender_name=None,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="show my slack messages", top_k=8)

	assert len(results) == 1
	assert results[0].source == "slack"


def test_hybrid_retriever_understands_docs_token_and_excludes_spotify_noise():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="track",
			source="spotify",
			title="Random song",
			summary="music",
			content="audio",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Privacy policy",
			summary="Risk summary table",
			content="sell or share user data with third parties",
			metadata_json={},
			item_date=now,
			file_path="/users/u/data/notion/policy.json",
			embedding=None,
			created_at=now,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="show docs", top_k=5)

	assert len(results) >= 1
	assert all(result.source in {"notion", "drive"} for result in results)
	assert all(result.type in {"document", "note", "page", "file"} or result.source in {"notion", "drive"} for result in results)


def test_hybrid_retriever_prioritizes_notion_when_query_mentions_notion_docs():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Risk Register",
			summary="Risk summary table",
			content="Mitigation and controls",
			metadata_json={},
			item_date=now,
			file_path="/users/u/data/notion/risk.json",
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="drive",
			title="General notes",
			summary="misc",
			content="non-notion content",
			metadata_json={},
			item_date=now,
			file_path="/users/u/data/drive/notes.json",
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="track",
			source="spotify",
			title="Song",
			summary="music",
			content="audio",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="show in notion docs", top_k=5)

	assert len(results) >= 1
	assert all(result.source == "notion" for result in results)


def test_hybrid_retriever_prefers_chunk_candidates_over_item_fallback():
	now = datetime.now(UTC)
	class _NoItemFallbackDb:
		def execute(self, _stmt):
			raise AssertionError("Item fallback query should not run when chunk candidates exist")

	class _ChunkFirstRetriever(HybridRetriever):
		def _retrieve_chunk_candidates(self, *args, **kwargs):
			return [
				RetrievedItem(
					id=str(uuid.uuid4()),
					type="document",
					source="notion",
					source_id="page-1",
					title="Policy",
					summary="Notion policy",
					content="Policy details",
					metadata={"file_path": "/users/u/data/notion/policy.json"},
					item_date=now,
					file_path="/users/u/data/notion/policy.json",
					score=0.9,
					chunk_id="item:1:0",
					chunk_index=0,
					chunk_text="notion policy details",
				)
			]

	retriever = _ChunkFirstRetriever(_NoItemFallbackDb())
	results = retriever.retrieve(user_id=uuid.uuid4(), query="show notion docs", top_k=5)

	assert len(results) == 1
	assert results[0].source == "notion"
	assert results[0].chunk_id == "item:1:0"


def test_hybrid_retriever_uses_lexical_candidates_when_semantic_missing():
	now = datetime.now(UTC)

	class _NoFallbackDb:
		def execute(self, _stmt):
			raise AssertionError("Item fallback should not run when lexical candidates exist")

	class _LexicalOnlyRetriever(HybridRetriever):
		def _retrieve_chunk_candidates(self, *args, **kwargs):
			return []

		def _retrieve_lexical_chunk_candidates(self, *args, **kwargs):
			return [
				RetrievedItem(
					id=str(uuid.uuid4()),
					type="document",
					source="drive",
					source_id="doc-77",
					title="Risk policy",
					summary="Lexical match",
					content="risk controls",
					metadata={},
					item_date=now,
					file_path="/users/u/data/drive/risk.json",
					score=0.8,
					chunk_id="item:77:0",
					chunk_index=0,
					chunk_text="risk controls and guardrails",
				)
			]

	retriever = _LexicalOnlyRetriever(_NoFallbackDb())
	results = retriever.retrieve(user_id=uuid.uuid4(), query="risk policy", top_k=5)

	assert len(results) == 1
	assert results[0].source == "drive"
	assert results[0].chunk_id == "item:77:0"


def test_apply_rank_fusion_prefers_semantic_or_lexical_by_configurable_weights():
	semantic_strong = RetrievedItem(
		id="sem",
		type="document",
		source="notion",
		score=1.0,
		debug={"distance": 0.05, "lexical_score": 0.01},
	)
	lexical_strong = RetrievedItem(
		id="lex",
		type="document",
		source="drive",
		score=1.0,
		debug={"distance": 0.8, "lexical_score": 0.9},
	)

	semantic_weighted = _apply_rank_fusion(
		[semantic_strong, lexical_strong],
		semantic_weight=0.9,
		lexical_weight=0.1,
		boost=8.0,
	)
	semantic_score = next(item.score for item in semantic_weighted if item.id == "sem")
	lexical_score = next(item.score for item in semantic_weighted if item.id == "lex")
	assert semantic_score > lexical_score

	semantic_strong_2 = RetrievedItem(
		id="sem2",
		type="document",
		source="notion",
		score=1.0,
		debug={"distance": 0.05, "lexical_score": 0.01},
	)
	lexical_strong_2 = RetrievedItem(
		id="lex2",
		type="document",
		source="drive",
		score=1.0,
		debug={"distance": 0.8, "lexical_score": 0.9},
	)
	lexical_weighted = _apply_rank_fusion(
		[semantic_strong_2, lexical_strong_2],
		semantic_weight=0.1,
		lexical_weight=0.9,
		boost=8.0,
	)
	semantic_score_2 = next(item.score for item in lexical_weighted if item.id == "sem2")
	lexical_score_2 = next(item.score for item in lexical_weighted if item.id == "lex2")
	assert lexical_score_2 > semantic_score_2


def test_query_rewriter_expands_domain_hints():
	rewriter = QueryRewriter(enabled=True, max_variants=3)
	variants = rewriter.rewrite("show docs")

	assert len(variants) >= 1
	assert any("documents" in variant for variant in variants)
	assert any("notion" in variant or "drive" in variant for variant in variants)


def test_compose_retrieval_query_blends_recent_session_turns():
	retrieval_query = _compose_retrieval_query(
		"what about last week",
		[
			{"role": "user", "content": "Show my GitHub repositories"},
			{"role": "assistant", "content": "Here are your top repos and recent updates"},
		],
	)

	assert "what about last week" in retrieval_query
	assert "Context from current session" in retrieval_query
	assert "GitHub repositories" in retrieval_query
	assert "top repos and recent updates" not in retrieval_query


def test_hybrid_retriever_prefers_github_when_query_mentions_repositories():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="repository",
			source="github",
			source_id="repo-1",
			title="Personal_API",
			summary="Main backend repository",
			content="Includes API, workers, and RAG",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
			sender_name=None,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="email",
			source="gmail",
			source_id="msg-1",
			title="Project update",
			summary="Summary notes",
			content="General status update",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
			sender_name=None,
		),
	]

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)
	results = retriever.retrieve(user_id=uuid.uuid4(), query="which github repositories did I work on", top_k=5)

	assert len(results) >= 1
	assert results[0].source == "github"


def test_rag_engine_uses_rewritten_variant_when_original_misses():
	class _StubEmbedder:
		def embed_text(self, _text: str):
			return [0.0] * 8

	class _RewriteAwareRetriever:
		def __init__(self):
			self.queries: list[str] = []

		def retrieve(
			self,
			user_id,
			query,
			top_k=8,
			type_filter=None,
			query_embedding=None,
			include_debug=False,
			date_after=None,
		):
			self.queries.append(query)
			if "gmail" not in query:
				return []
			return [
				RetrievedItem(
					id="email-1",
					type="email",
					source="gmail",
					title="Invoice",
					content="Invoice from vendor",
					summary="Invoice received",
					score=0.9,
				)
			]

	retriever = _RewriteAwareRetriever()
	engine = RAGEngine(
		db=SimpleNamespace(),
		user_id=uuid.uuid4(),
		embedder=_StubEmbedder(),
		retriever=retriever,
		query_rewriter=QueryRewriter(enabled=True, max_variants=3),
		reranker=LightweightReranker(enabled=False),
		use_llm=False,
	)

	result = engine.query("show mail", top_k=5)

	assert "answer" in result
	assert len(result["sources"]) == 1
	assert any("gmail" in query for query in retriever.queries)


def test_lightweight_reranker_reorders_by_query_alignment():
	reranker = LightweightReranker(enabled=True, weight=1.0, top_n=5)
	items = [
		RetrievedItem(
			id="1",
			type="document",
			source="notion",
			title="Random Notes",
			content="general unrelated text",
			summary="misc",
			score=1.0,
		),
		RetrievedItem(
			id="2",
			type="document",
			source="drive",
			title="Incident response playbook",
			content="incident response runbook and mitigation",
			summary="response plan",
			score=0.8,
		),
	]

	reranked = reranker.rerank("incident response", items, include_debug=True)
	assert reranked[0].id == "2"
	assert reranked[0].debug.get("reranker_applied") is True


def test_mmr_select_reduces_near_duplicate_items():
	items = [
		RetrievedItem(
			id="1",
			type="document",
			source="drive",
			title="Roadmap A",
			content="Roadmap planning and milestones",
			summary="Roadmap planning",
			score=1.0,
		),
		RetrievedItem(
			id="2",
			type="document",
			source="drive",
			title="Roadmap B",
			content="Roadmap planning and milestones for team",
			summary="Roadmap planning",
			score=0.99,
		),
		RetrievedItem(
			id="3",
			type="document",
			source="notion",
			title="Risk Register",
			content="Key risks and mitigations",
			summary="Risk log",
			score=0.95,
		),
	]

	selected = _mmr_select(items, top_k=2)
	selected_ids = {item.id for item in selected}

	assert len(selected) == 2
	assert "1" in selected_ids
	assert "3" in selected_ids


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


def test_context_builder_compose_answer_builds_message_digest_for_slack_query():
	now = datetime.now(UTC)
	builder = ContextBuilder()
	retrieved = [
		RetrievedItem(
			id="slack-1",
			type="message",
			source="slack",
			title="Standup update",
			summary="Backend deploy finished",
			content="Deploy completed for API and worker",
			metadata={"channel_name": "engineering", "channel_type": "public_channel"},
			item_date=now,
			file_path=None,
			score=1.0,
		),
	]

	answer = builder.compose_answer("show my slack messages", retrieved)

	assert "Slack Messages" in answer
	assert "Found **1 message(s)**" in answer
	assert "#engineering" in answer


def test_context_builder_compose_answer_mentions_slack_sync_when_no_data():
	builder = ContextBuilder()
	answer = builder.compose_answer("show my slack messages", [])

	assert "No Slack messages found yet" in answer
	assert "Sync your Slack connector" in answer


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


def test_rag_engine_include_debug_adds_source_breakdown():
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
	result = engine.query("roadmap", top_k=5, include_debug=True)

	assert len(result["sources"]) == 1
	assert "debug" in result["sources"][0]
	assert "total_score" in result["sources"][0]["debug"]


def test_rag_engine_uses_llm_generator_when_enabled():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Architecture",
			summary="Architecture summary",
			content="System has API, workers and retrieval components",
			metadata_json={"file_path": "/users/u/data/notion/architecture.json"},
			item_date=now,
			file_path="/users/u/data/notion/architecture.json",
			embedding=None,
			created_at=now,
		)
	]

	class _FakeGenerator:
		def generate(self, query: str, context_text: str) -> str:
			assert "architecture" in query.lower()
			assert "notion/document" in context_text
			return "Architecture summary and retrieval components [1]"

	db = FakeRetrieverDb(rows)
	engine = RAGEngine(db=db, user_id=uuid.uuid4(), generator=_FakeGenerator(), use_llm=True)
	result = engine.query("show my architecture notes", top_k=5)

	assert result["answer"] == "Architecture summary and retrieval components [1]"
	assert result["answer_mode"] == "llm"
	assert len(result["sources"]) == 1


def test_rag_engine_falls_back_when_llm_answer_has_no_valid_citations():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Architecture",
			summary="Architecture summary",
			content="System has API, workers and retrieval components",
			metadata_json={"file_path": "/users/u/data/notion/architecture.json"},
			item_date=now,
			file_path="/users/u/data/notion/architecture.json",
			embedding=None,
			created_at=now,
		)
	]

	class _InvalidCitationGenerator:
		def generate(self, query: str, context_text: str) -> str:
			return "Ungrounded answer with no source markers"

	db = FakeRetrieverDb(rows)
	engine = RAGEngine(db=db, user_id=uuid.uuid4(), generator=_InvalidCitationGenerator(), use_llm=True)
	result = engine.query("show my architecture notes", top_k=5)

	assert result["answer_mode"] == "fallback"
	assert isinstance(result["answer"], str)
	assert result["answer"]


def test_rag_engine_falls_back_when_claim_text_does_not_align_with_cited_source():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Architecture",
			summary="Architecture summary",
			content="System has API, workers and retrieval components",
			metadata_json={"file_path": "/users/u/data/notion/architecture.json"},
			item_date=now,
			file_path="/users/u/data/notion/architecture.json",
			embedding=None,
			created_at=now,
		)
	]

	class _MisalignedCitationGenerator:
		def generate(self, query: str, context_text: str) -> str:
			return "The answer is about weather forecast and stock market [1]"

	db = FakeRetrieverDb(rows)
	engine = RAGEngine(db=db, user_id=uuid.uuid4(), generator=_MisalignedCitationGenerator(), use_llm=True)
	result = engine.query("show my architecture notes", top_k=5)

	assert result["answer_mode"] == "fallback"


def test_rag_engine_uses_failover_generator_when_primary_fails():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Architecture",
			summary="Architecture summary",
			content="System has API, workers and retrieval components",
			metadata_json={"file_path": "/users/u/data/notion/architecture.json"},
			item_date=now,
			file_path="/users/u/data/notion/architecture.json",
			embedding=None,
			created_at=now,
		)
	]

	class _PrimaryBrokenGenerator:
		def generate(self, query: str, context_text: str) -> str:
			raise RuntimeError("primary unavailable")

	class _FailoverGenerator:
		def generate(self, query: str, context_text: str) -> str:
			return "Architecture retrieval components [1]"

	db = FakeRetrieverDb(rows)
	engine = RAGEngine(
		db=db,
		user_id=uuid.uuid4(),
		generator=_PrimaryBrokenGenerator(),
		failover_generator=_FailoverGenerator(),
		use_llm=True,
	)
	engine.llm_failover_enabled = True

	result = engine.query("show my architecture notes", top_k=5, include_debug=True)

	assert result["answer_mode"] == "llm"
	assert "[1]" in result["answer"]
	assert result["sources"][0]["debug"]["llm_provider_used"] == "failover"


def test_rag_engine_returns_timing_observability_payload():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Roadmap",
			summary="Roadmap summary",
			content="Q1 objectives and timeline",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		)
	]

	result = RAGEngine(db=FakeRetrieverDb(rows), user_id=uuid.uuid4(), use_llm=False).query("roadmap", top_k=5)

	assert "timings" in result
	assert isinstance(result["timings"].get("total_ms"), float)
	assert result["timings"].get("total_ms", 0.0) >= 0.0


def test_rag_engine_reuses_query_embedding_and_retrieval_cache_for_repeat_query():
	class _CountingEmbedder:
		def __init__(self):
			self.calls = 0

		def embed_text(self, _text: str):
			self.calls += 1
			return [0.1] * 8

	class _CountingRetriever:
		def __init__(self):
			self.calls = 0

		def retrieve(
			self,
			user_id,
			query,
			top_k=8,
			type_filter=None,
			query_embedding=None,
			include_debug=False,
			date_after=None,
		):
			self.calls += 1
			return [
				RetrievedItem(
					id="doc-1",
					type="document",
					source="notion",
					title="Roadmap",
					summary="Roadmap summary",
					content="Q2 milestones",
					score=0.9,
				)
			]

	embedder = _CountingEmbedder()
	retriever = _CountingRetriever()
	engine = RAGEngine(
		db=SimpleNamespace(),
		user_id=uuid.uuid4(),
		embedder=embedder,
		retriever=retriever,
		query_rewriter=QueryRewriter(enabled=False),
		reranker=LightweightReranker(enabled=False),
		use_llm=False,
	)

	first = engine.query("show my roadmap notes", top_k=5)
	second = engine.query("show my roadmap notes", top_k=5)

	assert first["answer"]
	assert second["answer"]
	assert embedder.calls == 1
	assert retriever.calls == 1


def test_rag_engine_opens_circuit_breaker_after_failure_and_skips_next_llm_call():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Architecture",
			summary="Architecture summary",
			content="System has API, workers and retrieval components",
			metadata_json={"file_path": "/users/u/data/notion/architecture.json"},
			item_date=now,
			file_path="/users/u/data/notion/architecture.json",
			embedding=None,
			created_at=now,
		)
	]

	class _AlwaysFailGenerator:
		def __init__(self):
			self.calls = 0

		def generate(self, query: str, context_text: str) -> str:
			self.calls += 1
			raise RuntimeError("provider unavailable")

	gen = _AlwaysFailGenerator()
	db = FakeRetrieverDb(rows)
	engine = RAGEngine(db=db, user_id=uuid.uuid4(), generator=gen, use_llm=True)
	engine.llm_circuit_breaker_enabled = True
	engine.llm_circuit_breaker_failure_threshold = 1
	engine.llm_circuit_breaker_cooldown_seconds = 120

	first = engine.query("show my architecture notes", top_k=5)
	second = engine.query("show my architecture notes", top_k=5)

	assert first["answer_mode"] == "fallback"
	assert second["answer_mode"] == "fallback"
	assert gen.calls == 1


def test_rag_engine_applies_neighbor_chunk_expansion_when_retriever_supports_it():
	class _NeighborAwareRetriever:
		def __init__(self):
			self.expansion_calls = 0

		def retrieve(
			self,
			user_id,
			query,
			top_k=8,
			type_filter=None,
			query_embedding=None,
			include_debug=False,
			date_after=None,
		):
			return [
				RetrievedItem(
					id="doc-1",
					type="document",
					source="notion",
					title="Roadmap",
					summary="Q2 milestones",
					content="Baseline content",
					score=0.9,
					chunk_index=2,
					chunk_text="core chunk",
				)
			]

		def expand_with_neighbor_chunks(self, results, window=1, include_debug=False):
			self.expansion_calls += 1
			results[0].chunk_text = f"neighbor evidence window={window}"
			return results

	class _StubEmbedder:
		def embed_text(self, _text: str):
			return [0.0] * 8

	retriever = _NeighborAwareRetriever()
	engine = RAGEngine(
		db=SimpleNamespace(),
		user_id=uuid.uuid4(),
		embedder=_StubEmbedder(),
		retriever=retriever,
		query_rewriter=QueryRewriter(enabled=False),
		reranker=LightweightReranker(enabled=False),
		use_llm=False,
	)
	engine.neighbor_chunk_enabled = True
	engine.neighbor_chunk_window = 1

	result = engine.query("show my roadmap notes", top_k=5)

	assert retriever.expansion_calls == 1
	assert "neighbor evidence" in result["context"]


def test_rag_engine_context_token_budget_limits_source_count():
	class _BudgetRetriever:
		def retrieve(
			self,
			user_id,
			query,
			top_k=8,
			type_filter=None,
			query_embedding=None,
			include_debug=False,
			date_after=None,
		):
			return [
				RetrievedItem(
					id="doc-1",
					type="document",
					source="notion",
					title="Roadmap",
					summary="first",
					content="first content",
					score=0.95,
					chunk_text="token " * 120,
				),
				RetrievedItem(
					id="doc-2",
					type="document",
					source="drive",
					title="Plan",
					summary="second",
					content="second content",
					score=0.9,
					chunk_text="token " * 120,
				),
			]

	class _StubEmbedder:
		def embed_text(self, _text: str):
			return [0.0] * 8

	engine = RAGEngine(
		db=SimpleNamespace(),
		user_id=uuid.uuid4(),
		embedder=_StubEmbedder(),
		retriever=_BudgetRetriever(),
		query_rewriter=QueryRewriter(enabled=False),
		reranker=LightweightReranker(enabled=False),
		use_llm=False,
	)
	engine.context_max_tokens = 140

	result = engine.query("show my roadmap", top_k=5)

	assert len(result["sources"]) == 1


def test_rag_engine_returns_fallback_answer_mode_when_llm_fails():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Architecture",
			summary="Architecture summary",
			content="System has API, workers and retrieval components",
			metadata_json={"file_path": "/users/u/data/notion/architecture.json"},
			item_date=now,
			file_path="/users/u/data/notion/architecture.json",
			embedding=None,
			created_at=now,
		)
	]

	class _BrokenGenerator:
		def generate(self, query: str, context_text: str) -> str:
			raise RuntimeError("ollama unavailable")

	db = FakeRetrieverDb(rows)
	engine = RAGEngine(db=db, user_id=uuid.uuid4(), generator=_BrokenGenerator(), use_llm=True)
	result = engine.query("show my architecture notes", top_k=5)

	assert result["answer_mode"] == "fallback"
	assert isinstance(result["answer"], str)
	assert result["answer"]


def test_rag_engine_skips_llm_when_no_retrieved_sources():
	class _TrackingGenerator:
		def __init__(self):
			self.called = False

		def generate(self, query: str, context_text: str) -> str:
			self.called = True
			return "should not be used"

	db = FakeRetrieverDb([])
	gen = _TrackingGenerator()
	engine = RAGEngine(db=db, user_id=uuid.uuid4(), generator=gen, use_llm=True)
	result = engine.query("what is my architecture", top_k=5)

	assert gen.called is False
	assert result["answer_mode"] == "abstain"
	assert "no supporting records" in result["answer"].lower()


def test_context_builder_compose_answer_returns_citation_based_output():
	builder = ContextBuilder()
	retrieved = [
		RetrievedItem(
			id="1",
			type="document",
			source="notion",
			title="Roadmap",
			content="Q2 milestones include auth hardening and search relevance tuning.",
			summary="Roadmap summary",
			metadata={},
			item_date=None,
			file_path=None,
			score=0.95,
		),
	]

	answer = builder.compose_answer("roadmap", retrieved)

	assert "here's what i found in your indexed data" in answer.lower()
	assert "[1]" in answer


def test_rag_engine_returns_abstain_when_scores_below_grounding_threshold():
	now = datetime.now(UTC)
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Roadmap",
			summary="Roadmap summary",
			content="Q1 planning notes",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		)
	]
	db = FakeRetrieverDb(rows)
	engine = RAGEngine(db=db, user_id=uuid.uuid4())
	engine.min_top_score = 10.0
	engine.min_avg_score = 10.0
	result = engine.query("roadmap", top_k=5)

	assert result["answer_mode"] == "abstain"
	assert "couldn't find confident evidence" in result["answer"].lower()


def test_ollama_prompt_contains_grounding_and_citation_rules():
	generator = OllamaGenerator(base_url="http://localhost:11434", model="qwen2.5:1.5b")
	prompt = generator._build_prompt(
		query="What did I write about roadmap?",
		context_text="[1] (notion/document) score=1.200 id=abc :: Roadmap has Q2 milestones",
	)

	assert "Retrieved Context" in prompt
	assert "source numbers like [1], [2]" in prompt
	assert "Only answer using retrieved context" in prompt


class FakeChatDb:
	def __init__(self):
		self.added = []
		self._rows = []

	def add(self, obj):
		if getattr(obj, "id", None) is None:
			obj.id = uuid.uuid4()
		self.added.append(obj)

	def commit(self):
		return None

	def refresh(self, _obj):
		return None

	def execute(self, _stmt):
		class _Rows:
			def __init__(self, rows):
				self._rows = rows

			def all(self):
				return self._rows

		class _Result:
			def __init__(self, rows):
				self._rows = rows

			def scalars(self):
				return _Rows(self._rows)

		return _Result([])


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
		lambda self, query, top_k=8, type_filter=None, include_debug=False, conversation_history=None: {
			"answer": "Synthetic answer",
			"sources": [
				{
					"id": "doc-1",
					"type": "document",
					"source": "notion",
					"score": 0.9,
					"preview": "preview",
					"debug": {"weighted_score": 0.9} if include_debug else None,
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


def test_chat_endpoint_debug_mode_returns_source_debug(monkeypatch):
	from api.routers import chat as chat_router

	fake_db = FakeChatDb()
	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = _override_user

	monkeypatch.setattr(
		chat_router.RAGEngine,
		"query",
		lambda self, query, top_k=8, type_filter=None, include_debug=False, conversation_history=None: {
			"answer": "Synthetic answer",
			"sources": [
				{
					"id": "doc-2",
					"type": "document",
					"source": "drive",
					"score": 0.88,
					"preview": "debug preview",
					"debug": {"total_score": 0.88} if include_debug else None,
				}
			],
			"documents": ["Plan"],
			"file_links": ["/users/u/data/drive/plan.json"],
		},
	)

	client = TestClient(app)
	response = client.post("/v1/chat/message?include_debug=true", json={"message": "show plan"})

	assert response.status_code == 200
	body = response.json()
	assert body["sources"][0]["debug"]["total_score"] == 0.88

	app.dependency_overrides.clear()

