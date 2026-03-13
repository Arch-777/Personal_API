import json
import uuid
from types import SimpleNamespace

from normalizer.base import NormalizedItem
from normalizer.drive import DriveNormalizer
from normalizer.gcal import GCalNormalizer
from normalizer.gmail import GmailNormalizer
from normalizer.notion import NotionNormalizer
from normalizer.spotify import SpotifyNormalizer
from normalizer.whatsapp import WhatsAppNormalizer
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


def test_whatsapp_normalizer_maps_message_fields():
	normalizer = WhatsAppNormalizer()
	row = {
		"id": "wa-1",
		"text": {"body": "Hey there"},
		"from": "+15550001111",
		"from_name": "Drew",
		"timestamp": "1710000000",
	}

	item = normalizer.normalize_record(row)
	assert item is not None
	assert item.type == "message"
	assert item.source_id == "wa-1"
	assert item.sender_name == "Drew"
	assert item.content == "Hey there"


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
		"played_at": "2026-03-13T08:00:00Z",
		"track": {
			"id": "trk-1",
			"name": "Morning Light",
			"artists": [{"name": "Artist A"}, {"name": "Artist B"}],
			"album": {"name": "Sunrise"},
		},
	}

	item = normalizer.normalize_record(row)
	assert item is not None
	assert item.type == "media"
	assert item.title == "Morning Light"
	assert item.sender_name == "Artist A, Artist B"
	assert item.metadata_json["album"] == "Sunrise"


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

