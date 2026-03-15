import re
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from rag.engine import RAGEngine


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


def _build_fixture_rows():
	now = datetime.now(UTC)
	return [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="notion",
			title="Q2 roadmap",
			summary="Roadmap and milestones",
			content="Roadmap priorities and milestones for Q2",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="email",
			source="gmail",
			title="Invoice from vendor",
			summary="Invoice received",
			content="Please review the latest invoice",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="repository",
			source="github",
			title="Personal_API",
			summary="Backend and workers",
			content="Repository for personal API project",
			metadata_json={},
			item_date=now,
			file_path=None,
			embedding=None,
			created_at=now,
		),
	]


def _citation_indices(text: str) -> set[int]:
	indices: set[int] = set()
	for match in re.findall(r"\[(\d+)\]", text or ""):
		indices.add(int(match))
	return indices


def _citations_valid(answer: str, source_count: int) -> bool:
	indices = _citation_indices(answer)
	if not indices:
		return False
	return all(1 <= idx <= source_count for idx in indices)


def test_rag_quality_gate_retrieval_relevance_at_3():
	rows = _build_fixture_rows()
	db = FakeRetrieverDb(rows)
	engine = RAGEngine(db=db, user_id=uuid.uuid4(), use_llm=False)

	cases = [
		("show roadmap milestones", "notion"),
		("find invoice mail", "gmail"),
		("which github repository", "github"),
	]

	hits = 0
	for query, expected_source in cases:
		result = engine.query(query, top_k=3)
		sources = result.get("sources", [])
		if sources and sources[0].get("source") == expected_source:
			hits += 1

	relevance_at_3 = hits / float(len(cases))
	assert relevance_at_3 >= 0.66


def test_rag_quality_gate_abstain_precision_for_non_personal_queries():
	rows = _build_fixture_rows()
	db = FakeRetrieverDb(rows)
	engine = RAGEngine(db=db, user_id=uuid.uuid4(), use_llm=False)

	cases = [
		"what is the capital of france",
		"qwerty asdf zxcv unrelated",
	]

	correct = 0
	for query in cases:
		result = engine.query(query, top_k=3)
		mode = str(result.get("answer_mode", ""))
		if mode in {"out_of_scope", "abstain"}:
			correct += 1

	abstain_precision = correct / float(len(cases))
	assert abstain_precision >= 1.0


def test_rag_quality_gate_citation_validity_when_llm_mode_is_used():
	rows = _build_fixture_rows()
	db = FakeRetrieverDb(rows)

	class _CitationGenerator:
		def generate(self, query: str, context_text: str) -> str:
			return "Roadmap milestones for Q2 are captured in the summary [1]"

	engine = RAGEngine(db=db, user_id=uuid.uuid4(), use_llm=True, generator=_CitationGenerator())
	result = engine.query("show roadmap milestones", top_k=3)

	assert result.get("answer_mode") == "llm"
	answer = str(result.get("answer", ""))
	source_count = len(result.get("sources", []))
	assert _citations_valid(answer, source_count=source_count)
