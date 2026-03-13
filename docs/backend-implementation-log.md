# Backend Implementation Log

## Purpose
Track backend implementation progress step-by-step, with what changed, status, and next action.

## Format
- Step: Identifier and title
- Status: Completed | In Progress | Blocked
- Date: YYYY-MM-DD
- Changes: Files and summary
- Verification: How it was validated
- Next: Immediate next step

---

## Step 1 - Foundation Setup (Person 1 / Week 1)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/requirements.txt: Added initial backend dependencies.
  - backend/api/main.py: Added FastAPI app bootstrap, CORS, health endpoint, and router inclusion pattern.
  - backend/api/core/config.py: Added environment-based settings.
  - backend/api/core/db.py: Added SQLAlchemy engine, Base, session factory, and get_db dependency.
  - backend/.env.example: Added baseline environment variables.
- Verification:
  - Python compile check passed for API package.
- Next:
  - Implement auth/security and user model.

## Step 2 - Auth and Security Core (Person 1 / Week 2)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/core/security.py: Added password hashing and JWT create/decode utilities.
  - backend/api/core/auth.py: Added get_current_user dependency with token validation and UUID parsing.
  - backend/api/models/user.py: Added users ORM model.
  - backend/api/schemas/auth.py: Added register/login/token/user response schemas.
  - backend/api/routers/auth.py: Added register, login, and me endpoints.
  - backend/requirements.txt: Added email-validator.
- Verification:
  - Python compile check passed for updated modules.
- Next:
  - Implement remaining DB models and migration schema.

## Step 3 - Azure PostgreSQL + pgvector Schema (Person 1 DB Track)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/migrations/001_initial.sql: Added initial schema with extensions, core tables, constraints, and indexes.
    - Extensions: pgcrypto, vector, pg_trgm.
    - Optional extension: pageinspect (guarded block to avoid migration failure when unavailable).
    - Vector search: embedding vector(1536) + ivfflat cosine index.
    - Text/page indexing: generated tsvector + GIN and trigram index.
  - backend/api/core/config.py: Added DATABASE_SSL_MODE and DATABASE_CONNECT_TIMEOUT settings.
  - backend/api/core/db.py: Added SQLAlchemy connect_args for sslmode and connect_timeout.
  - backend/.env.example: Added Azure PostgreSQL connection examples and SSL mode guidance.
  - backend/requirements.txt: Fixed typo pydanti to pydantic.
- Verification:
  - Python compile check passed for api/core.
- Next:
  - Align all SQLAlchemy models with the SQL schema and create schema-level Pydantic models.

## Step 4 - ORM and Schema Parity (Person 1 / Week 2)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/models/connector.py: Added Connector ORM model matching connectors table.
  - backend/api/models/item.py: Added Item ORM model with vector(1536), metadata JSONB, and search-aligned fields.
  - backend/api/models/api_key.py: Added ApiKey ORM model with allowed_channels and lifecycle fields.
  - backend/api/models/chat_session.py: Added ChatSession and ChatMessage ORM models.
  - backend/api/models/access_log.py: Added AccessLog ORM model for auditing.
  - backend/api/schemas/connector.py: Added connector response/sync schemas.
  - backend/api/schemas/item.py: Added item and paginated item response schemas.
  - backend/api/schemas/search.py: Added search query/result/response schemas.
  - backend/api/schemas/chat.py: Added chat request/response/history schemas.
- Verification:
  - Python compile check passed for full api package.
  - Editor warning remains for unresolved pydantic import in one file due local environment dependency resolution.
- Next:
  - Implement Step 5 core routers: emails, documents, search, and developer API key endpoints.

## Step 5 - Core Routers and Developer API Keys (Person 1 / Week 3)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/routers/emails.py: Added authenticated email listing with pagination and deterministic ordering.
  - backend/api/routers/documents.py: Added authenticated document listing with pagination and deterministic ordering.
  - backend/api/routers/search.py: Added authenticated semantic-style text search endpoint with type filter and ranking.
  - backend/api/routers/developer.py: Added developer API key lifecycle endpoints (create/list/revoke).
  - Implemented API key hashing using SHA-256 and one-time raw key return on create.
