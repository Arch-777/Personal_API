# 🏗️ PersonalAPI — System Architecture

> **Version:** 2.0 · **Updated:** 2026-03-13
>
> Complete system architecture for PersonalAPI — a personal data aggregation platform with semantic search, RAG, and portable chatbot access.

---

## 1. Architecture Overview

PersonalAPI aggregates data from multiple services, normalizes it into a unified schema, generates vector embeddings, and exposes it through REST, WebSocket, chatbot, and MCP interfaces.

```
┌──────────────────────────────────────────────────────────────────────┐
│                        PERSONALAPI PLATFORM                          │
│                                                                      │
│   INTERFACES                                                         │
│   ┌───────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐     │
│   │  Next.js  │  │ Chatbot  │  │ OpenClaw  │  │ MCP Server   │     │
│   │ Dashboard │  │   UI     │  │ Telegram/ │  │ (Tool-Based) │     │
│   │  :3000    │  │          │  │ WhatsApp  │  │              │     │
│   └─────┬─────┘  └────┬─────┘  └─────┬─────┘  └──────┬───────┘     │
│         └──────────────┼──────────────┼───────────────┘             │
│                  REST + WebSocket + MCP                              │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    FastAPI Backend  :8000                    │   │
│   │   Auth │ REST API │ WebSocket │ RAG Pipeline │ MCP Server   │   │
│   └──────────────────────┬──────────────────────────────────────┘   │
│                          │                                          │
│   ┌──────────────────────┴──────────────────────────────────────┐   │
│   │              Celery Workers (per-service queues)             │   │
│   │  WhatsApp │ Google │ Notion │ Spotify │ Embedding │ Watcher │   │
│   └──────────────────────┬──────────────────────────────────────┘   │
│                          │                                          │
│   DATA STORES                                                       │
│   ┌──────────────┐  ┌────────┐  ┌──────────────────┐               │
│   │ PostgreSQL   │  │ Redis  │  │ User Data FS     │               │
│   │ + pgvector   │  │ Broker │  │ /users/{id}/data │               │
│   │ :5432        │  │ :6379  │  │                  │               │
│   └──────────────┘  └────────┘  └──────────────────┘               │
└──────────────────────────────────────────────────────────────────────┘
```

### Design Principles

| Principle | Detail |
|---|---|
| **Unified Schema** | All sources normalize into one `items` table with a `type` column |
| **Connector Isolation** | Each service is an independent Celery worker — zero coupling |
| **Security-First** | Fernet encryption, SHA-256 hashed keys, per-user data isolation |
| **Async-First** | Embeddings and syncs run in background workers, never in API path |
| **File-Per-Document** | Each page/note/email stored as an individual JSON file |

---

## 2. Service Topology

| Service | Port | Role |
|---|---|---|
| FastAPI | `8000` | REST API + WebSocket |
| Next.js Dashboard | `3000` | Web frontend |
| PostgreSQL + pgvector | `5432` | Primary database + vector storage |
| Redis | `6379` | Celery broker + cache + pub/sub |
| Flower | `5555` | Celery task monitor |
| OpenClaw | `9000` | External agent bridge (Telegram/WhatsApp) |

---

## 3. Data Source Connectors

### Connector Registry

| Service | Auth | Data Type | Storage Path | Worker |
|---|---|---|---|---|
| WhatsApp | Business API Token | Messages, media | `/users/{id}/data/whatsapp/` | `whatsapp_worker.py` |
| Gmail | OAuth 2.0 | Emails | `/users/{id}/data/google/gmail/` | `google_worker.py` |
| Google Drive | OAuth 2.0 | Documents | `/users/{id}/data/google/drive/` | `google_worker.py` |
| Google Photos | OAuth 2.0 | Photos, metadata | `/users/{id}/data/google/photos/` | `google_worker.py` |
| Google Calendar | OAuth 2.0 | Events | `/users/{id}/data/google/calendar/` | `google_worker.py` |
| Notion | OAuth / Internal Token | Pages, databases | `/users/{id}/data/notion/` | `notion_worker.py` |
| Spotify | OAuth 2.0 | Playlists, history | `/users/{id}/data/spotify/` | `spotify_worker.py` |

### Connector Lifecycle

```
User connects service ──▶ OAuth/Token exchange
    ──▶ Encrypt & store tokens (connectors table)
    ──▶ Enqueue initial sync (Celery/Redis)
    ──▶ Worker fetches data via external API
    ──▶ Normalize → store files → upsert to DB
    ──▶ Trigger embedding job
    ──▶ WebSocket notification to dashboard
```

### Adding New Connectors

Any new service follows: `/users/{userID}/data/{service_name}/`

Create: `workers/{name}_worker.py` + `normalizer/{name}.py` + OAuth config.
No changes needed to DB schema, API endpoints, or RAG pipeline.

---

## 4. User Data Folder Structure

Each user gets an isolated folder keyed by UUID:

```
/users/{userID}/
    └── data/
        ├── whatsapp/
        │   ├── msg_001.json
        │   └── media/
        │       └── img_001.jpg
        ├── google/
        │   ├── drive/
        │   │   ├── doc_001.json
        │   │   └── raw/file.pdf
        │   ├── photos/
        │   │   └── photo_001.json
        │   ├── gmail/
        │   │   └── email_001.json
        │   └── calendar/
        │       └── event_001.json
        ├── notion/
        │   ├── page_001.json
        │   └── page_002.json
        └── spotify/
            ├── playlist_001.json
            └── listening_history.json
```

