import time
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from rag.retriever import HybridRetriever


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


def test_hybrid_retriever_latency_budget_synthetic_corpus():
	now = datetime.now(UTC)
	rows = []
	for i in range(600):
		rows.append(
			SimpleNamespace(
				id=uuid.uuid4(),
				type="document" if i % 3 else "email",
				source="drive" if i % 2 else "gmail",
				title=f"Doc {i} quarterly roadmap and planning",
				summary="This is a generated summary for benchmark testing",
				content="Quarterly roadmap milestones, owners, meeting notes, and operational updates",
				metadata_json={},
				item_date=now - timedelta(days=i % 120),
				file_path=None,
				embedding=None,
				created_at=now,
			)
		)

	db = FakeRetrieverDb(rows)
	retriever = HybridRetriever(db)

	start = time.perf_counter()
	results = retriever.retrieve(user_id=uuid.uuid4(), query="quarterly roadmap meeting notes", top_k=8)
	elapsed = time.perf_counter() - start

	assert len(results) > 0
	# Keep this threshold conservative for CI variability while still guarding regressions.
	assert elapsed < 2.0