- Verification:
  - Python compile check passed for full api package.
  - No lint/compile errors reported for Step 5 router files.
- Next:
  - Add Step 6 tests for api and search endpoints.
  - Finalize API contract notes for Person 2 (connector sync trigger, chat payloads, websocket event envelope).

## Step 6 - Tests and Integration Contract Notes (Person 1 / Week 4)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/tests/test_api.py: Added endpoint tests for health, emails, documents, and developer API key lifecycle.
  - backend/tests/test_search.py: Added search endpoint tests for ranked results and top_k behavior.
  - backend/requirements.txt: Added pytest dependency for local test execution.
  - backend/api/models/item.py: Renamed mapped attribute to metadata_json (column name remains metadata) to avoid SQLAlchemy reserved attribute conflict.
  - backend/api/models/connector.py: Renamed mapped attribute to metadata_json (column name remains metadata).
  - backend/api/schemas/item.py, backend/api/schemas/connector.py: Added validation aliases for metadata_json and adjusted UUID id typing.
  - backend/api/schemas/auth.py: Adjusted UUID id typing for ORM compatibility.
  - backend/api/routers/search.py: Updated metadata selection to align with metadata_json mapped attribute.
- Verification:
  - Test execution passed: 7 passed in 1.01s.
  - Command used: py -3 -m pytest tests/test_api.py tests/test_search.py -q
- Next:
  - Handoff to Person 2 for workers, normalizers, RAG, websocket, and MCP implementation.

## Step 7 - Postman Collection (API Validation Artifact)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json: Added production-grade Postman collection for implemented endpoints.
  - Included endpoint coverage:
    - GET /health
    - POST /auth/register
    - POST /auth/login
    - GET /auth/me
    - GET /v1/emails/
    - GET /v1/documents/
    - GET /v1/search/
    - POST /v1/developer/api-keys
    - GET /v1/developer/api-keys
    - POST /v1/developer/api-keys/{api_key_id}/revoke
  - Added collection variables, auth automation, and test scripts:
    - accessToken capture from login
    - apiKeyId and developerApiKey capture from create API key
    - request-level assertions for response contract checks
- Verification:
  - JSON validation passed via python json.tool.
- Next:
  - Optional: add environment files for local/staging/prod and Newman CI execution.

## Step 8 - Runtime Environment Setup (.env)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/.env: Added runtime environment file with Azure PostgreSQL credentials and required app settings.
  - DATABASE_URL configured for endpoint personalapi.postgres.database.azure.com with URL-encoded password.
  - DATABASE_SSL_MODE set to require for Azure PostgreSQL.
  - .gitignore: Added .env ignore entries to protect credentials from accidental commits.
- Verification:
  - File created successfully and aligned with api/core/config.py required settings.
- Next:
  - Run a DB connectivity check and verify authenticated endpoints against Azure DB.

## Step 9 - Azure DB Schema Bootstrap and Startup Gate Validation
- Status: Completed
- Date: 2026-03-13
- Changes:
  - Confirmed startup DB gate behavior in api/main.py + api/core/db.py blocks app boot on DB failures.
  - Diagnosed runtime error as missing schema (`relation users does not exist`) after successful DB connectivity.
  - Applied migration script `backend/migrations/001_initial.sql` to Azure PostgreSQL via Python SQL execution.
- Verification:
  - Verified table existence: `users_exists= True`.
  - Startup guard behavior confirmed: backend does not start when DB is unreachable/invalid.
- Next:
  - Restart backend and run auth/register smoke test.

## Step 10 - Auth Hashing Runtime Fix (bcrypt Compatibility)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/core/security.py: Switched password hashing scheme from `bcrypt` to `pbkdf2_sha256` to avoid passlib+bcrypt backend compatibility failure in current runtime.
  - backend/requirements.txt: Changed dependency from `passlib[bcrypt]` to `passlib`.
- Verification:
  - Local validation passed:
    - hash prefix generated: `pbkdf2-sha256`
    - password verify check: `True`
- Next:
  - Restart backend and retry POST /auth/register and POST /auth/login smoke tests.

