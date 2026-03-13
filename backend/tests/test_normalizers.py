import json
import uuid
from types import SimpleNamespace

import httpx

from normalizer.base import NormalizedItem
from normalizer.drive import DriveNormalizer
from normalizer.gcal import GCalNormalizer
from normalizer.gmail import GmailNormalizer
from normalizer.notion import NotionNormalizer
from normalizer.slack import SlackNormalizer
from normalizer.spotify import SpotifyNormalizer
from workers import connector_sync


def test_gmail_normalizer_maps_subject_sender_and_date():
	normalizer = GmailNormalizer()
	row = {
		"id": "msg-1",
		"snippet": "Hello from Gmail",
		"internalDate": "1710000000000",
		"payload": {
			"headers": [
				{"name": "Subject", "value": "Quarterly Update"},
				{"name": "From", "value": "Alice <alice@example.com>"},
				{"name": "Date", "value": "2026-03-13T10:00:00Z"},
			]
		},
	}

	item = normalizer.normalize_record(row)

	assert item is not None
	assert item.type == "email"
	assert item.source == "gmail"
	assert item.source_id == "msg-1"
	assert item.title == "Quarterly Update"
	assert item.sender_name == "Alice"
	assert item.sender_email == "alice@example.com"
	assert item.content == "Hello from Gmail"
	assert item.item_date is not None


def test_drive_normalizer_maps_document_fields():
	normalizer = DriveNormalizer()
	row = {
		"id": "file-1",
		"name": "Specs",
		"mimeType": "application/pdf",
		"description": "Project specification",
		"modifiedTime": "2026-03-13T11:00:00Z",
		"owners": [{"displayName": "Bob", "emailAddress": "bob@example.com"}],
	}

	item = normalizer.normalize_record(row)
	assert item is not None
	assert item.type == "document"
	assert item.title == "Specs"
	assert item.sender_name == "Bob"
	assert item.metadata_json["mime_type"] == "application/pdf"


def test_gcal_normalizer_maps_event_fields():
	normalizer = GCalNormalizer()
	row = {
		"id": "event-1",
		"summary": "Team Sync",
		"description": "Weekly planning",
		"start": {"dateTime": "2026-03-13T09:30:00Z"},
		"end": {"dateTime": "2026-03-13T10:00:00Z"},
		"creator": {"displayName": "Carol", "email": "carol@example.com"},
	}

	item = normalizer.normalize_record(row)
	assert item is not None
	assert item.type == "event"
	assert item.sender_name == "Carol"
	assert item.sender_email == "carol@example.com"
	assert item.metadata_json["attendees_count"] == 0


def test_notion_normalizer_extracts_title_from_properties():
	normalizer = NotionNormalizer()
	row = {
		"id": "page-1",
		"plain_text": "Notion page body",
		"properties": {
			"Name": {
				"type": "title",
				"title": [{"plain_text": "Roadmap"}],
			}
		},
		"last_edited_time": "2026-03-13T12:00:00Z",
	}

	item = normalizer.normalize_record(row)
	assert item is not None
	assert item.type == "document"
	assert item.title == "Roadmap"
	assert item.content == "Notion page body"


def test_spotify_normalizer_maps_track_and_artists():
	normalizer = SpotifyNormalizer()
	row = {
		"liked": True,
		"top_rank": 3,
		"played_at": "2026-03-13T08:00:00Z",
		"track": {
			"id": "trk-1",
			"name": "Morning Light",
			"artists": [{"name": "Artist A"}, {"name": "Artist B"}],
			"popularity": 88,
			"album": {"name": "Sunrise"},
		},
	}

	item = normalizer.normalize_record(row)
	assert item is not None
	assert item.type == "track"
	assert item.title == "Morning Light"
	assert item.sender_name == "Artist A, Artist B"
	assert item.metadata_json["album"] == "Sunrise"
	assert item.metadata_json["track_id"] == "trk-1"
	assert item.metadata_json["liked"] is True
	assert item.metadata_json["top_rank"] == 3


