"""
Live integration tests against the hosted backend.
Run with:  python -m pytest tests/test_live_backend.py -v -s

Uses BASE_URL env-var (default: https://api.personalapi.tech).
Each test registers a unique throwaway user so the suite is repeatable.
"""
from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

BASE_URL = os.getenv("BASE_URL", "https://api.personalapi.tech").rstrip("/")

# Unique test-run suffix so re-runs do not collide with existing users
_RUN_ID = uuid.uuid4().hex[:8]
TEST_EMAIL = f"live_test_{_RUN_ID}@qa.personalapi.tech"
TEST_PASSWORD = "LiveTest#2026!"
TEST_FULL_NAME = "Live QA Bot"

client = httpx.Client(base_url=BASE_URL, timeout=30.0)

# Shared state populated by auth tests and used by later tests
_state: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers() -> dict[str, str]:
    token = _state.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _dev_key_headers() -> dict[str, str]:
    key = _state.get("dev_key", "")
    return {"X-API-Key": key}


# ============================================================
# 1. Platform / health
# ============================================================

class TestPlatform:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "ok"

    def test_mcp_health(self):
        r = client.get("/mcp/health")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "ok"
        assert body.get("service") == "mcp"


# ============================================================
# 2. Auth
# ============================================================

class TestAuth:
    def test_register(self):
        r = client.post("/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_FULL_NAME,
        })
        assert r.status_code in (201, 409), r.text
        if r.status_code == 201:
            body = r.json()
            assert body["email"] == TEST_EMAIL

    def test_login_and_capture_token(self):
        r = client.post("/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        _state["access_token"] = body["access_token"]

    def test_login_wrong_password_returns_401(self):
        r = client.post("/auth/login", json={
            "email": TEST_EMAIL,
            "password": "WrongPassword999!",
        })
        assert r.status_code == 401, r.text

    def test_me(self):
        r = client.get("/auth/me", headers=_auth_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == TEST_EMAIL
        assert "id" in body

    def test_me_no_token_returns_401(self):
        r = client.get("/auth/me")
        assert r.status_code == 401, r.text

    def test_google_connect_url_shape(self):
        r = client.get("/auth/google/connect")
        assert r.status_code in (200, 503), r.text
        if r.status_code == 200:
            assert "url" in r.json()


# ============================================================
# 3. Emails / Documents (empty but valid)
# ============================================================

class TestContent:
    def test_emails_paginated(self):
        r = client.get("/v1/emails/?limit=5&offset=0", headers=_auth_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body
        assert isinstance(body["items"], list)

    def test_documents_paginated(self):
        r = client.get("/v1/documents/?limit=5&offset=0", headers=_auth_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_emails_invalid_token_returns_401(self):
        r = client.get("/v1/emails/", headers={"Authorization": "Bearer bad.token.here"})
        assert r.status_code == 401, r.text


# ============================================================
# 4. Search
# ============================================================

class TestSearch:
    def test_search_returns_contract(self):
        r = client.get("/v1/search/?q=meeting+notes&top_k=5", headers=_auth_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert "query" in body
        assert "results" in body
        assert "count" in body
        assert isinstance(body["results"], list)

    def test_search_with_type_filter(self):
        r = client.get("/v1/search/?q=test&top_k=5&type_filter=email", headers=_auth_headers())
        assert r.status_code == 200, r.text

    def test_search_empty_query_422(self):
        r = client.get("/v1/search/?q=", headers=_auth_headers())
        assert r.status_code == 422, r.text

    def test_search_no_auth_401(self):
        r = client.get("/v1/search/?q=test")
        assert r.status_code == 401, r.text


# ============================================================
# 5. Connectors
# ============================================================

class TestConnectors:
    def test_list_connectors_returns_array(self):
        r = client.get("/v1/connectors/", headers=_auth_headers())
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_get_connector_not_found_404(self):
        r = client.get("/v1/connectors/gmail", headers=_auth_headers())
        assert r.status_code == 404, r.text

    def test_google_connect_url(self):
        r = client.get("/v1/connectors/google/connect?platform=gmail", headers=_auth_headers())
        assert r.status_code in (200, 503), r.text
        if r.status_code == 200:
            body = r.json()
            assert "url" in body

    def test_slack_connect_url(self):
        r = client.get("/v1/connectors/slack/connect", headers=_auth_headers())
        assert r.status_code in (200, 503), r.text

    def test_notion_connect_url(self):
        r = client.get("/v1/connectors/notion/connect", headers=_auth_headers())
        assert r.status_code in (200, 503), r.text

    def test_spotify_connect_url(self):
        r = client.get("/v1/connectors/spotify/connect", headers=_auth_headers())
        assert r.status_code in (200, 503), r.text

    def test_sync_without_connector_422_or_404(self):
        r = client.post("/v1/connectors/gmail/sync", headers=_auth_headers())
        assert r.status_code in (404, 422, 400), r.text

    def test_bootstrap_creates_connector(self):
        r = client.post(
            "/v1/connectors/gmail/bootstrap",
            headers=_auth_headers(),
            json={
                "access_token": "dummy_token",
                "metadata_json": {
                    "sample_records": [
                        {
                            "id": f"msg_{_RUN_ID}",
                            "payload": {
                                "headers": [
                                    {"name": "Subject", "value": "Live Test Email"},
                                    {"name": "From", "value": "sender@example.com"},
                                    {"name": "Date", "value": "Sat, 14 Mar 2026 10:00:00 +0000"},
                                ]
                            },
                            "snippet": "This is a live integration test email snippet",
                        }
                    ],
                    "sample_next_cursor": "cursor_001",
                },
            },
        )
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body["platform"] == "gmail"
        _state["gmail_connector"] = body

    def test_get_bootstrapped_connector(self):
        if "gmail_connector" not in _state:
            pytest.skip("Bootstrap did not run")
        r = client.get("/v1/connectors/gmail", headers=_auth_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["platform"] == "gmail"

    def test_trigger_sync_after_bootstrap(self):
        if "gmail_connector" not in _state:
            pytest.skip("Bootstrap did not run")
        r = client.post("/v1/connectors/gmail/sync", headers=_auth_headers())
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["status"] == "sync_queued"
        assert body["platform"] == "gmail"


# ============================================================
# 6. Chat / RAG
# ============================================================

class TestChat:
    def test_chat_message_starts_session(self):
        r = client.post(
            "/v1/chat/message",
            headers=_auth_headers(),
            json={"message": "What emails do I have?", "session_id": None},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "session_id" in body
        assert "answer" in body
        assert isinstance(body["answer"], str)
        assert len(body["answer"]) > 0
        assert "sources" in body
        _state["chat_session_id"] = body["session_id"]

    def test_chat_continues_session(self):
        session_id = _state.get("chat_session_id")
        if not session_id:
            pytest.skip("No session from previous test")
        r = client.post(
            "/v1/chat/message",
            headers=_auth_headers(),
            json={"message": "Tell me more.", "session_id": session_id},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["session_id"] == session_id

    def test_chat_history(self):
        session_id = _state.get("chat_session_id")
        if not session_id:
            pytest.skip("No session from previous test")
        r = client.get(
            f"/v1/chat/{session_id}/history?limit=50",
            headers=_auth_headers(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list)
        assert len(body) >= 2  # user + assistant messages
        roles = {msg["role"] for msg in body}
        assert "user" in roles
        assert "assistant" in roles

    def test_chat_invalid_session_history_returns_empty_or_404(self):
        fake_id = str(uuid.uuid4())
        r = client.get(f"/v1/chat/{fake_id}/history", headers=_auth_headers())
        assert r.status_code in (200, 404), r.text
        if r.status_code == 200:
            assert r.json() == []


# ============================================================
# 7. Developer API Keys
# ============================================================

class TestDeveloper:
    def test_create_api_key(self):
        r = client.post(
            "/v1/developer/api-keys",
            headers=_auth_headers(),
            json={
                "name": f"live-test-key-{_RUN_ID}",
                "allowed_channels": ["mcp"],
                "agent_type": "mcp",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert "api_key" in body
        assert body["api_key"].startswith("pk_live_")
        assert "id" in body
        _state["dev_key"] = body["api_key"]
        _state["dev_key_id"] = body["id"]

    def test_list_api_keys(self):
        r = client.get("/v1/developer/api-keys", headers=_auth_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list)
        ids = [k["id"] for k in body]
        assert _state.get("dev_key_id") in ids

    def test_revoke_api_key(self):
        key_id = _state.get("dev_key_id")
        if not key_id:
            pytest.skip("No key id from create test")
        r = client.post(
            f"/v1/developer/api-keys/{key_id}/revoke",
            headers=_auth_headers(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["revoked_at"] is not None


# ============================================================
# 8. MCP Server
# ============================================================

class TestMCP:
    def _get_fresh_key(self) -> str:
        """Create a new (unrevoked) key for MCP tests since the main one was revoked."""
        r = client.post(
            "/v1/developer/api-keys",
            headers=_auth_headers(),
            json={"name": f"mcp-test-{_RUN_ID}", "allowed_channels": ["mcp"], "agent_type": "mcp"},
        )
        assert r.status_code == 201, r.text
        key = r.json()["api_key"]
        _state["mcp_key"] = key
        return key

    def test_mcp_list_tools(self):
        key = _state.get("mcp_key") or self._get_fresh_key()
        r = client.get("/mcp/tools/list", headers={"X-API-Key": key})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "tools" in body
        tool_names = [t["name"] for t in body["tools"]]
        assert "search" in tool_names
        assert "ask" in tool_names

    def test_mcp_search(self):
        key = _state.get("mcp_key") or self._get_fresh_key()
        r = client.post(
            "/mcp/tools/search",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            json={"query": "email meeting", "top_k": 5},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "results" in body
        assert "count" in body

    def test_mcp_ask(self):
        key = _state.get("mcp_key") or self._get_fresh_key()
        r = client.post(
            "/mcp/tools/ask",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            json={"question": "Summarize my recent activity", "top_k": 5},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "answer" in body
        assert isinstance(body["answer"], str)
        assert len(body["answer"]) > 0

    def test_mcp_connectors(self):
        key = _state.get("mcp_key") or self._get_fresh_key()
        r = client.get("/mcp/tools/connectors", headers={"X-API-Key": key})
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_mcp_profile(self):
        key = _state.get("mcp_key") or self._get_fresh_key()
        r = client.get("/mcp/tools/profile", headers={"X-API-Key": key})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "email" in body
        assert "item_count" in body
        assert "connector_count" in body

    def test_mcp_invalid_key_returns_401(self):
        r = client.get("/mcp/tools/profile", headers={"X-API-Key": "pk_live_fake_invalid"})
        assert r.status_code == 401, r.text

    def test_mcp_get_item_invalid_id(self):
        key = _state.get("mcp_key") or self._get_fresh_key()
        r = client.get("/mcp/tools/item/not-a-uuid", headers={"X-API-Key": key})
        assert r.status_code == 400, r.text