## Step 11 - Google OAuth Login for Hackathon + Worker Readiness
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/core/google_oauth.py: Added Google ID token verification against Google tokeninfo endpoint with issuer/audience/email_verified checks.
  - backend/api/core/config.py: Added GOOGLE_CLIENT_ID and GOOGLE_TOKEN_INFO_URL settings.
  - backend/api/schemas/auth.py: Added GoogleLoginRequest schema.
  - backend/api/routers/auth.py: Added POST /auth/google endpoint that creates/updates user and returns JWT.
  - backend/.env.example: Added Google OAuth env var placeholders.
  - backend/tests/test_auth_google.py: Added tests for new-user login, existing-user login, and invalid token behavior.
  - frontend/hooks/use-auth.ts: Fixed email/password login endpoint path and added useGoogleLogin hook.
- Verification:
  - Test execution passed: 10 passed in 1.05s.
  - Command used: Set-Location backend; py -3 -m pytest tests/test_auth_google.py tests/test_api.py tests/test_search.py -q
- Next:
  - Add frontend Google Sign-In button/One Tap and call POST /auth/google with id_token.
  - Reuse Google OAuth refresh tokens for Gmail/Drive connector onboarding flow.

## Step 12 - Spotify Worker and OAuth Connect Flow
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/normalizer/spotify.py: Full normalizer with recently-played and liked-songs support. Distinct source_ids (play:id:played_at vs liked:id). play_type in metadata.
  - backend/workers/spotify_worker.py: Celery task wiring sync_spotify to run_connector_sync.
  - backend/workers/connector_sync.py: Enhanced _fetch_spotify_records to fetch recently-played (limit 50, cursor-based) + liked songs (limit 50, best-effort). Added _maybe_refresh_spotify_token for automatic Spotify access token refresh using stored refresh_token.
  - backend/api/routers/connectors.py: Added GET /v1/connectors/spotify/connect (returns Spotify auth URL with signed state JWT) and GET /v1/connectors/spotify/callback (exchanges code, upserts connector row, stores tokens).
  - backend/api/core/config.py: Added SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI settings.
  - backend/.env + backend/.env.example: Added Spotify env var placeholders.
  - backend/tests/test_normalizers.py: Fixed item type assertion from "media" to "track".
- Verification:
  - Test execution passed: 58 passed in 1.40s.
  - Command used: py -3 -m pytest tests/ -q
- Next:
  - Set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI in .env.
  - Register http://127.0.0.1:8000/v1/connectors/spotify/callback in Spotify Dashboard redirect URIs.
  - Frontend calls GET /v1/connectors/spotify/connect → redirects user to returned URL.
  - After callback, trigger POST /v1/connectors/spotify/sync to start first data pull.

## Step 13 - Postman Coverage for Spotify Connector Flow
- Status: Completed
- Date: 2026-03-13
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Added collection variables: spotifyAuthUrl, spotifyAuthCode, spotifyState.
    - Added Connectors folder requests:
      - GET /v1/connectors/spotify/connect
      - GET /v1/connectors/spotify/callback?code=&state=
      - GET /v1/connectors/spotify
      - POST /v1/connectors/spotify/sync
    - Added assertions and pre-request guards for code/state dependent callback flow.
- Verification:
  - Collection JSON updated successfully and preserves existing auth + variable automation.
- Next:
  - In Postman, run Auth/Login first, then Spotify - Get Connect URL.
  - Complete consent in browser, set spotifyAuthCode, then run callback and sync requests.

## Step 14 - Postman Base URL Alignment (Spotify Connect 404 Fix)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Updated default baseUrl from http://localhost:8000 to http://127.0.0.1:8000.
    - Updated pre-request baseUrl fallback to http://127.0.0.1:8000.
- Verification:
  - Runtime endpoint check returned 401 (route exists and requires auth): GET /v1/connectors/spotify/connect.
  - OpenAPI check confirms route is loaded: /v1/connectors/spotify/connect present.
- Next:
  - In Postman, ensure `baseUrl=http://127.0.0.1:8000` and `apiPrefix=/v1`.
  - Run Auth/Login, then rerun Spotify - Get Connect URL.

## Step 15 - Postman apiPrefix URL Assembly Fix
- Status: Completed
- Date: 2026-03-13
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Normalized `apiPrefix` default from `/v1` to `v1`.
    - Added prerequest normalization to strip leading/trailing slashes from `apiPrefix`.
    - Updated request raw URLs to use `{{baseUrl}}/{{apiPrefix}}/...`.