def test_slack_normalizer_maps_message_channel_and_sender_profile():
	normalizer = SlackNormalizer()
	row = {
		"ts": "1710000000.123",
		"text": "Daily standup notes",
		"user": "U123",
		"thread_ts": "1710000000.123",
		"_channel": {"id": "C123", "name": "engineering", "is_private": False, "is_im": False, "is_mpim": False},
		"_user_profile": {"id": "U123", "display_name": "Nisha", "email": "nisha@example.com"},
	}

	item = normalizer.normalize_record(row)

	assert item is not None
	assert item.type == "message"
	assert item.source == "slack"
	assert item.source_id == "C123:1710000000.123"
	assert item.sender_name == "Nisha"
	assert item.sender_email == "nisha@example.com"
	assert item.metadata_json["channel_name"] == "engineering"
	assert item.metadata_json["thread_ts"] == "1710000000.123"


def test_fetch_slack_records_collects_messages_and_advances_cursor(monkeypatch):
	payloads = {
		"https://slack.com/api/conversations.list": {
			"ok": True,
			"channels": [{"id": "C123", "name": "engineering", "is_private": False, "is_im": False, "is_mpim": False}],
		},
		"https://slack.com/api/conversations.history": {
			"ok": True,
			"messages": [{"type": "message", "ts": "1710000000.123", "text": "Deploy done", "user": "U123"}],
		},
		"https://slack.com/api/users.info": {
			"ok": True,
			"user": {
				"name": "nisha",
				"profile": {"display_name": "Nisha", "email": "nisha@example.com"},
			},
		},
	}

	def fake_get(url, access_token, params=None, headers=None):
		return payloads[url]

	monkeypatch.setattr(connector_sync, "_http_get_json", fake_get)
	rows, next_cursor = connector_sync._fetch_slack_records(access_token="token", source_cursor="0")

	assert len(rows) == 1
	assert rows[0]["_channel"]["id"] == "C123"
	assert rows[0]["_user_profile"]["email"] == "nisha@example.com"
	assert json.loads(next_cursor)["latest_ts"] == "1710000000.123"


def test_fetch_gmail_records_does_not_send_invalid_zero_page_token(monkeypatch):
	seen_params = {}

	def fake_get(url, access_token, params=None, headers=None):
		if "messages/" in url:
			return {"id": "msg-1", "snippet": "Hello", "payload": {"headers": []}}
		seen_params.update(params or {})
		return {"messages": [{"id": "msg-1"}]}

	monkeypatch.setattr(connector_sync, "_http_get_json", fake_get)

	rows, next_cursor = connector_sync._fetch_gmail_records(access_token="token", source_cursor="0")

	assert len(rows) == 1
	assert "pageToken" not in seen_params
	assert next_cursor == ""


def test_fetch_drive_records_uses_incremental_state_cursor(monkeypatch):
	calls = []

	def fake_get(url, access_token, params=None, headers=None):
		calls.append(params or {})
		return {
			"files": [
				{
					"id": "file-1",
					"name": "Roadmap",
					"modifiedTime": "2026-03-14T10:00:00Z",
				}
			]
		}

	monkeypatch.setattr(connector_sync, "_http_get_json", fake_get)

	rows, next_cursor = connector_sync._fetch_drive_records(access_token="token", source_cursor="0")

	assert len(rows) == 1
	assert calls
	assert "pageToken" not in calls[0]
	assert "trashed = false" in calls[0]["q"]
	state = json.loads(next_cursor)
	assert state["updated_after"] == "2026-03-14T10:00:00Z"


def test_fetch_gcal_records_recovers_when_sync_token_is_expired(monkeypatch):
	calls = []

	def fake_get(url, access_token, params=None, headers=None):
		calls.append(params or {})
		if "syncToken" in (params or {}):
			req = httpx.Request("GET", url)
			resp = httpx.Response(410, request=req)
			raise httpx.HTTPStatusError("stale sync token", request=req, response=resp)
		return {
			"items": [{"id": "event-1", "updated": "2026-03-14T11:00:00Z"}],
			"nextSyncToken": "sync-next-1",
		}

	monkeypatch.setattr(connector_sync, "_http_get_json", fake_get)

	rows, next_cursor = connector_sync._fetch_gcal_records(
		access_token="token",
		source_cursor=json.dumps({"sync_token": "stale-token", "updated_after": "2026-03-14T09:00:00Z"}),
	)

	assert len(rows) == 1
	assert len(calls) == 2
	assert calls[0]["syncToken"] == "stale-token"
	assert calls[1]["updatedMin"] == "2026-03-14T09:00:00Z"
	state = json.loads(next_cursor)
	assert state["sync_token"] == "sync-next-1"
	assert state["updated_after"] == "2026-03-14T11:00:00Z"


