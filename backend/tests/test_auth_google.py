import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.core.db import get_db
from api.main import app


class _FakeResult:
	def __init__(self, one=None):
		self._one = one

	def scalar_one_or_none(self):
		return self._one


class FakeDb:
	def __init__(self):
		self.user = None

	def execute(self, _stmt):
		return _FakeResult(one=self.user)

	def add(self, obj):
		if getattr(obj, "id", None) is None:
			obj.id = uuid.uuid4()
		if getattr(obj, "created_at", None) is None:
			obj.created_at = datetime.now(UTC)
		self.user = obj

	def commit(self):
		return None

	def refresh(self, _obj):
		return None


def test_google_login_creates_user_and_returns_token(monkeypatch):
	fake_db = FakeDb()

	def _verify(_token: str):
		return {"email": "new.user@example.com", "name": "New User"}

	monkeypatch.setattr("api.routers.auth.verify_google_id_token", _verify)
	app.dependency_overrides[get_db] = lambda: fake_db

	client = TestClient(app)
	response = client.post("/auth/google", json={"id_token": "x" * 30})

	assert response.status_code == 200
	body = response.json()
	assert body["token_type"] == "bearer"
	assert body["access_token"]
	assert fake_db.user is not None
	assert fake_db.user.email == "new.user@example.com"
	assert fake_db.user.full_name == "New User"

	app.dependency_overrides.clear()


def test_google_login_rejects_invalid_token(monkeypatch):
	fake_db = FakeDb()

	def _verify(_token: str):
		raise ValueError("Invalid Google ID token")

	monkeypatch.setattr("api.routers.auth.verify_google_id_token", _verify)
	app.dependency_overrides[get_db] = lambda: fake_db

	client = TestClient(app)
	response = client.post("/auth/google", json={"id_token": "x" * 30})

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid Google ID token"

	app.dependency_overrides.clear()


def test_google_login_returns_existing_user_token(monkeypatch):
	fake_db = FakeDb()
	fake_db.user = SimpleNamespace(
		id=uuid.uuid4(),
		email="existing@example.com",
		full_name="Existing User",
		hashed_password="hash",
		created_at=datetime.now(UTC),
	)

	def _verify(_token: str):
		return {"email": "existing@example.com", "name": "Existing User"}

	monkeypatch.setattr("api.routers.auth.verify_google_id_token", _verify)
	app.dependency_overrides[get_db] = lambda: fake_db

	client = TestClient(app)
	response = client.post("/auth/google", json={"id_token": "x" * 30})

	assert response.status_code == 200
	body = response.json()
	assert body["token_type"] == "bearer"
	assert body["access_token"]

	app.dependency_overrides.clear()