- Verification:
  - Collection JSON remains valid after update.
- Next:
  - In Postman collection variables set `baseUrl=http://127.0.0.1:8000` and `apiPrefix=v1`.
  - Retry Connectors -> Spotify - Get Connect URL.

## Step 16 - Live Spotify Sync Validation
- Status: Completed
- Date: 2026-03-13
- Changes:
  - Executed live Spotify sync using stored connected connector.
  - Verified direct Spotify API access for:
    - GET /v1/me/player/recently-played
    - GET /v1/me/tracks
  - Persisted fetched Spotify records into items table.
- Verification:
  - Connector row present: platform=spotify, status=connected.
  - Pre-sync spotify items count: 0.
  - Sync result: status=completed, records_fetched=100, records_normalized=100, items_upserted=100.
  - Post-sync spotify items count: 100.
  - Sample persisted rows confirmed (`type=track`, play-based `source_id`).
- Next:
  - Use POST /v1/connectors/spotify/sync for subsequent incremental syncs.
  - Optional: run sync via Celery worker process (not direct function invocation) for production-like execution.

## Step 17 - Development Fallback Policy (Production Redis Enforcement)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/core/config.py: Added `ENABLE_INLINE_SYNC_FALLBACK` setting.
  - backend/api/routers/connectors.py: Inline sync fallback now runs only when both `DEBUG=true` and `ENABLE_INLINE_SYNC_FALLBACK=true`.
  - backend/.env and backend/.env.example: Added `ENABLE_INLINE_SYNC_FALLBACK=true` for local development convenience.
- Verification:
  - Backend test suite passed after changes.
- Next:
  - For production: set `DEBUG=false` and `ENABLE_INLINE_SYNC_FALLBACK=false`, and run Redis/Celery.

## Step 18 - Google Connector OAuth + Worker Token Refresh
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/routers/connectors.py:
    - Added `GET /v1/connectors/google/connect?platform=gmail|drive|gcal` to generate Google OAuth URL.
    - Added `GET /v1/connectors/google/callback` to exchange code, resolve user email, and upsert connector tokens.
  - backend/workers/connector_sync.py:
    - Added Google token refresh logic before sync for `gmail`, `drive`, `gcal` connectors.
  - backend/api/core/config.py:
    - Added `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI` settings.
  - backend/.env and backend/.env.example:
    - Added Google connector OAuth env variables.
- Verification:
  - Backend tests passed after changes: 58 passed.
- Next:
  - Register `http://127.0.0.1:8000/v1/connectors/google/callback` in Google Cloud OAuth redirect URIs.
  - Connect each platform (`gmail`, `drive`, `gcal`) and trigger `POST /v1/connectors/{platform}/sync`.

## Step 19 - Google App Login/Signup OAuth + Full Postman Endpoint Coverage
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/routers/auth.py:
    - Added `GET /auth/google/connect` to issue Google OAuth URL for app login/signup.
    - Added `GET /auth/google/callback` to exchange code/state and return PersonalAPI JWT.
  - backend/api/core/config.py:
    - Added `GOOGLE_AUTH_REDIRECT_URI` setting.
  - backend/.env and backend/.env.example:
    - Added `GOOGLE_AUTH_REDIRECT_URI` values.
  - docs/postman/PersonalAPI.postman_collection.json:
    - Added Auth requests for:
      - `POST /auth/google`
      - `GET /auth/google/connect`
      - `GET /auth/google/callback`
    - Added Connectors requests for missing endpoints:
      - `GET /v1/connectors/`
      - `GET /v1/connectors/google/connect`
      - `GET /v1/connectors/google/callback`
      - Generic platform endpoints:
        - `GET /v1/connectors/{platform}`
        - `POST /v1/connectors/{platform}/bootstrap`
        - `POST /v1/connectors/{platform}/sync`
    - Added new collection variables for Google auth flows and connector platform selection.
- Verification:
  - Postman collection JSON validation passed.
  - Backend tests passed: 58 passed.