| Rule | Detail |
|---|---|
| One file per document | Each item stored as a separate JSON file |
| Deterministic naming | `{type}_{source_id}.json` prevents duplicates |
| Media alongside | Binaries go in `raw/` or `media/` subdir |
| Metadata envelope | Standard wrapper: `{ source, source_id, content, metadata, timestamp }` |

---

## 5. Worker Architecture

### Worker Directory

```
workers/
├── celery_app.py            ← Config + queue definitions
├── whatsapp_worker.py
├── google_worker.py         ← Gmail, Drive, Photos, Calendar
├── notion_worker.py
├── spotify_worker.py
├── embedding_worker.py      ← Vector embedding generation
└── file_watcher_worker.py   ← Monitors dirs, triggers re-indexing
```

### Worker Pipeline

```
Step 1 → Authenticate (decrypt OAuth/token from DB, auto-refresh)
Step 2 → Fetch data (paginate, resume from sync_cursor)
Step 3 → Normalize via BaseNormalizer subclass
Step 4 → Store files in /users/{id}/data/{service}/
Step 5 → Upsert items to PostgreSQL (UNIQUE constraint deduplicates)
Step 6 → Dispatch embedding job + WebSocket notification
```

### Periodic Sync Schedule

| Worker | Schedule |
|---|---|
| WhatsApp | Every 15 minutes |
| Google services | Every 30 minutes |
| Notion | Every hour |
| Spotify | Daily at 2:00 AM |

---

## 6. Real-Time Update System

```
Worker writes file → File Watcher detects change
    → Redis Pub/Sub publishes event
    → WebSocket Manager pushes to connected clients
    → Triggers: re-indexing + dashboard notification + RAG update
```

### WebSocket Event Schema

```json
{
  "event": "data.new",
  "user_id": "uuid",
  "service": "notion",
  "file_path": "/users/{id}/data/notion/page_042.json",
  "item_type": "document",
  "timestamp": "2026-03-13T14:00:00Z",
  "actions": { "indexing_triggered": true, "embedding_queued": true }
}
```

---

## 7. RAG System Design

### Pipeline

```
/users/{id}/data/* (source files)
    ──▶ Document Chunking (512 tokens, 50-token overlap)
    ──▶ Embedding Generation (text-embedding-3-small, 1536d)
    ──▶ Vector Storage (PostgreSQL pgvector)
    ──▶ Query Engine (embed query → cosine similarity → filter → re-rank)
    ──▶ Context Assembly (Top-K results → system prompt → LLM)
    ──▶ Response (text answer + source citations + document links)
```

### Chunking Strategy

| Data Type | Approach |
|---|---|
| Emails | Full email as one chunk (most <512 tokens) |
| Documents | Split by section/paragraph, 512 max, 50 overlap |
| Messages | 15-min sliding conversation windows |
| Events | Entire event as one chunk |
| Notion Pages | Split by block/heading boundaries |

### Continuous Indexing

New data is searchable within seconds: worker ingests → file watcher detects → embedding worker runs → pgvector updated → next query includes it. No manual retraining.

---

## 8. MCP Integration

MCP server exposes tool-based access to the RAG system for LLM agents.

| Tool | Description |
|---|---|
| `fetch_user_documents` | Retrieve documents by service, type, or all |
| `search_user_vectors` | Semantic search across all indexed data |
| `retrieve_file_links` | Get paths/links to original files |
| `retrieve_conversation_history` | Fetch past chatbot conversations |

---

## 9. Chatbot Layer

The RAG-powered chatbot is embedded in the dashboard and accessible via OpenClaw.

**Capabilities:** answer questions about user data, retrieve documents, return file links, provide contextual summaries, cross-service search.

```
User Question → Chatbot Interface → RAG Query Engine → pgvector Search
    → Context Assembly (Top-K) → LLM Generation → Response with Sources
```

---

## 10. OpenClaw — External Agent

OpenClaw is a portable interface connecting to PersonalAPI via Telegram and WhatsApp.

### Auth Flow

```
Dashboard → User generates OpenClaw token
    → OpenClaw stores token
    → Authenticates to PersonalAPI
    → User queries via Telegram/WhatsApp
    → Responses: text answers + document links + file references
```

Token management: generated via `/v1/developer/api-keys`, SHA-256 hashed, scoped permissions, revocable from dashboard.

---

## 11. Security Architecture

| Layer | Controls |
|---|---|
| **Authentication** | Google OAuth 2.0, Email+Password (bcrypt), JWT (15-min), Refresh tokens (7-day) |
| **Token Security** | Fernet/AES-256 encryption at rest, SHA-256 API key hashes, auto-refresh |
| **Data Isolation** | All queries filtered by `user_id`, filesystem namespaced by UUID, UNIQUE constraints |
| **Connector Security** | Encrypted credentials, scoped permissions, status tracking, error isolation |
| **Access Control** | Role-based (user/developer/admin), API key scopes, rate limiting, immutable audit log |

---

> **Next:** See [02-implementation-guide.md](./02-implementation-guide.md) for complete backend and frontend implementation.
2