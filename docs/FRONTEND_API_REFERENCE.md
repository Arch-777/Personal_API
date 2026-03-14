# Frontend API Reference

> Base URL: `http://127.0.0.1:8000` (local) or your production domain  
> API prefix: `/v1` (applies to all endpoints except Auth)  
> All protected endpoints require: `Authorization: Bearer <access_token>`

---

## Table of Contents

1. [Auth](#1-auth)
2. [Emails](#2-emails)
3. [Documents](#3-documents)
4. [Search](#4-search)
5. [Chat](#5-chat)
6. [Connectors](#6-connectors)
7. [Developer API Keys](#7-developer-api-keys)
8. [WebSocket](#8-websocket)
9. [MCP Server](#9-mcp-server)

---

## 1. Auth

### POST `/auth/register`
Register a new user with email and password.

**Headers**
```
Content-Type: application/json
```

**Body**
```json
{
  "email": "user@example.com",
  "password": "strongpassword123",
  "full_name": "Jane Doe"
}
```

**Response `201`**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe"
}
```

**Error cases**
- `409` — Email already registered

---

### POST `/auth/login`
Login with email and password, receive a JWT.

**Headers**
```
Content-Type: application/json
```

**Body**
```json
{
  "email": "user@example.com",
  "password": "strongpassword123"
}
```

**Response `200`**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Error cases**
- `401` — Invalid credentials

---

### GET `/auth/me`
Get the currently authenticated user's profile.

**Headers**
```
Authorization: Bearer <access_token>
```

**Response `200`**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe"
}
```

---

### GET `/auth/google/connect`
Get the Google OAuth URL to redirect the user to for app login/signup.

**Headers** _(none required — public endpoint)_

**Response `200`**
```json
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

**Use case:** Redirect the user's browser to `url`. After consent, Google redirects back to `/auth/google/callback`.

---

### GET `/auth/google/callback?code=...&state=...`
Exchange the Google auth code for a PersonalAPI JWT. This is the redirect target from Google.

**Query params**
| Param | Type | Description |
|-------|------|-------------|
| `code` | string | Auth code from Google |
| `state` | string | CSRF state issued by `/auth/google/connect` |

**Response `200`**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Use case:** Handle this redirect in the frontend, extract `access_token`, and store it.

---

### POST `/auth/google`
Login / register using a Google ID token (from Google One Tap or `google-auth-library`).

**Headers**
```
Content-Type: application/json
```

**Body**
```json
{
  "id_token": "eyJhbGciOiJSUzI1NiIs..."
}
```

**Response `200`**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Use case:** Use when you handle Google auth client-side and just pass the `id_token` to the backend.

---

## 2. Emails

### GET `/v1/emails/`
List the authenticated user's synced Gmail emails.

**Headers**
```
Authorization: Bearer <access_token>
```

**Query params**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `20` | Items per page (max 100) |
| `offset` | int | `0` | Pagination offset |

**Response `200`**
```json
{
  "items": [
    {
      "id": "uuid",
      "type": "email",
      "source": "gmail",
      "source_id": "gmail_msg_id",
      "title": "Subject line",
      "sender_name": "John Doe",
      "sender_email": "john@example.com",
      "content": "Email body text...",
      "summary": "Short summary...",
      "metadata": { "labels": ["INBOX"] },
      "item_date": "2026-03-10T09:00:00Z",
      "file_path": "/users/uuid/data/gmail/email_...",
      "created_at": "2026-03-13T12:00:00Z",
      "updated_at": "2026-03-13T12:00:00Z"
    }
  ],
  "total": 142,
  "limit": 20,
  "offset": 0
}
```

**Use case:** Populate an email inbox view. Use `offset` + `limit` for pagination.

---

## 3. Documents

### GET `/v1/documents/`
List the authenticated user's synced documents (Google Drive files and Notion pages).

**Headers**
```
Authorization: Bearer <access_token>
```

**Query params**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `20` | Items per page (max 100) |
| `offset` | int | `0` | Pagination offset |

**Response `200`**
```json
{
  "items": [
    {
      "id": "uuid",
      "type": "document",
      "source": "drive",
      "source_id": "drive_file_id",
      "title": "Q1 Report.pdf",
      "sender_name": "Jane Doe",
      "sender_email": "jane@example.com",
      "content": "Extracted text content...",
      "summary": null,
      "metadata": { "mime_type": "application/pdf", "web_view_link": "https://..." },
      "item_date": "2026-02-15T00:00:00Z",
      "file_path": "/users/uuid/data/drive/document_...",
      "created_at": "2026-03-13T12:00:00Z",
      "updated_at": "2026-03-13T12:00:00Z"
    }
  ],
  "total": 38,
  "limit": 20,
  "offset": 0
}
```

**Use case:** Populate a documents/files browser. Sources include `drive` and `notion`.

---

## 4. Search

### GET `/v1/search/`
Full-text + trigram semantic search across all the user's synced data.

**Headers**
```
Authorization: Bearer <access_token>
```

**Query params**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | _(required)_ | Search query (1–2000 chars) |
| `top_k` | int | `10` | Max results to return (1–50) |
| `type_filter` | string | `null` | Optionally filter by item type (e.g. `email`, `document`, `track`, `message`, `event`) |

**Response `200`**
```json
{
  "query": "project kickoff notes",
  "results": [
    {
      "id": "uuid",
      "type": "document",
      "source": "notion",
      "preview": "First 300 chars of summary or content...",
      "score": 1.42,
      "metadata": { "workspace_name": "My Workspace" },
      "item_date": "2026-03-01T00:00:00Z"
    }
  ],
  "count": 5
}
```

**Use case:** Global search bar. Pass `q` as the user types (debounced). Use `type_filter` to scope the search (e.g. filter by `"email"` in an email view).

---

## 5. Chat

### POST `/v1/chat/message`
Send a chat message. The backend retrieves relevant personal data via RAG and returns a grounded answer.

**Headers**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body**
```json
{
  "message": "What did I discuss with Sarah last week?",
  "session_id": null
}
```

> Pass `session_id` as `null` to start a new conversation, or provide an existing session UUID to continue one.

**Response `200`**
```json
{
  "session_id": "uuid",
  "answer": "Based on your emails and Slack messages, you discussed...",
  "sources": [
    {
      "id": "uuid",
      "type": "email",
      "source": "gmail",
      "score": 0.87,
      "preview": "Hey Sarah, following up on..."
    }
  ],
  "documents": ["Q1 Planning Notes", "Project Kickoff Agenda"],
  "file_links": ["/users/uuid/data/gmail/email_...json"]
}
```

**Use case:** AI chat interface. Always pass `session_id` from the first response in subsequent turns to keep the conversation in context.

---

### GET `/v1/chat/{session_id}/history`
Retrieve the message history for an existing chat session.

**Headers**
```
Authorization: Bearer <access_token>
```

**Path params**
| Param | Type | Description |
|-------|------|-------------|
| `session_id` | UUID | Chat session identifier |

**Query params**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `50` | Max messages to return (1–200) |

**Response `200`**
```json
[
  {
    "id": "uuid",
    "role": "user",
    "content": "What did I discuss with Sarah last week?",
    "sources": [],
    "created_at": "2026-03-14T10:30:00Z"
  },
  {
    "id": "uuid",
    "role": "assistant",
    "content": "Based on your emails...",
    "sources": [{ "id": "...", "type": "email", "source": "gmail", "score": 0.87, "preview": "..." }],
    "created_at": "2026-03-14T10:30:02Z"
  }
]
```

**Use case:** Restore chat history when the user reopens a session. Messages are ordered oldest → newest.

---

## 6. Connectors

> Connectors represent linked third-party platforms (Gmail, Slack, Notion, Google Drive, Google Calendar, Spotify).

### GET `/v1/connectors/`
List all connectors for the authenticated user.

**Headers**
```
Authorization: Bearer <access_token>
```

**Response `200`**
```json
[
  {
    "id": "uuid",
    "platform": "gmail",
    "platform_email": "user@gmail.com",
    "status": "connected",
    "last_synced": "2026-03-14T08:00:00Z",
    "error_message": null,
    "metadata": { "google_scopes": "openid email https://..." },
    "created_at": "2026-03-13T09:00:00Z",
    "updated_at": "2026-03-14T08:00:00Z"
  }
]
```

**`status` values:** `connected` | `syncing` | `error` | `disconnected`

**Use case:** Display integration status cards on the settings/integrations page.

---

### GET `/v1/connectors/{platform}`
Get status for a single connector.

**Headers**
```
Authorization: Bearer <access_token>
```

**Path params**
| Param | Type | Description |
|-------|------|-------------|
| `platform` | string | `gmail` \| `drive` \| `gcal` \| `notion` \| `slack` \| `spotify` |

**Response `200`** — same shape as a single item from the list above.

---

### POST `/v1/connectors/{platform}/sync`
Trigger a background data sync for the given platform.

**Headers**
```
Authorization: Bearer <access_token>
```

**Body** — none

**Response `202`**
```json
{
  "status": "sync_queued",
  "platform": "notion"
}
```

**Use case:** "Sync now" button. After calling this, listen on the WebSocket for `sync.started`, `sync.progress`, and `sync.completed` events.

---

### DELETE `/v1/connectors/{platform}`
Disconnect (remove) an integration and optionally wipe all synced data for it.

**Headers**
```
Authorization: Bearer <access_token>
```

**Path params**
| Param | Type | Description |
|-------|------|-------------|
| `platform` | string | `gmail` \| `drive` \| `gcal` \| `notion` \| `slack` \| `spotify` |

**Query params**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `delete_data` | bool | `false` | When `true`, permanently deletes all synced `items` (and `item_chunks`) for the removed platform(s) |
| `cascade_google` | bool | `true` | When `true` and the platform is any Google connector (`gmail`, `drive`, `gcal`), **all three** Google connectors are removed together — they share a single OAuth token |

**Response `200`**
```json
{
  "disconnected": ["drive", "gcal", "gmail"],
  "items_deleted": 0
}
```

- `disconnected` — sorted list of all connector platform rows that were removed
- `items_deleted` — number of synced item rows deleted; always `0` when `delete_data=false`

**Error cases**
- `400` — Unknown or unsupported platform
- `404` — No connector found for the requested platform

**Examples**

| Use case | Request |
|----------|---------|
| Remove Notion | `DELETE /v1/connectors/notion` |
| Remove all Google connectors | `DELETE /v1/connectors/gmail` (cascade_google defaults to true) |
| Remove Gmail only, keep Drive & GCal | `DELETE /v1/connectors/gmail?cascade_google=false` |
| Remove Slack + wipe all Slack messages | `DELETE /v1/connectors/slack?delete_data=true` |

> **Note on Google:** Because Gmail, Drive, and Google Calendar share one OAuth token, removing any one of them without `cascade_google=false` removes all three. The frontend should warn the user about this before confirming.

---

### Google OAuth Connect Flow (Gmail / Drive / Google Calendar)

**Step 1 — Get the consent URL**

```
GET /v1/connectors/google/connect?platform=gmail
Authorization: Bearer <access_token>
```

Response:
```json
{ "url": "https://accounts.google.com/o/oauth2/v2/auth?..." }
```

**Step 2 — Redirect user to `url`**

**Step 3 — Google redirects back to `/v1/connectors/google/callback?code=...&state=...`**
The API handles token exchange and saves the connector automatically.

---

### Notion OAuth Connect Flow

**Step 1 — Get the consent URL**

```
GET /v1/connectors/notion/connect
Authorization: Bearer <access_token>
```

Response:
```json
{ "url": "https://api.notion.com/v1/oauth/authorize?..." }
```

**Step 2 — Redirect user to `url`**

**Step 3 — Notion redirects back to `/v1/connectors/notion/callback?code=...&state=...`**

---

### Notion Quick Token (Dev / Internal Integration)

```
POST /v1/connectors/notion/token
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body**
```json
{
  "access_token": "ntn_xxxxxxxxxxxxxxxx"
}
```

**Response `200`**
```json
{
  "status": "connected",
  "platform": "notion",
  "workspace": "My Workspace"
}
```

**Use case:** For Notion internal integrations (no OAuth flow needed). Get the token from [notion.so/my-integrations](https://www.notion.so/my-integrations).

---

### Slack OAuth Connect Flow

**Step 1 — Get the consent URL**

```
GET /v1/connectors/slack/connect
Authorization: Bearer <access_token>
```

Response:
```json
{ "url": "https://slack.com/oauth/v2/authorize?..." }
```

**Step 2 — Redirect user to `url`**

**Step 3 — Slack redirects back to `/v1/connectors/slack/callback?code=...&state=...`**

---

### Spotify OAuth Connect Flow

**Step 1 — Get the consent URL**

```
GET /v1/connectors/spotify/connect
Authorization: Bearer <access_token>
```

Response:
```json
{ "url": "https://accounts.spotify.com/authorize?..." }
```

**Step 2 — Redirect user to `url`**

**Step 3 — Spotify redirects back to `/v1/connectors/spotify/callback?code=...&state=...`**

---

### POST `/v1/connectors/{platform}/bootstrap`
Seed a connector with sample/test data for demo purposes without going through a full OAuth flow.

**Headers**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body**
```json
{
  "access_token": "optional-token",
  "metadata_json": {
    "sample_records": [
      { "id": "1", "subject": "Test email" }
    ]
  }
}
```

**Response `201`** — ConnectorResponse (same shape as GET `/v1/connectors/{platform}`)

---

## 7. Developer API Keys

Used to generate keys for agent/automation access to this API.

### POST `/v1/developer/api-keys`
Create a new API key.

**Headers**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body**
```json
{
  "name": "My MCP Agent Key",
  "allowed_channels": ["mcp", "agent"],
  "agent_type": "mcp"
}
```

**Response `201`**
```json
{
  "id": "uuid",
  "name": "My MCP Agent Key",
  "key_prefix": "pk_live_xxxxxx",
  "api_key": "pk_live_xxxxxxxxxxxxxxxxxxx",
  "allowed_channels": ["mcp", "agent"],
  "agent_type": "mcp",
  "created_at": "2026-03-14T10:00:00Z"
}
```

> **Important:** `api_key` is returned **only once**. Store it securely — it cannot be retrieved again.

---

### GET `/v1/developer/api-keys`
List all API keys for the authenticated user.

**Headers**
```
Authorization: Bearer <access_token>
```

**Response `200`**
```json
[
  {
    "id": "uuid",
    "name": "My MCP Agent Key",
    "key_prefix": "pk_live_xxxxxx",
    "allowed_channels": ["mcp"],
    "agent_type": "mcp",
    "created_at": "2026-03-14T10:00:00Z",
    "last_used_at": null,
    "expires_at": null,
    "revoked_at": null
  }
]
```

---

### POST `/v1/developer/api-keys/{api_key_id}/revoke`
Revoke an existing API key.

**Headers**
```
Authorization: Bearer <access_token>
```

**Path params**
| Param | Type | Description |
|-------|------|-------------|
| `api_key_id` | UUID | ID of the key to revoke |

**Response `200`** — same shape as list item, with `revoked_at` set.

---

## 8. WebSocket

### WS `/ws`
Real-time push notifications for sync progress and completion events.

**Connection URL**
```
ws://127.0.0.1:8000/ws?token=<access_token>
```

> Pass the JWT as the `token` query parameter (WebSocket connections cannot set `Authorization` headers in browsers).

**Connection example (JavaScript)**
```js
const ws = new WebSocket(`ws://127.0.0.1:8000/ws?token=${accessToken}`);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg.event, msg.data);
};
```

**Ping / keepalive**

Send a plain text `"ping"` message to keep the connection alive. The server responds with `"pong"`.

---

**Event envelope shape**
```json
{
  "event": "sync.completed",
  "timestamp": "2026-03-14T10:05:23Z",
  "user_id": "uuid",
  "data": { ... }
}
```

---

**Event types**

| Event | When | `data` fields |
|-------|------|---------------|
| `connected` | Immediately on successful connection | `{ "message": "Connected" }` |
| `sync.started` | Sync task picked up by worker | `{ "platform", "connector_id", "task_id" }` |
| `sync.progress` | During ingestion (optional, if emitted) | `{ "platform", "connector_id", "processed", "total" }` |
| `sync.completed` | Sync finished successfully | `{ "platform", "connector_id", "items_upserted", "embedded" }` |
| `sync.failed` | Sync encountered an error | `{ "platform", "connector_id", "error" }` |
| `error` | Auth failure or server error | `{ "detail": "..." }` |

---

**Use case flow**

1. Establish WS connection on app load (after login).
2. User clicks "Sync Now" → call `POST /v1/connectors/{platform}/sync`.
3. Listen for `sync.started` → show spinner/progress indicator.
4. Listen for `sync.completed` → dismiss spinner, refresh email/document lists.
5. Listen for `sync.failed` → show error toast.

---

## 9. MCP Server

> The MCP (Model Context Protocol) server is mounted at `/mcp` and exposes tool-based data access for AI agents (Claude Desktop, custom MCP clients, automation scripts, etc.).  
> **Auth:** All MCP endpoints require `X-API-Key: <developer_key>` — generate one via `POST /v1/developer/api-keys`.  
> **Base URL:** `http://127.0.0.1:8000/mcp` (same host as the main API).

---

### GET `/mcp/health`
Liveness check for the MCP sub-application.

**Headers** — none required

**Response `200`**
```json
{ "status": "ok", "service": "mcp" }
```

---

### GET `/mcp/tools/list`
Discover all available MCP tools. Useful for MCP client auto-discovery.

**Headers**
```
X-API-Key: pk_live_xxxxxxxxxx
```

**Response `200`**
```json
{
  "tools": [
    {
      "name": "search",
      "method": "POST",
      "path": "/tools/search",
      "description": "Full-text search across all synced personal data.",
      "input_schema": {
        "query": "string (required)",
        "top_k": "integer (default 10, max 50)",
        "type_filter": "string|null — email|document|track|message|event",
        "source_filter": "string|null — gmail|drive|notion|slack|spotify|gcal"
      }
    },
    { "name": "ask", "method": "POST", "path": "/tools/ask", "description": "..." },
    { "name": "get_item", "method": "GET", "path": "/tools/item/{item_id}", "description": "..." },
    { "name": "list_connectors", "method": "GET", "path": "/tools/connectors", "description": "..." },
    { "name": "get_profile", "method": "GET", "path": "/tools/profile", "description": "..." }
  ]
}
```

---

### POST `/mcp/tools/search`
Full-text search across all of the user's synced personal data.

**Headers**
```
X-API-Key: pk_live_xxxxxxxxxx
Content-Type: application/json
```

**Body**
```json
{
  "query": "project kickoff meeting notes",
  "top_k": 10,
  "type_filter": "document",
  "source_filter": "notion"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | ✅ | Natural language search query (1–2000 chars) |
| `top_k` | int | ❌ | Number of results (default `10`, max `50`) |
| `type_filter` | string | ❌ | `email` \| `document` \| `track` \| `message` \| `event` |
| `source_filter` | string | ❌ | `gmail` \| `drive` \| `notion` \| `slack` \| `spotify` \| `gcal` |

**Response `200`**
```json
{
  "query": "project kickoff meeting notes",
  "results": [
    {
      "id": "uuid",
      "type": "document",
      "source": "notion",
      "title": "Project Kickoff — Q2",
      "preview": "First 300 chars of summary or content...",
      "score": 1.0,
      "item_date": "2026-03-01T00:00:00Z",
      "metadata": { "workspace_name": "My Workspace" }
    }
  ],
  "count": 3
}
```

**Use case:** Agent-driven data lookup. Pass user query directly; filter by `type_filter` to narrow scope.

---

### POST `/mcp/tools/ask`
Ask a natural language question and receive a grounded answer with source citations from the RAG engine.

**Headers**
```
X-API-Key: pk_live_xxxxxxxxxx
Content-Type: application/json
```

**Body**
```json
{
  "question": "What did I discuss with my team last week about the product roadmap?",
  "session_id": null,
  "top_k": 8
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | ✅ | Natural language question (1–4000 chars) |
| `session_id` | string | ❌ | Optional session UUID for conversation continuity |
| `top_k` | int | ❌ | Number of context documents to retrieve (default `8`, max `30`) |

**Response `200`**
```json
{
  "answer": "Based on your Slack messages and Notion notes, you discussed...",
  "sources": [
    { "id": "uuid", "type": "message", "source": "slack", "score": 0.92, "preview": "..." }
  ],
  "documents": ["Product Roadmap Q2", "Team Standup Notes"],
  "file_links": ["/users/uuid/data/slack/message_...json"]
}
```

**Use case:** Conversational AI agent that reasons over the user's personal data. If `RAG_LLM_ENABLED=true`, uses local Ollama/qwen2.5 for generation; otherwise uses deterministic context assembly.

---

### GET `/mcp/tools/item/{item_id}`
Retrieve the full content and metadata of a single personal data item by UUID.

**Headers**
```
X-API-Key: pk_live_xxxxxxxxxx
```

**Path params**
| Param | Type | Description |
|-------|------|-------------|
| `item_id` | UUID | Item identifier from a search result |

**Response `200`**
```json
{
  "id": "uuid",
  "type": "email",
  "source": "gmail",
  "source_id": "gmail_message_id",
  "title": "Re: Q2 Planning",
  "sender_name": "Jane Doe",
  "sender_email": "jane@example.com",
  "content": "Full email body text...",
  "summary": "Short summary...",
  "metadata": { "labels": ["INBOX"], "connector_id": "uuid" },
  "item_date": "2026-03-10T09:00:00Z",
  "file_path": "/users/uuid/data/gmail/email_...json"
}
```

**Error cases**
- `400` — Invalid UUID format
- `404` — Item not found or not owned by key owner

---

### GET `/mcp/tools/connectors`
List all connected platforms and their sync status for the key owner.

**Headers**
```
X-API-Key: pk_live_xxxxxxxxxx
```

**Response `200`**
```json
[
  {
    "platform": "gmail",
    "status": "connected",
    "platform_email": "user@gmail.com",
    "last_synced": "2026-03-14T08:00:00Z",
    "error_message": null
  },
  {
    "platform": "notion",
    "status": "connected",
    "platform_email": null,
    "last_synced": "2026-03-14T07:30:00Z",
    "error_message": null
  }
]
```

**Use case:** Agent checks which data sources are available before deciding where to search.

---

### GET `/mcp/tools/profile`
Return the user's profile and a summary of their synced data counts.

**Headers**
```
X-API-Key: pk_live_xxxxxxxxxx
```

**Response `200`**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "connector_count": 4,
  "item_count": 1842
}
```

**Use case:** Agent introduction — understand who the user is and how much data has been synced before querying.

---

## Error Response Format

All errors follow this shape:

```json
{
  "detail": "Human-readable error message"
}
```

**Common HTTP status codes**

| Code | Meaning |
|------|---------|
| `400` | Bad request / validation error |
| `401` | Missing or invalid token |
| `403` | Forbidden |
| `404` | Resource not found |
| `409` | Conflict (e.g. email already registered) |
| `422` | Request body schema validation failed |
| `503` | External service unavailable (OAuth not configured, Redis down) |

---

## Auth Header Quick Reference

```js
// Set once after login
const headers = {
  "Authorization": `Bearer ${accessToken}`,
  "Content-Type": "application/json"
};

// All protected API calls
fetch(`${BASE_URL}/v1/emails/`, { headers });
```
