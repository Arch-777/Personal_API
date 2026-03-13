import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.core.auth import get_current_user
from api.core.db import get_db
from api.main import app
from api.models.user import User


class _FakeSearchResult:
	def __init__(self, rows):
		self._rows = rows

	def all(self):
		return self._rows


class FakeSearchDb:
	def __init__(self, rows):
		self.rows = rows

	def execute(self, _stmt):
		return _FakeSearchResult(self.rows)


def _override_user() -> User:
	return SimpleNamespace(id=uuid.uuid4())


def test_search_returns_ranked_results():
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="drive",
			summary="Meeting notes summary",
			content="Meeting notes content",
			metadata={"doc": "1"},
			item_date=datetime.now(UTC),
			score=0.82,
		),
		SimpleNamespace(
			id=uuid.uuid4(),
			type="email",
			source="gmail",
			summary="",
			content="Email body",
			metadata={"mail": "2"},
			item_date=datetime.now(UTC),
			score=0.51,
		),
	]

	app.dependency_overrides[get_db] = lambda: FakeSearchDb(rows)
	app.dependency_overrides[get_current_user] = _override_user

	client = TestClient(app)
	response = client.get("/v1/search/?q=meeting&top_k=5")

	assert response.status_code == 200
	body = response.json()
	assert body["query"] == "meeting"
	assert body["count"] == 2
	assert body["results"][0]["source"] == "drive"
	assert isinstance(body["results"][0]["score"], float)

	app.dependency_overrides.clear()


def test_search_respects_top_k_limit():
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="note",
			source="notion",
			summary="alpha",
			content="alpha content",
			metadata={},
			item_date=datetime.now(UTC),
			score=0.9,
		)
	]

	app.dependency_overrides[get_db] = lambda: FakeSearchDb(rows)
	app.dependency_overrides[get_current_user] = _override_user

	client = TestClient(app)
	response = client.get("/v1/search/?q=alpha&top_k=1&type_filter=note")

	assert response.status_code == 200
	body = response.json()
	assert body["count"] == 1
	assert body["results"][0]["type"] == "note"

	app.dependency_overrides.clear()


def test_search_include_debug_returns_similarity_breakdown():
	rows = [
		SimpleNamespace(
			id=uuid.uuid4(),
			type="document",
			source="drive",
			summary="Meeting notes summary",
			content="Meeting notes content",
			metadata={"doc": "1"},
			item_date=datetime.now(UTC),
			score=0.82,
			title_similarity=0.4,
			content_similarity=0.22,
		)
	]

	app.dependency_overrides[get_db] = lambda: FakeSearchDb(rows)
	app.dependency_overrides[get_current_user] = _override_user

	client = TestClient(app)
	response = client.get("/v1/search/?q=meeting&top_k=5&include_debug=true")

	assert response.status_code == 200
	body = response.json()
	assert body["count"] == 1
	assert body["results"][0]["debug"]["title_similarity"] == 0.4
	assert body["results"][0]["debug"]["content_similarity"] == 0.22

	app.dependency_overrides.clear()