def test_fetch_notion_records_ignores_zero_cursor_and_returns_empty_next_cursor(monkeypatch):
	requests: list[dict[str, object]] = []

	def fake_post(url, access_token, json_body=None, headers=None):
		requests.append({"url": url, "json_body": dict(json_body or {})})
		return {"results": [{"object": "page", "id": "page-1"}], "next_cursor": None}

	monkeypatch.setattr(connector_sync, "_http_post_json", fake_post)
	monkeypatch.setattr(connector_sync, "_enrich_notion_rows", lambda access_token, rows: rows)

	rows, next_cursor = connector_sync._fetch_notion_records(access_token="token", source_cursor="0")

	assert len(rows) == 1
	assert requests[0]["json_body"] == {"page_size": 25}
	assert next_cursor == ""


def test_fetch_platform_records_uses_seeded_metadata_records_without_http():
	connector = SimpleNamespace(
		metadata_json={
			"sample_records": [{"id": "seed-1", "snippet": "seed"}],
			"sample_next_cursor": "42",
		}
	)

	rows, next_cursor = connector_sync._fetch_platform_records(
		platform="gmail",
		connector=connector,
		source_cursor="10",
		access_token="token",
	)

	assert len(rows) == 1
	assert rows[0]["id"] == "seed-1"
	assert next_cursor == "42"


def test_store_item_file_writes_deterministic_user_path(tmp_path, monkeypatch):
	user_id = uuid.uuid4()
	item = NormalizedItem(
		type="document",
		source="notion",
		source_id="page/42",
		title="Roadmap",
		sender_name=None,
		sender_email=None,
		content="Body",
		summary="Body",
		metadata_json={"k": "v"},
		item_date=None,
		raw_record={"id": "page/42"},
	)

	monkeypatch.setattr(connector_sync, "get_settings", lambda: SimpleNamespace(user_data_root=str(tmp_path)))

	file_path = connector_sync._store_item_file(user_id=user_id, platform="notion", item=item)

	assert file_path.startswith(f"/users/{user_id}/data/notion/document_")
	filename = file_path.rsplit("/", 1)[-1]
	actual_path = tmp_path / "users" / str(user_id) / "data" / "notion" / filename
	assert actual_path.exists()

	payload = json.loads(actual_path.read_text(encoding="utf-8"))
	assert payload["source_id"] == "page/42"
	assert payload["title"] == "Roadmap"


def test_persist_normalized_items_adds_connector_metadata(monkeypatch):
	connector = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), platform="gmail")
	item = NormalizedItem(
		type="email",
		source="gmail",
		source_id="msg-99",
		title="Subject",
		sender_name="Alice",
		sender_email="alice@example.com",
		content="Body",
		summary="Body",
		metadata_json={"thread_id": "th-1"},
		item_date=None,
		raw_record={"id": "msg-99"},
	)

	monkeypatch.setattr(connector_sync, "_store_item_file", lambda **_: "/users/u/data/gmail/email_msg-99.json")
	rows = connector_sync._persist_normalized_items(connector, [item], source_cursor="7")

	assert len(rows) == 1
	row = rows[0]
	assert row["file_path"] == "/users/u/data/gmail/email_msg-99.json"
	assert row["metadata_json"]["ingestion_mode"] == "api"
	assert row["metadata_json"]["cursor"] == "7"
	assert row["metadata_json"]["connector_id"] == str(connector.id)


def test_extract_notion_plain_text_joins_rich_text_lines():
	blocks = [
		{
			"type": "paragraph",
			"paragraph": {
				"rich_text": [
					{"plain_text": "Line one"},
					{"plain_text": "part two"},
				],
			},
		},
		{
			"type": "heading_1",
			"heading_1": {
				"rich_text": [{"plain_text": "Header"}],
			},
		},
	]

	text = connector_sync._extract_notion_plain_text(blocks)

	assert text == "Line one part two\nHeader"


def test_fetch_notion_database_rows_returns_empty_on_http_error(monkeypatch):
	def _raise(*_args, **_kwargs):
		raise ValueError("boom")

	monkeypatch.setattr(connector_sync, "_http_post_json", _raise)
	rows = connector_sync._fetch_notion_database_rows(access_token="token", database_id="db-1")

	assert rows == []

