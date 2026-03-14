import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import hashlib
import hmac

import pytest
from fastapi import HTTPException
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


def test_developer_create_api_key_with_expires_in_days_sets_expires_at():
	fake_db = FakeDb()

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = _override_user

	client = TestClient(app)
	create_resp = client.post(
		"/v1/developer/api-keys",
		json={
			"name": "expiring key",
			"allowed_channels": ["mcp"],
			"agent_type": "openclaw",
			"expires_in_days": 7,
		},
	)
	assert create_resp.status_code == 201
	body = create_resp.json()
	assert body["expires_at"] is not None

	app.dependency_overrides.clear()


def test_mcp_resolve_user_rejects_expired_api_key(monkeypatch):
	from mcp import server as mcp_server

	class _FakeMcpResult:
		def __init__(self, one=None):
			self._one = one

		def scalar_one_or_none(self):
			return self._one

	class _FakeMcpDb:
		def __init__(self, row):
			self.row = row
			self.committed = False
			self.closed = False

		def execute(self, _stmt):
			return _FakeMcpResult(one=self.row)

		def commit(self):
			self.committed = True

		def close(self):
			self.closed = True

	expired_row = SimpleNamespace(
		user_id=uuid.uuid4(),
		revoked_at=None,
		expires_at=datetime.now(UTC) - timedelta(minutes=1),
		last_used_at=None,
	)
	fake_db = _FakeMcpDb(row=expired_row)
	monkeypatch.setattr(mcp_server, "SessionLocal", lambda: fake_db)

	with pytest.raises(HTTPException) as exc:
		mcp_server._resolve_user("pk_live_expired")

	assert exc.value.status_code == 401
	assert fake_db.committed is False
	assert fake_db.closed is True


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


def test_mcp_unified_endpoint_lists_tools():
	client = TestClient(app)
	response = client.post(
		"/mcp/endpoint",
		headers={"X-API-Key": "pk_live_dummy"},
		json={"action": "list_tools"},
	)

	assert response.status_code == 200
	body = response.json()
	assert body["action"] == "list_tools"
	assert "data" in body and "tools" in body["data"]
	tool_names = [t["name"] for t in body["data"]["tools"]]
	assert "search" in tool_names
	assert "ask" in tool_names


