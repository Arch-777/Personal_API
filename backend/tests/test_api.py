import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.core.auth import get_current_user
from api.core.db import get_db
from api.main import app
from api.models.user import User


class _FakeScalarResult:
	def __init__(self, rows):
		self._rows = rows

	def all(self):
		return self._rows


class _FakeResult:
	def __init__(self, rows=None, one=None):
		self._rows = rows or []
		self._one = one

	def scalars(self):
		return _FakeScalarResult(self._rows)

	def scalar_one_or_none(self):
		return self._one


class FakeDb:
	def __init__(self):
		self.items = []
		self.api_keys = []
		self.next_scalar = None
		self.next_rows = []
		self.next_one = None

	def scalar(self, _stmt):
		return self.next_scalar

	def execute(self, _stmt):
		return _FakeResult(rows=self.next_rows, one=self.next_one)

	def add(self, obj):
		if getattr(obj, "id", None) is None:
			obj.id = uuid.uuid4()
		if getattr(obj, "created_at", None) is None:
			obj.created_at = datetime.now(UTC)
		self.api_keys.append(obj)

	def commit(self):
		return None

	def refresh(self, _obj):
		return None


def _override_user() -> User:
	return SimpleNamespace(id=uuid.uuid4())


def _build_item(item_type: str, source: str) -> SimpleNamespace:
	now = datetime.now(UTC)
	return SimpleNamespace(
		id=uuid.uuid4(),
		type=item_type,
		source=source,
		source_id=f"{source}-1",
		title="Sample",
		sender_name="Sender",
		sender_email="sender@example.com",
		content="Example content",
		summary="Example summary",
		metadata_json={"k": "v"},
		item_date=now,
		file_path="/tmp/file.json",
		created_at=now,
		updated_at=now,
	)


def test_health_endpoint_returns_ok():
	client = TestClient(app)
	response = client.get("/health")

	assert response.status_code == 200
	assert response.json() == {"status": "ok"}


def test_llm_health_endpoint_returns_disabled_when_llm_is_off(monkeypatch):
	from api import main as api_main

	monkeypatch.setattr(
		api_main,
		"get_settings",
		lambda: SimpleNamespace(
			rag_llm_enabled=False,
			rag_llm_provider="ollama",
			rag_llm_base_url="http://127.0.0.1:11434",
			rag_llm_model="qwen2.5:1.5b",
			rag_llm_timeout_seconds=45,
		),
	)

	client = TestClient(app)
	response = client.get("/health/llm")

	assert response.status_code == 200
	assert response.json()["status"] == "disabled"


def test_llm_health_endpoint_returns_ok_when_ollama_is_ready(monkeypatch):
	from api import main as api_main

	monkeypatch.setattr(
		api_main,
		"get_settings",
		lambda: SimpleNamespace(
			rag_llm_enabled=True,
			rag_llm_provider="ollama",
			rag_llm_base_url="http://127.0.0.1:11434",
			rag_llm_model="qwen2.5:1.5b",
			rag_llm_timeout_seconds=45,
		),
	)
	monkeypatch.setattr(api_main, "check_ollama_readiness", lambda base_url, timeout_seconds=3: (True, "ok"))

	client = TestClient(app)
	response = client.get("/health/llm")

	assert response.status_code == 200
	assert response.json()["status"] == "ok"
	assert response.json()["model"] == "qwen2.5:1.5b"


def test_llm_health_endpoint_returns_503_when_ollama_is_unreachable(monkeypatch):
	from api import main as api_main

	monkeypatch.setattr(
		api_main,
		"get_settings",
		lambda: SimpleNamespace(
			rag_llm_enabled=True,
			rag_llm_provider="ollama",
			rag_llm_base_url="http://10.0.0.5:11434",
			rag_llm_model="qwen2.5:1.5b",
			rag_llm_timeout_seconds=45,
		),
	)
	monkeypatch.setattr(api_main, "check_ollama_readiness", lambda base_url, timeout_seconds=3: (False, "connection refused"))

	client = TestClient(app)
	response = client.get("/health/llm")

	assert response.status_code == 503
	assert response.json()["status"] == "unreachable"


def test_emails_endpoint_returns_paginated_items():
	fake_db = FakeDb()
	fake_db.next_scalar = 1
	fake_db.next_rows = [_build_item("email", "gmail")]

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = _override_user

	client = TestClient(app)
	response = client.get("/v1/emails/?limit=10&offset=0")

	assert response.status_code == 200
	body = response.json()
	assert body["total"] == 1
	assert body["limit"] == 10
	assert len(body["items"]) == 1
	assert body["items"][0]["type"] == "email"

	app.dependency_overrides.clear()