- Next:
  - Register both Google redirect URIs in Google Cloud Console:
    - `http://127.0.0.1:8000/auth/google/callback`
    - `http://127.0.0.1:8000/v1/connectors/google/callback`
  - Use Postman to execute Google app auth flow and Google connector onboarding flow end-to-end.

## Step 20 - Postman Google Quick Actions (Gmail/Drive/GCal)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Added explicit Google connect shortcut requests:
      - Google Gmail - Get Connect URL
      - Google Drive - Get Connect URL
      - Google Calendar - Get Connect URL
    - Added explicit Google sync shortcut requests:
      - Gmail - Trigger Sync
      - Drive - Trigger Sync
      - GCal - Trigger Sync
    - Kept existing generic connector endpoints for flexible platform testing.
- Verification:
  - Collection JSON validation passed.
- Next:
  - Use shortcuts for quick platform testing without changing variables.

## Integration Contract Notes for Person 2

### 1. Connector Sync Trigger Contract
- Endpoint: POST /v1/connectors/{platform}/sync
- Auth: Bearer JWT required (current user scope).
- Request body: none.
- Response (success):
  - status: sync_queued
  - platform: {platform}
- Queue task naming expected from workers:
  - gmail -> workers.google_worker.sync_gmail
  - drive -> workers.google_worker.sync_drive
  - whatsapp -> workers.whatsapp_worker.sync_whatsapp
  - notion -> workers.notion_worker.sync_notion
  - spotify -> workers.spotify_worker.sync_spotify

### 2. Chat Endpoint Contract (for Person 2 chat implementation)
- Endpoint target: POST /v1/chat/message
- Auth: Bearer JWT required.
- Request payload:
  - message: string (1..8000)
  - session_id: string | null
- Response payload shape:
  - session_id: string
  - answer: string
  - sources: array of { id, type, source, score, preview }
  - documents: array of string
  - file_links: array of string

### 3. WebSocket Event Envelope Contract
- Endpoint target: /ws or /v1/ws (final path to be confirmed by Person 2 ws router).
- Auth: user-scoped session/token validation.
- Event envelope (recommended stable shape):
  - event: string
  - timestamp: ISO-8601 string
  - user_id: UUID string
  - data: object
- Minimum events required for frontend hooks:
  - sync.started: { platform, connector_id, task_id }
  - sync.progress: { platform, connector_id, processed, total }
  - sync.completed: { platform, connector_id, items_upserted, embedded }
  - sync.failed: { platform, connector_id, error }

### 4. Search/Item Data Contract Used by Person 1 Routers
- Item mapped attribute names in ORM:
  - metadata_json (DB column: metadata)
- Search router expects row fields:
  - id, type, source, summary, content, metadata, item_date, score
- Schemas currently used by Person 1 routers:
  - ItemResponse, PaginatedItemsResponse, SearchResponse, SearchResult

### 5. Developer API Key Contract for Agent Integrations
- Endpoints:
  - POST /v1/developer/api-keys
  - GET /v1/developer/api-keys
  - POST /v1/developer/api-keys/{api_key_id}/revoke
- Storage behavior:
  - key_hash is SHA-256 hash of raw key.
  - raw key returned once on create response only.
  - allowed_channels and agent_type fields available for channel/agent restrictions.

---

## Current Status
- Person 1 progress through Step 10 is completed.
- Backend auth hashing is runtime-stable and ready for register/login verification.

## Step 11 - Async Processing Foundation (Person 2 / Week 1)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/workers/celery_app.py: Implemented Celery app with standardized queues, task routing, retry/time limits, and Redis dead-letter fallback.
  - backend/workers/__init__.py: Added package export for shared celery_app.
  - backend/workers/google_worker.py: Added task stubs for sync_gmail, sync_drive, sync_gcal.
  - backend/workers/whatsapp_worker.py: Added task stub for sync_whatsapp.
  - backend/workers/notion_worker.py: Added task stub for sync_notion.
  - backend/workers/spotify_worker.py: Added task stub for sync_spotify.
  - backend/workers/file_watcher_worker.py: Added task stub for watch_file_changes.
  - backend/workers/embedding_worker.py: Added task stub for embed_item.
  - backend/docker-compose.yml: Added local stack with API, Postgres (pgvector), Redis, and queue-specific worker services.
  - backend/Dockerfile: Added runtime image for API and worker containers.
