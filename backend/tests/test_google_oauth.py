import types

import pytest

import api.core.google_oauth as google_oauth


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = types.SimpleNamespace(url="https://example.com")
            response = types.SimpleNamespace(status_code=self.status_code, text="error")
            raise google_oauth.httpx.HTTPStatusError("bad status", request=request, response=response)

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _configure_google_settings(monkeypatch):
    monkeypatch.setattr(google_oauth.settings, "google_client_id", "web-client-id")
    monkeypatch.setattr(google_oauth.settings, "google_allowed_client_ids", "web-client-id,mobile-client-id")


def test_verify_google_id_token_supports_bearer_prefix(monkeypatch):
    def _fake_get(url, *, params=None, headers=None, timeout=None):
        assert timeout == 8.0
        if params and params.get("id_token") == "valid-id-token":
            return _FakeResponse(
                200,
                {
                    "iss": "https://accounts.google.com",
                    "aud": "web-client-id",
                    "email": "person@example.com",
                    "email_verified": "true",
                    "name": "Person",
                },
            )
        raise AssertionError("unexpected request")

    monkeypatch.setattr(google_oauth.httpx, "get", _fake_get)

    identity = google_oauth.verify_google_id_token("Bearer valid-id-token")

    assert identity == {"email": "person@example.com", "name": "Person"}


def test_verify_google_id_token_falls_back_to_access_token(monkeypatch):
    def _fake_get(url, *, params=None, headers=None, timeout=None):
        if params and "id_token" in params:
            return _FakeResponse(400, {"error": "invalid_token"})
        if params and params.get("access_token") == "valid-access-token":
            return _FakeResponse(200, {"aud": "mobile-client-id"})
        if headers and headers.get("Authorization") == "Bearer valid-access-token":
            return _FakeResponse(
                200,
                {
                    "email": "mobile@example.com",
                    "verified_email": True,
                    "name": "Mobile User",
                },
            )
        raise AssertionError("unexpected request")

    monkeypatch.setattr(google_oauth.httpx, "get", _fake_get)

    identity = google_oauth.verify_google_id_token("valid-access-token")

    assert identity == {"email": "mobile@example.com", "name": "Mobile User"}


def test_verify_google_id_token_rejects_mismatched_audience(monkeypatch):
    def _fake_get(url, *, params=None, headers=None, timeout=None):
        if params and params.get("id_token") == "wrong-audience-token":
            return _FakeResponse(
                200,
                {
                    "iss": "accounts.google.com",
                    "aud": "other-client-id",
                    "email": "person@example.com",
                    "email_verified": "true",
                },
            )
        raise AssertionError("unexpected request")

    monkeypatch.setattr(google_oauth.httpx, "get", _fake_get)

    with pytest.raises(ValueError, match="Google token audience mismatch"):
        google_oauth.verify_google_id_token("wrong-audience-token")