def test_documents_endpoint_returns_paginated_items():
	fake_db = FakeDb()
	fake_db.next_scalar = 1
	fake_db.next_rows = [_build_item("document", "drive")]

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = _override_user

	client = TestClient(app)
	response = client.get("/v1/documents/?limit=10&offset=0")

	assert response.status_code == 200
	body = response.json()
	assert body["total"] == 1
	assert body["items"][0]["source"] == "drive"

	app.dependency_overrides.clear()


def test_developer_create_and_list_api_keys():
	fake_db = FakeDb()
	created = SimpleNamespace(
		id=uuid.uuid4(),
		name="local key",
		key_prefix="pk_live_123456",
		allowed_channels=["telegram"],
		agent_type="openclaw",
		created_at=datetime.now(UTC),
		last_used_at=None,
		expires_at=None,
		revoked_at=None,
	)
	fake_db.next_rows = [created]

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = _override_user

	client = TestClient(app)
	create_resp = client.post(
		"/v1/developer/api-keys",
		json={"name": "local key", "allowed_channels": ["telegram"], "agent_type": "openclaw"},
	)
	assert create_resp.status_code == 201
	assert create_resp.json()["api_key"].startswith("pk_live_")

	list_resp = client.get("/v1/developer/api-keys")
	assert list_resp.status_code == 200
	assert len(list_resp.json()) >= 1

	app.dependency_overrides.clear()


def test_developer_revoke_api_key_success():
	fake_db = FakeDb()
	key_id = uuid.uuid4()
	record = SimpleNamespace(
		id=key_id,
		name="revokable",
		key_prefix="pk_live_123456",
		allowed_channels=[],
		agent_type=None,
		created_at=datetime.now(UTC),
		last_used_at=None,
		expires_at=None,
		revoked_at=None,
	)
	fake_db.next_one = record

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = _override_user

	client = TestClient(app)
	resp = client.post(f"/v1/developer/api-keys/{key_id}/revoke")

	assert resp.status_code == 200
	assert resp.json()["revoked_at"] is not None

	app.dependency_overrides.clear()



@pytest.mark.parametrize(
	"platform,task_name",
	[
		("gmail", "workers.google_worker.sync_gmail"),
		("drive", "workers.google_worker.sync_drive"),
		("gcal", "workers.google_worker.sync_gcal"),
	],
)
def test_connector_sync_queues_expected_worker_task(platform: str, task_name: str):
	from unittest.mock import patch
	from api.routers import connectors as connectors_router

	class _FakeConnectorResult:
		def __init__(self, one):
			self._one = one

		def scalar_one_or_none(self):
			return self._one

	class _FakeConnectorDb:
		def __init__(self, connector):
			self.connector = connector
			self.committed = False

		def execute(self, _stmt):
			return _FakeConnectorResult(one=self.connector)

		def commit(self):
			self.committed = True

	connector = SimpleNamespace(
		id=uuid.uuid4(),
		user_id=uuid.uuid4(),
		platform=platform,
		sync_cursor="0",
		status="connected",
		error_message=None,
	)
	fake_db = _FakeConnectorDb(connector)
	current_user = SimpleNamespace(id=connector.user_id)

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = lambda: current_user

	with patch.object(
		connectors_router,
		"get_settings",
		return_value=SimpleNamespace(debug=False, enable_inline_sync_fallback=False),
	):
		with patch.object(connectors_router.celery_app, "send_task", return_value=SimpleNamespace(id="task-1")) as send_task:
			client = TestClient(app)
			response = client.post(f"/v1/connectors/{platform}/sync")

			assert response.status_code == 202
			assert response.json() == {"status": "sync_queued", "platform": platform}
			assert fake_db.committed is True
			assert connector.status == "connected"
			assert connector.error_message is None

			send_task.assert_called_once()
			called_task_name = send_task.call_args.args[0]
			called_args = send_task.call_args.kwargs["args"]
			assert called_task_name == task_name
			assert called_args[0] == str(connector.id)
			assert called_args[1] == str(current_user.id)
			assert called_args[2] == "0"

	app.dependency_overrides.clear()


def test_slack_connect_returns_authorize_url():
	from unittest.mock import patch
	from api.routers import connectors as connectors_router

	app.dependency_overrides[get_current_user] = _override_user

	with patch.object(
		connectors_router,
		"get_settings",
		return_value=SimpleNamespace(
			slack_client_id="client-id",
			slack_client_secret="client-secret",
			slack_redirect_uri="http://127.0.0.1:8000/v1/connectors/slack/callback",
		),
	):
		client = TestClient(app)
		response = client.get("/v1/connectors/slack/connect")

	assert response.status_code == 200
	body = response.json()
	assert body["url"].startswith("https://slack.com/oauth/v2/authorize?")
	assert "client_id=client-id" in body["url"]
	assert "state=" in body["url"]

	app.dependency_overrides.clear()