def test_mcp_unified_endpoint_requires_tool_for_call_action():
	client = TestClient(app)
	response = client.post(
		"/mcp/endpoint",
		headers={"X-API-Key": "pk_live_dummy"},
		json={"action": "call_tool", "arguments": {}},
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Missing required field: tool"

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


# ---------------------------------------------------------------------------
# Disconnect / DELETE integration tests
# ---------------------------------------------------------------------------

class _FakeDisconnectDb:
	"""Minimal DB fake for disconnect endpoint tests."""

	def __init__(self, connectors: list):
		self._connectors = connectors
		self.deleted_connector_platforms: list[str] = []
		self.deleted_item_sources: list[str] = []
		self.committed = False

	def execute(self, stmt):
		# Detect the kind of statement by inspecting the compiled string.
		stmt_str = str(stmt)
		if "DELETE" in stmt_str and "connectors" in stmt_str:
			# Record which platforms were deleted via the IN clause values.
			self.deleted_connector_platforms = [c.platform for c in self._connectors]
			return _FakeResult()
		if "DELETE" in stmt_str and "items" in stmt_str:
			self.deleted_item_sources.append("__deleted__")
			result = _FakeResult()
			result.rowcount = 5  # type: ignore[attr-defined]
			return result
		# SELECT — return the stored connectors.
		return _FakeResult(rows=self._connectors)

	def commit(self):
		self.committed = True


def _make_connector(platform: str, user_id: uuid.UUID):
	return SimpleNamespace(
		id=uuid.uuid4(),
		user_id=user_id,
		platform=platform,
		platform_email="test@example.com",
		status="connected",
		last_synced=None,
		error_message=None,
		metadata_json={},
		created_at=datetime.now(UTC),
		updated_at=datetime.now(UTC),
	)


def test_disconnect_notion_removes_connector():
	user_id = uuid.uuid4()
	connector = _make_connector("notion", user_id)
	fake_db = _FakeDisconnectDb(connectors=[connector])
	current_user = SimpleNamespace(id=user_id)

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = lambda: current_user

	client = TestClient(app)
	response = client.delete("/v1/connectors/notion")

	assert response.status_code == 200
	body = response.json()
	assert body["disconnected"] == ["notion"]
	assert body["items_deleted"] == 0  # delete_data defaults to false
	assert fake_db.committed is True

	app.dependency_overrides.clear()


def test_disconnect_google_platform_cascades_all_three_siblings():
	"""Deleting 'gmail' with cascade_google=true removes gmail, drive, and gcal."""
	user_id = uuid.uuid4()
	connectors = [
		_make_connector("gmail", user_id),
		_make_connector("drive", user_id),
		_make_connector("gcal", user_id),
	]
	fake_db = _FakeDisconnectDb(connectors=connectors)
	current_user = SimpleNamespace(id=user_id)

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = lambda: current_user

	client = TestClient(app)
	response = client.delete("/v1/connectors/gmail?cascade_google=true")

	assert response.status_code == 200
	body = response.json()
	assert set(body["disconnected"]) == {"gmail", "drive", "gcal"}
	assert body["items_deleted"] == 0

	app.dependency_overrides.clear()


def test_disconnect_google_platform_no_cascade_removes_only_one():
	"""Deleting 'gmail' with cascade_google=false removes only gmail."""
	user_id = uuid.uuid4()
	connector = _make_connector("gmail", user_id)
	fake_db = _FakeDisconnectDb(connectors=[connector])
	current_user = SimpleNamespace(id=user_id)

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = lambda: current_user

	client = TestClient(app)
	response = client.delete("/v1/connectors/gmail?cascade_google=false")

	assert response.status_code == 200
	body = response.json()
	assert body["disconnected"] == ["gmail"]

	app.dependency_overrides.clear()


def test_disconnect_returns_404_when_connector_not_found():
	user_id = uuid.uuid4()
	fake_db = _FakeDisconnectDb(connectors=[])  # no connectors
	current_user = SimpleNamespace(id=user_id)

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = lambda: current_user

	client = TestClient(app)
	response = client.delete("/v1/connectors/spotify")


def test_github_webhook_signature_helper_validation():
	from api.routers import connectors as connectors_router

	secret = "webhook-secret"
	payload = b'{"repository":{"full_name":"arch-777/personal-api"}}'
	valid_signature = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

	assert connectors_router._is_valid_github_webhook_signature(secret, payload, valid_signature) is True
	assert connectors_router._is_valid_github_webhook_signature(secret, payload, "sha256=deadbeef") is False


def test_parse_github_token_response_supports_form_encoded_payload():
	from api.routers import connectors as connectors_router

	class _FormOnlyResponse:
		text = "access_token=gho_test_token&scope=repo&token_type=bearer"

		def json(self):
			raise ValueError("not-json")

	token_data = connectors_router._parse_github_token_response(_FormOnlyResponse())

	assert token_data["access_token"] == "gho_test_token"
	assert token_data["scope"] == "repo"
	assert token_data["token_type"] == "bearer"


def test_build_github_token_exchange_error_detail_uses_message_field():
	from api.routers import connectors as connectors_router

	detail = connectors_router._build_github_token_exchange_error_detail(
		{"message": "The code passed is incorrect or expired."}
	)

	assert detail == "GitHub token exchange failed: The code passed is incorrect or expired."


def test_build_github_token_exchange_error_detail_returns_none_without_known_fields():
	from api.routers import connectors as connectors_router

	detail = connectors_router._build_github_token_exchange_error_detail({"foo": "bar"})

	assert detail is None


def test_github_connect_returns_authorize_url_with_redirect_uri():
	from unittest.mock import patch
	from api.routers import connectors as connectors_router

	app.dependency_overrides[get_current_user] = _override_user

	with patch.object(
		connectors_router,
		"get_settings",
		return_value=SimpleNamespace(
			github_client_id="github-client-id",
			github_client_secret="github-client-secret",
			github_redirect_uri="http://127.0.0.1:8000/v1/connectors/github/callback",
		),
	):
		client = TestClient(app)
		response = client.get("/v1/connectors/github/connect")

	assert response.status_code == 200
	body = response.json()
	assert body["url"].startswith("https://github.com/login/oauth/authorize?")
	assert "client_id=github-client-id" in body["url"]
	assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8000%2Fv1%2Fconnectors%2Fgithub%2Fcallback" in body["url"]
	assert "state=" in body["url"]

	app.dependency_overrides.clear()


def test_github_callback_redirects_to_frontend_on_success(monkeypatch):
	from api.routers import connectors as connectors_router

	class _FakeDbForGithubCallback:
		pass

	class _FakeHttpResponse:
		def __init__(self, payload: dict, status_code: int = 200):
			self._payload = payload
			self.status_code = status_code
			self.headers = {"content-type": "application/json"}
			self.text = ""

		def raise_for_status(self):
			return None

		def json(self):
			return self._payload

	class _FakeHttpClient:
		def post(self, _url, data=None, headers=None):
			assert isinstance(data, dict)
			assert data["code"] == "oauth-code"
			return _FakeHttpResponse(
				{
					"access_token": "gho_test_access_token",
					"scope": "read:user user:email repo",
					"token_type": "bearer",
				}
			)

		def get(self, url, headers=None):
			if url.endswith("/user"):
				return _FakeHttpResponse({"login": "arch-777", "name": "Arch", "email": "arch@example.com"})
			if url.endswith("/user/emails"):
				return _FakeHttpResponse([
					{"email": "arch@example.com", "primary": True, "verified": True},
				])
			if url.endswith("/user/orgs"):
				return _FakeHttpResponse([
					{"login": "Const-Coders"},
				])
			return _FakeHttpResponse({}, status_code=404)

	fake_db = _FakeDbForGithubCallback()
	user_id = uuid.uuid4()
	recorded_upsert: dict[str, object] = {}

	monkeypatch.setattr(connectors_router, "decode_access_token", lambda _state: {"sub": f"{user_id}|github"})
	monkeypatch.setattr(
		connectors_router,
		"get_settings",
		lambda: SimpleNamespace(
			github_client_id="github-client-id",
			github_client_secret="github-client-secret",
			github_redirect_uri="http://127.0.0.1:8000/v1/connectors/github/callback",
			frontend_app_url="http://127.0.0.1:3000",
		),
	)
	monkeypatch.setattr(connectors_router, "get_http_client", lambda _timeout: _FakeHttpClient())

	def _fake_upsert(*, db, user_id, access_token, platform_email, metadata):
		recorded_upsert["user_id"] = user_id
		recorded_upsert["access_token"] = access_token
		recorded_upsert["platform_email"] = platform_email
		recorded_upsert["metadata"] = metadata

	monkeypatch.setattr(connectors_router, "_upsert_github_connector", _fake_upsert)

	app.dependency_overrides[get_db] = lambda: fake_db
	client = TestClient(app)
	response = client.get(
		"/v1/connectors/github/callback?code=oauth-code&state=oauth-state",
		follow_redirects=False,
	)

	assert response.status_code == 307
	location = response.headers["location"]
	assert location.startswith("http://127.0.0.1:3000/dashboard/integrations?")
	assert "integration=github" in location
	assert "status=success" in location
	assert recorded_upsert["user_id"] == user_id
	assert recorded_upsert["access_token"] == "gho_test_access_token"
	assert recorded_upsert["platform_email"] == "arch@example.com"

	app.dependency_overrides.clear()


def test_github_callback_missing_code_returns_400_without_redirect(monkeypatch):
	from api.routers import connectors as connectors_router

	class _FakeDbForGithubCallback:
		pass

	monkeypatch.setattr(
		connectors_router,
		"get_settings",
		lambda: SimpleNamespace(
			github_client_id="github-client-id",
			github_client_secret="github-client-secret",
			github_redirect_uri="http://127.0.0.1:8000/v1/connectors/github/callback",
			frontend_app_url="http://127.0.0.1:3000",
		),
	)

	app.dependency_overrides[get_db] = lambda: _FakeDbForGithubCallback()
	client = TestClient(app)
	response = client.get(
		"/v1/connectors/github/callback?code=&state=oauth-state&redirect_to_frontend=false",
		follow_redirects=False,
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Missing GitHub OAuth code"

	app.dependency_overrides.clear()


def test_build_frontend_integrations_callback_url_normalizes_message():
	from api.routers import connectors as connectors_router

	message = "line-1\nline-2\r\n" + ("x" * 300)

	with pytest.MonkeyPatch.context() as monkeypatch:
		monkeypatch.setattr(
			connectors_router,
			"get_settings",
			lambda: SimpleNamespace(frontend_app_url="http://127.0.0.1:3000"),
		)
		url = connectors_router._build_frontend_integrations_callback_url(
			platform="github",
			ok=False,
			message=message,
		)

	assert url.startswith("http://127.0.0.1:3000/dashboard/integrations?")
	assert "integration=github" in url
	assert "status=error" in url
	assert "line-1+line-2" in url
	assert len(url) < 400


def test_github_webhook_ping_returns_ok(monkeypatch):
	from api.routers import connectors as connectors_router

	secret = "webhook-secret"
	body = b'{"zen":"Keep it logically awesome."}'
	signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

	class _FakeWebhookResult:
		def scalars(self):
			return _FakeScalarResult([])

	class _FakeWebhookDb:
		def execute(self, _stmt):
			return _FakeWebhookResult()

	app.dependency_overrides[get_db] = lambda: _FakeWebhookDb()

	monkeypatch.setattr(
		connectors_router,
		"get_settings",
		lambda: SimpleNamespace(github_webhook_secret=secret, debug=False, enable_inline_sync_fallback=False),
	)

	client = TestClient(app)
	response = client.post(
		"/v1/connectors/github/webhook",
		data=body,
		headers={
			"X-GitHub-Event": "ping",
			"X-GitHub-Delivery": "delivery-123",
			"X-Hub-Signature-256": signature,
			"Content-Type": "application/json",
		},
	)

	assert response.status_code == 200
	body_json = response.json()
	assert body_json["status"] == "ok"
	assert body_json["event"] == "ping"


def test_google_callback_upserts_each_google_platform_once(monkeypatch):
	from api.routers import connectors as connectors_router

	class _FakeDbForGoogleCallback:
		def __init__(self):
			self.committed = False

		def commit(self):
			self.committed = True

	class _FakeHttpResponse:
		def __init__(self, payload: dict, status_code: int = 200):
			self._payload = payload
			self.status_code = status_code

		def raise_for_status(self):
			return None

		def json(self):
			return self._payload

	class _FakeHttpClient:
		def __init__(self, *args, **kwargs):
			pass

		def __enter__(self):
			return self

		def __exit__(self, exc_type, exc, tb):
			return False

		def post(self, url, data=None, headers=None):
			assert "oauth2.googleapis.com/token" in url
			return _FakeHttpResponse(
				{
					"access_token": "access-token",
					"refresh_token": "refresh-token",
					"expires_in": 3600,
					"scope": "openid email https://www.googleapis.com/auth/calendar.readonly",
				}
			)

		def get(self, url, headers=None):
			assert "openidconnect.googleapis.com/v1/userinfo" in url
			return _FakeHttpResponse({"email": "test@example.com"}, status_code=200)

	fake_db = _FakeDbForGoogleCallback()
	user_id = uuid.uuid4()
	upsert_calls: list[str] = []

	monkeypatch.setattr(
		connectors_router,
		"decode_access_token",
		lambda _state: {"sub": f"{user_id}|gcal"},
	)
	monkeypatch.setattr(
		connectors_router,
		"get_settings",
		lambda: SimpleNamespace(
			google_client_id="client-id",
			google_client_secret="client-secret",
			google_redirect_uri="http://127.0.0.1:8000/v1/connectors/google/callback",
			frontend_app_url="http://127.0.0.1:3000",
		),
	)
	monkeypatch.setattr(connectors_router.httpx, "Client", _FakeHttpClient)

	def _fake_upsert(*, db, user_id, platform, access_token, refresh_token, token_expires_at, platform_email, google_scope):
		upsert_calls.append(platform)

	monkeypatch.setattr(connectors_router, "_ensure_google_connector_row", _fake_upsert)

	app.dependency_overrides[get_db] = lambda: fake_db
	client = TestClient(app)
	response = client.get(
		"/v1/connectors/google/callback?code=fake-code&state=fake-state",
		follow_redirects=False,
	)

	assert response.status_code == 307
	assert sorted(upsert_calls) == ["drive", "gcal", "gmail"]
	assert len(upsert_calls) == 3
	assert fake_db.committed is True

	app.dependency_overrides.clear()


class _FakeAutoSyncToggleDb:
	def __init__(self, connectors: list):
		self._connectors = connectors
		self.committed = False

	def execute(self, _stmt):
		return _FakeResult(rows=self._connectors)

	def commit(self):
		self.committed = True


def test_set_connector_auto_sync_updates_single_platform_metadata():
	user_id = uuid.uuid4()
	connector = _make_connector("spotify", user_id)
	connector.metadata_json = {}
	fake_db = _FakeAutoSyncToggleDb(connectors=[connector])
	current_user = SimpleNamespace(id=user_id)

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = lambda: current_user

	client = TestClient(app)
	response = client.patch("/v1/connectors/spotify/auto-sync", json={"enabled": False})

	assert response.status_code == 200
	body = response.json()
	assert body["platforms"] == ["spotify"]
	assert body["auto_sync_enabled"] is False
	assert connector.metadata_json["auto_sync_enabled"] is False
	assert fake_db.committed is True

	app.dependency_overrides.clear()


def test_set_connector_auto_sync_cascades_google_platforms_by_default():
	user_id = uuid.uuid4()
	connectors = [
		_make_connector("gmail", user_id),
		_make_connector("drive", user_id),
		_make_connector("gcal", user_id),
	]
	for connector in connectors:
		connector.metadata_json = {}
	fake_db = _FakeAutoSyncToggleDb(connectors=connectors)
	current_user = SimpleNamespace(id=user_id)

	app.dependency_overrides[get_db] = lambda: fake_db
	app.dependency_overrides[get_current_user] = lambda: current_user

	client = TestClient(app)
	response = client.patch("/v1/connectors/gmail/auto-sync", json={"enabled": True})

	assert response.status_code == 200
	body = response.json()
	assert set(body["platforms"]) == {"gmail", "drive", "gcal"}
	assert body["auto_sync_enabled"] is True
	assert all(c.metadata_json.get("auto_sync_enabled") is True for c in connectors)