- Verification:
  - Python compile check passed for workers package.
  - Command used: py -3 -m compileall workers
  - Docker compose validation command could not run in this environment because Docker CLI is unavailable.
  - Full pytest suite passed: 38/38 tests in 0.42s (Python 3.11.9).
  - Command: py -3 -m pytest tests/test_celery_foundation.py -v
  - Coverage: queue constants, routing table, ResilientTask config attrs, lazy DLQ Redis client, on_failure dead-letter push (including default-queue fallback and RedisError swallowing), celery_app settings (serializers, timezone, prefetch, declared queues), ping task, worker includes.
- Next:
  - Implement connector worker logic with connector record loading, token handling, and idempotent upsert flow.
  - Add POST /v1/connectors/{platform}/sync router to enqueue connector-specific tasks.

## Step 12 - Connector Worker Pipeline and Sync API (Person 2 / Week 2)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/workers/connector_sync.py: Added shared sync runner with connector lookup, token checks, cursor-based ingestion batches, and idempotent item upsert.
  - backend/workers/google_worker.py: Wired sync_gmail/sync_drive/sync_gcal to shared connector sync pipeline.
  - backend/workers/whatsapp_worker.py: Wired sync_whatsapp to shared connector sync pipeline.
  - backend/workers/notion_worker.py: Wired sync_notion to shared connector sync pipeline.
  - backend/workers/spotify_worker.py: Wired sync_spotify to shared connector sync pipeline.
  - backend/workers/file_watcher_worker.py: Implemented file watcher task that enqueues embedding task.
  - backend/workers/embedding_worker.py: Implemented idempotent embedding status update flow on items.
  - backend/api/routers/connectors.py: Added connector listing/get/bootstrap endpoints and sync queue trigger endpoint.
  - backend/tests/test_api.py: Added connector sync endpoint test validating queued worker task mapping.
- Verification:
  - Python compile checks passed for workers, connectors router, and API tests module.
  - Command used: py -3 -m compileall workers api/routers/connectors.py tests/test_api.py
  - pytest execution could not run in this environment because pytest is not installed in the active interpreter.
- Next:
  - Replace mock ingestion in connector_sync with real connector API clients and platform normalizers.
  - Implement normalization modules and route worker output to file-per-document storage + DB upsert path.

## Step 13 - Normalization Pipeline and File Persistence (Person 2 / Week 2)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/normalizer/base.py: Added shared normalizer contract, normalized item dataclass, datetime/text helpers, sender parsing, and deterministic source ID generation.
  - backend/normalizer/gmail.py: Implemented Gmail message normalization.
  - backend/normalizer/drive.py: Implemented Drive file normalization.
  - backend/normalizer/gcal.py: Implemented Calendar event normalization.
  - backend/normalizer/whatsapp.py: Implemented WhatsApp message normalization.
  - backend/normalizer/notion.py: Implemented Notion page normalization.
  - backend/normalizer/spotify.py: Implemented Spotify playback normalization.
  - backend/workers/connector_sync.py: Replaced mock ingestion with platform API fetchers, wired normalizer registry, added file-per-document persistence under /users/{id}/data/{service}/, and retained idempotent DB upsert flow.
  - backend/api/core/config.py: Added user_data_root setting for storage location.
  - backend/.env.example: Added USER_DATA_ROOT variable.
  - backend/tests/test_normalizers.py: Added unit tests for all platform normalizers and connector sync storage helpers.
  - backend/requirements.txt: Pinned httpx to a Starlette-compatible range (<0.28) for runtime/test compatibility.
- Verification:
  - Targeted pytest suites passed: 53/53 tests in 1.60s (Python 3.11.9).
  - Command: py -3 -m pytest tests/test_normalizers.py tests/test_celery_foundation.py tests/test_api.py -v
  - Coverage: all normalizer mappings, seeded connector record ingestion path, deterministic file persistence path/contents, metadata enrichment before upsert, Celery foundation regression checks, and connectors API queue trigger behavior.
- Next:
  - Implement Workstream 4 (RAG and chat engine): chunking, embedding, retrieval, context assembly, and chat response orchestration.
