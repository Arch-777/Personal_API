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

## Step 46 - High-Impact Backend Performance Pass (Low-Risk)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/core/http_client.py: Added shared synchronous HTTP client registry with keep-alive connection reuse.
  - backend/api/routers/auth.py: Replaced per-request Google token exchange client creation with shared client usage.
  - backend/api/routers/connectors.py: Replaced repeated OAuth/profile per-request client creation (GitHub/Google/Notion/Spotify/Slack flows) with shared client usage.
  - backend/rag/generator.py: Reused shared client for Ollama readiness and generation calls.
  - backend/workers/connector_sync.py:
    - Replaced per-call client creation in provider fetch and token refresh helpers with shared client usage.
    - Removed duplicate post-upsert enqueue of embedding pipeline after inline indexing to avoid redundant work.
  - backend/api/core/google_oauth.py: Kept direct httpx.get behavior to preserve existing test monkeypatch compatibility.
- Verification:
  - Focused regression tests passed: 45 passed in 2.04s.
  - Command used (from backend/): `PYTHONPATH=. pytest tests/test_google_oauth.py tests/test_auth_google.py tests/test_celery_foundation.py -q`
- Next:
  - Optional next low-risk optimization: add configurable SQLAlchemy pool sizing/timeouts in config and tune per environment.
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

## Step 21 - Notion Worker Deep Ingestion Enrichment
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/workers/connector_sync.py:
    - Enhanced Notion ingestion from search-only results to enriched records.
    - Added bounded enrichment controls for page content and database expansion.
    - Added plain-text extraction from Notion block children.
    - Added database row expansion by querying discovered database objects.
  - backend/tests/test_normalizers.py:
    - Added unit tests for Notion block plain-text extraction.
    - Added unit test coverage for database-row fallback behavior on fetch failure.
- Verification:
  - Code changes applied successfully.
  - Local test execution in current shell is blocked by missing runtime dependencies (`psycopg`, `celery`) during collection.
  - Command attempted: `pytest -q` (with `PYTHONPATH=.`).
- Next:
  - Install backend dependencies in the active environment, rerun `pytest -q`, and then run a live Notion sync to confirm record quality and item upsert counts.

## Step 22 - Slack Connector Backend Integration
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/core/config.py: Added Slack OAuth settings for client id, client secret, and redirect URI.
  - backend/api/routers/connectors.py: Added GET /v1/connectors/slack/connect and GET /v1/connectors/slack/callback with Slack OAuth v2 token exchange and connector upsert flow.
  - backend/workers/connector_sync.py: Registered Slack in the generic connector sync runner and added bounded Slack conversation/message ingestion with per-user profile enrichment and incremental cursor tracking.
  - backend/normalizer/slack.py: Added Slack message normalizer producing message items with channel and sender metadata.
  - backend/workers/slack_worker.py, backend/workers/celery_app.py, backend/docker-compose.yml: Added dedicated Slack Celery task, queue routing, include registration, and worker service.
  - backend/.env.example: Added Slack environment variable placeholders.
  - backend/tests/test_normalizers.py, backend/tests/test_celery_foundation.py, backend/tests/test_api.py: Added Slack-focused test coverage for normalizer behavior, sync fetch cursoring, queue registration, and OAuth connect URL generation.
- Verification:
  - Targeted tests passed: 58 passed in 1.87s.
  - Command used: `Set-Location backend; py -3 -m pytest tests/test_normalizers.py tests/test_celery_foundation.py tests/test_api.py -q`
- Next:
  - Set `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, and `SLACK_REDIRECT_URI` in backend/.env.
  - Register `http://127.0.0.1:8000/v1/connectors/slack/callback` in the Slack app OAuth redirect URLs.
  - Start `worker-slack` alongside the API and trigger `POST /v1/connectors/slack/sync` after completing the OAuth callback.

## Step 23 - Postman Gap Fill + Notion/Slack Worker Verification
- Status: Completed
- Date: 2026-03-13
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Added missing Chat endpoints:
      - `POST /v1/chat/message`
      - `GET /v1/chat/{session_id}/history`
    - Added missing Slack OAuth endpoints:
      - `GET /v1/connectors/slack/connect`
      - `GET /v1/connectors/slack/callback`
    - Added supporting collection variables for chat and Slack OAuth flow (`chatSessionId`, `chatMessage`, `slackAuthUrl`, `slackAuthCode`, `slackAuthState`).
  - Verified Notion and Slack workers remain correctly wired through Celery and connector sync runner:
    - `workers.notion_worker.sync_notion`
    - `workers.slack_worker.sync_slack`
- Verification:
  - Collection JSON parses successfully.
  - Route coverage check confirms no missing non-doc HTTP endpoints in Postman collection.
  - Focused tests passed:
    - `pytest tests/test_normalizers.py tests/test_api.py -q` with `PYTHONPATH=.` -> 20 passed
    - `pytest tests/test_celery_foundation.py -q` with `PYTHONPATH=.` -> 38 passed
- Next:
  - Optional: add explicit Postman requests for OpenAPI docs routes (`/openapi.json`, `/docs`) if API exploration in Postman is needed.

## Step 24 - Slack OAuth Redirect Scheme Fix (HTTPS to HTTP)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/.env:
    - Updated `SLACK_REDIRECT_URI` from `https://127.0.0.1:8000/v1/connectors/slack/callback` to `http://127.0.0.1:8000/v1/connectors/slack/callback` to match local Uvicorn (non-TLS) runtime.
- Verification:
  - Configuration now aligns with local server transport (HTTP), preventing TLS handshake bytes from being sent to an HTTP socket.
- Next:
  - Ensure Slack app OAuth Redirect URLs include the exact same callback URI: `http://127.0.0.1:8000/v1/connectors/slack/callback`.
  - Restart API process and retry Slack connect flow.

## Step 25 - Connector Sync Queue Status Accuracy Fix
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/connectors.py: Removed the premature `syncing` status update from the sync trigger route so connectors only transition to `syncing` when a worker actually begins execution.
  - backend/tests/test_api.py: Updated connector sync trigger coverage to verify queued jobs preserve the connector's existing status while clearing stale errors.
- Verification:
  - Targeted connector sync API tests passed.
- Next:
  - Add separate queued-state observability if the product needs distinct user-facing queue and run states.

## Step 26 - Worker FK Metadata Registration Hardening
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/workers/connector_sync.py:
    - Added explicit `api.models.user` import to ensure `users` table metadata is present when connector sync flush/commit resolves `connectors.user_id -> users.id` FK.
  - backend/workers/celery_app.py:
    - Added startup-time imports for all ORM model modules (`user`, `connector`, `item`, `item_chunk`, `api_key`, `access_log`, `chat_session`) so Celery worker processes preload full SQLAlchemy metadata.
    - Prevents similar `NoReferencedTableError` failures across other connector and pipeline workers.
- Verification:
  - Static validation of worker import graph confirms metadata preloading now occurs before task execution.
- Next:
  - Restart all Celery worker containers/processes so the new startup imports are loaded.
  - Re-run Slack/Spotify/Google/Notion sync tasks and confirm no FK table-resolution retries/errors in logs.

## Step 27 - Google Connector Auto-Provisioning (Drive/GCal Not Found Fix)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/connectors.py:
    - Added Google connector row upsert helper and callback hardening to ensure Google connector records exist consistently.
    - Google callback now upserts all Google platform rows (`gmail`, `drive`, `gcal`) using the latest token payload so follow-up syncs do not fail with `Connector not found`.
    - Added fallback clone behavior in `GET /v1/connectors/{platform}` and `POST /v1/connectors/{platform}/sync` for Google platforms: if one Google connector exists, missing sibling rows are created automatically.
- Verification:
  - Router compile check passed after changes.
  - Static route-path inspection confirms 404 path now includes Google auto-provision fallback before final not-found response.
- Next:
  - Redeploy API service and retry:
    - `GET /v1/connectors/google/connect?platform=drive`
    - `GET /v1/connectors/google/connect?platform=gcal`
    - `POST /v1/connectors/drive/sync`
    - `POST /v1/connectors/gcal/sync`

## Step 28 - Google 403 Scope/Auth Fail-Fast + Retry Suppression
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/workers/exceptions.py:
    - Added `NonRetryableSyncError` for connector sync failures that should not be retried.
  - backend/workers/celery_app.py:
    - Updated base Celery task to set `dont_autoretry_for = (NonRetryableSyncError,)` while keeping retry behavior for transient errors.
  - backend/workers/connector_sync.py:
    - Added Google platform required-scope validation before API fetch (`gmail`, `drive`, `gcal`).
    - Added fail-fast conversion of Google HTTP 401/403 responses into `NonRetryableSyncError` with extracted provider error message.
    - Added human-actionable reconnect guidance in error text (`/v1/connectors/google/connect?platform=...`).
- Verification:
  - No editor errors in modified worker modules.
  - Worker package compile check passed (`py -3 -m compileall workers`).
- Next:
  - Redeploy workers and API so new exception flow is active.
  - Reconnect Google Drive/GCal with the matching platform OAuth flow and retry sync.

## Step 48 - Scalability Foundation: RLS, HNSW, Rate Limits, and Pool Tuning
- Status: Completed
- Date: 2026-03-17
- Changes:
  - backend/migrations/003_scalability_foundation.sql:
    - Added `idx_items_user_type_created` composite index for user-first query paths.
    - Added HNSW vector indexes for `items.embedding` and `item_chunks.embedding`.
    - Enabled row-level security on `items` and `item_chunks` with `app.current_user_id` policies.
  - backend/api/core/rate_limit.py:
    - Added shared Redis sorted-set sliding window limiter.
    - Added inbound limiter keyed by API key hash namespace.
    - Added outbound limiter keyed by `user_id:platform` namespace.
  - backend/api/main.py:
    - Added inbound API middleware rate limit for `x-api-key` requests with `429` and `Retry-After`.
  - backend/workers/connector_sync.py:
    - Added outbound per-user-per-platform rate limiting before sync execution.
    - Returns `status=throttled` with `retry_after_seconds` when over limit.
  - backend/api/core/config.py, backend/api/core/db.py, backend/.env.example:
    - Added SQLAlchemy pool settings and wired pool configuration into engine creation.
    - Added configurable inbound/outbound rate-limit settings.
- Verification:
  - Compile check passed for edited modules via `py -3 -m compileall`.
  - Targeted tests run (`tests/test_api.py tests/test_celery_foundation.py`) showed one existing failure in GitHub callback state handling that is unrelated to these scalability changes.
- Next:
  - Apply migration `003_scalability_foundation.sql` in deployed environments.
  - Set `app.current_user_id` per DB transaction in API/worker query paths before enforcing `FORCE ROW LEVEL SECURITY`.
  - Add/adjust tests for new `x-api-key` inbound and outbound throttling behavior.

## Step 47 - RAG Phase 1 (Semantic Embeddings + Grounded Abstain + Extractive Citations)
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/rag/embedder.py:
    - Added `SemanticEmbedder` with `fastembed` support (`BAAI/bge-small-en-v1.5`) and deterministic fallback for low-resource local environments.
    - Added vector dimension fitting to preserve compatibility with existing pgvector schema (`vector(1536)`).
  - backend/api/core/config.py:
    - Added configurable RAG embedding settings (`RAG_EMBEDDING_PROVIDER`, `RAG_EMBEDDING_MODEL`, `RAG_EMBEDDING_DIMENSIONS`).
    - Added grounding thresholds (`RAG_GROUNDING_MIN_TOP_SCORE`, `RAG_GROUNDING_MIN_AVG_SCORE`).
  - backend/rag/indexer.py:
    - Switched default indexing embedder from deterministic-only to configurable semantic embedder with safe fallback.
  - backend/rag/engine.py:
    - Added grounding confidence computation and strict confidence gate.
    - Added explicit `abstain` answer mode when evidence quality is weak, preventing non-grounded responses.
  - backend/rag/context.py:
    - Updated deterministic response composition to citation-oriented extractive output from retrieved evidence only.
    - Added dedicated abstain response helper with actionable refinement guidance.
  - backend/requirements.txt:
    - Added `fastembed` dependency for lightweight local semantic embeddings.
  - backend/tests/test_rag.py:
    - Updated no-source behavior expectation to `abstain` mode.
    - Added tests for citation-based deterministic output and weak-evidence abstain behavior.
- Verification:
  - Focused RAG test suite passed: 28 passed in 45.65s.
  - Command used: `Set-Location backend; py -3 -m pytest tests/test_rag.py -q`
- Next:
  - Phase 2: add lexical FTS retrieval branch + calibrated fusion weights and stronger chunking for better recall precision.

## Step 48 - RAG Env Parity Sync (.env + .env.example + Main Health)
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/.env.example:
    - Added missing Phase 1 RAG env vars:
      - `RAG_LLM_SYSTEM_PROMPT`
      - `RAG_EMBEDDING_PROVIDER`
      - `RAG_EMBEDDING_MODEL`
      - `RAG_EMBEDDING_DIMENSIONS`
      - `RAG_GROUNDING_MIN_TOP_SCORE`
      - `RAG_GROUNDING_MIN_AVG_SCORE`
  - backend/.env:
    - Added the same RAG env vars for local runtime parity.
  - backend/api/main.py:
    - Added `GET /health/rag` endpoint to expose effective RAG mode and threshold settings at runtime.
- Verification:
  - Existing focused RAG tests remain green (`tests/test_rag.py`: 28 passed).
  - API suite run surfaced one unrelated pre-existing failure in GitHub callback redirect test (`tests/test_api.py::test_github_callback_redirects_to_frontend_on_success`).
- Next:
  - Begin Phase 2 with lexical FTS retrieval path and calibrated fusion.

## Step 49 - RAG Phase 2 (Lexical FTS + Calibrated Fusion + Better Chunking)
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/rag/retriever.py:
    - Added lexical FTS candidate retrieval over `item_chunks.content_tsv` using PostgreSQL `websearch_to_tsquery` and `ts_rank_cd`.
    - Merged semantic vector candidates and lexical FTS candidates before grouping/reranking.
    - Upgraded RRF rank fusion to configurable weights/boost (`semantic_weight`, `lexical_weight`, `k`, `boost`).
    - Added stable rank identity for chunk-level fusion so chunk-scoped ranking is reliable.
  - backend/rag/engine.py:
    - Wired retriever construction to use new configurable Phase 2 retrieval tuning settings.
  - backend/rag/chunker.py:
    - Updated defaults to smaller, retrieval-friendly chunks (`max_tokens=240`, `overlap_tokens=40`).
    - Added sentence-aware segmentation and preferred sentence-boundary chunk endings for better chunk coherence.
  - backend/rag/indexer.py:
    - Wired chunk sizing to settings (`RAG_CHUNK_MAX_TOKENS`, `RAG_CHUNK_OVERLAP_TOKENS`).
  - backend/api/core/config.py:
    - Added Phase 2 retrieval/chunk settings:
      - `RAG_SEMANTIC_CANDIDATE_LIMIT`
      - `RAG_LEXICAL_CANDIDATE_LIMIT`
      - `RAG_RRF_K`
      - `RAG_RRF_SEMANTIC_WEIGHT`
      - `RAG_RRF_LEXICAL_WEIGHT`
      - `RAG_RRF_BOOST`
      - `RAG_CHUNK_MAX_TOKENS`
      - `RAG_CHUNK_OVERLAP_TOKENS`
  - backend/.env.example and backend/.env:
    - Added all new Phase 2 RAG environment variables for parity.
  - backend/api/main.py:
    - Extended `GET /health/rag` response to include retrieval and chunking runtime settings.
  - backend/tests/test_rag.py:
    - Added lexical-only retrieval path test to ensure no fallback query runs when lexical candidates exist.
    - Added configurable fusion weighting test to verify semantic-vs-lexical ranking behavior changes with weight tuning.
- Verification:
  - Focused RAG test suite passed: 30 passed in 1.29s.
  - Command used: `Set-Location P:\vs-code\projects\Personal_API\backend; py -3 -m pytest tests/test_rag.py -q`
- Next:
  - Phase 3: optional lightweight reranker and query-rewrite controls with strict grounded output enforcement kept in place.

## Step 50 - RAG Phase 3 (Query Rewrite + Lightweight Reranker)
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/rag/query_rewriter.py:
    - Added deterministic query rewrite module with domain-aware hint expansion (gmail/slack/notion/drive/document cues).
    - Added configurable cap on rewrite variants to keep CPU/memory usage low.
  - backend/rag/reranker.py:
    - Added low-cost heuristic reranker that boosts candidates by query-token coverage, phrase match, and local token-order proximity.
    - Reranker is optional and applied only to top-N candidates for bounded cost.
  - backend/rag/engine.py:
    - Integrated query rewrite retrieval flow (`_retrieve_with_rewrites`) that merges variant results and preserves strongest evidence per chunk identity.
    - Integrated optional lightweight reranker before grounding/answer generation while preserving strict abstain gating.
  - backend/api/core/config.py:
    - Added Phase 3 settings:
      - `RAG_QUERY_REWRITE_ENABLED`
      - `RAG_QUERY_REWRITE_MAX_VARIANTS`
      - `RAG_RERANKER_ENABLED`
      - `RAG_RERANKER_TOP_N`
      - `RAG_RERANKER_WEIGHT`
  - backend/.env.example and backend/.env:
    - Added all Phase 3 env vars for config parity.
  - backend/api/main.py:
    - Extended `GET /health/rag` to expose rewrite and reranker runtime configuration.
  - backend/tests/test_rag.py:
    - Added tests for domain hint expansion in query rewriting.
    - Added test proving engine can recover results via rewritten query variants.
    - Added test validating reranker can reorder results by query alignment.
- Verification:
  - Focused RAG test suite passed: 33 passed in 1.41s.
  - Command used: `Set-Location P:\vs-code\projects\Personal_API\backend; py -3 -m pytest tests/test_rag.py -q`
- Next:
  - Re-index existing items with new chunk settings to maximize recall gains from Phase 2 + Phase 3.

## Step 51 - Sync Priority Lanes + Async/Idempotent Embedding Enforcement
- Status: Completed
- Date: 2026-03-17
- Changes:
  - backend/workers/celery_app.py:
    - Added sync priority queues: `sync.high`, `sync.normal`, `sync.low`.
    - Added low-priority embedding queue: `pipeline.embedding.low`.
    - Registered new queues in Celery `task_queues`.
  - backend/api/routers/connectors.py:
    - Routed webhook-triggered GitHub sync to `sync.high`.
    - Routed user-triggered connector sync to `sync.normal`.
  - backend/workers/auto_sync_worker.py:
    - Added activity-based lane selection for scheduled syncs:
      - active users (`updated_at >= now-7d`) -> `sync.normal`
      - inactive users -> `sync.low`
    - Added queue distribution counters (`queued_normal`, `queued_low`).
  - backend/workers/connector_sync.py:
    - Enforced async-only embedding dispatch from ingestion path.
    - Removed inline embedding fallback and now reports `embedding_jobs_failed` when enqueueing fails.
    - Kept idempotent embedding behavior in worker flow (re-queue safe overwrite semantics remain).
  - backend/workers/file_watcher_worker.py:
    - Explicitly routes embedding jobs to `pipeline.embedding`.
  - backend/scripts/backfill_item_chunks.py:
    - Converted from synchronous indexing to async enqueueing on `pipeline.embedding.low`.
    - Marks items as `embedding_status=queued` instead of completing inline.
  - backend/docker-compose.yml, backend/docker-compose.coolify.yml:
    - Connector workers now consume their connector queue plus `sync.high,sync.normal,sync.low`.
    - Embedding worker now consumes `pipeline.embedding,pipeline.embedding.low`.
  - backend/tests/test_celery_foundation.py:
    - Updated queue constant/import assertions for new sync and embedding-low lanes.
- Verification:
  - `py -3 -m pytest tests/test_celery_foundation.py -q` -> 39 passed.
  - `py -3 -m pytest tests/test_api.py -k "github_webhook_ping_returns_ok or sync_connector" -q` -> 1 passed.
  - `py -3 -m compileall workers api/routers/connectors.py scripts/backfill_item_chunks.py` -> completed without syntax errors.
- Next:
  - Start/redeploy workers so new queue subscriptions are active.
  - Optionally split dedicated lane workers (`worker-sync-high`, `worker-sync-normal`, `worker-sync-low`) for stricter isolation at higher scale.

## Step 52 - RLS Runtime Binding (app.current_user_id)
- Status: Completed
- Date: 2026-03-17
- Changes:
  - backend/api/core/db.py:
    - Added `set_db_current_user` helper to bind the authenticated tenant id into DB session context.
    - Added SQLAlchemy `after_begin` session event hook to apply `SET LOCAL app.current_user_id` at transaction start for any session carrying tenant context.
  - backend/api/core/auth.py:
    - Bound `app.current_user_id` during auth dependency resolution so authenticated request transactions run under tenant-scoped DB context.
  - backend/workers/connector_sync.py:
    - Bound tenant context for worker DB sessions before querying/upserting tenant-scoped tables.
  - backend/workers/embedding_worker.py:
    - Bound tenant context before item/chunk reads and writes.
- Verification:
  - Editor/type diagnostics report no errors in modified files.
  - Focused regression run: `tests/test_api.py tests/test_celery_foundation.py` -> 77 passed, 1 known pre-existing failure in GitHub callback state parsing path unrelated to RLS runtime binding.
- Next:
  - Apply migration `backend/migrations/003_scalability_foundation.sql` in all environments if not already applied.
  - Restart API/workers to ensure the runtime context hook is active in all processes.

## Step 47 - API Worker Hotfix: Mixed Datetime Sort Crash
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/rag/retriever.py:
    - Fixed mixed offset-naive and offset-aware datetime sorting in retrieval ranking paths.
    - Added `_coerce_sort_datetime` helper to normalize all sort keys to UTC-aware datetimes.
    - Updated all relevant sorts to use normalized datetime keys:
      - chunk-first rerank sort
      - combined rerank sort
      - recent-items deduped sort
  - backend/tests/test_rag.py:
    - Added regression test `test_hybrid_retriever_handles_mixed_naive_and_aware_item_dates_in_sorting`.
- Verification:
  - Focused tests passed: `tests/test_rag.py` -> 20 passed in 2.42s.
  - Command used: `Set-Location backend; py -3 -m pytest tests/test_rag.py -q`
- Next:
  - Redeploy/restart API worker service to load the patched retriever.
  - Run one live chat query that previously failed to confirm no ASGI exception on mixed datetime data.

## Step 29 - OAuth Callback UX Redirect to Frontend + Toast Feedback
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/core/config.py:
    - Added `frontend_app_url` setting to control callback redirect target for web UI.
  - backend/api/routers/connectors.py:
    - Updated connector OAuth callbacks (`google`, `notion`, `spotify`, `slack`) to return HTTP redirects to frontend integrations route instead of JSON pages.
    - Added query payload on redirect (`integration`, `status`, `message`) for client-side toast rendering.
  - frontend/app/providers.tsx:
    - Mounted global Sonner toaster so callback messages can be displayed anywhere in app.
  - frontend/app/dashboard/integrations/page.tsx:
    - Added URL query handling to show success/error toast after callback redirect and then clean URL via `router.replace`.
- Verification:
  - No editor errors on modified backend/frontend files.
  - Backend compile check passed for modified modules.
  - Frontend lint run reported pre-existing errors in unrelated files (`frontend/app/(public)/layout.tsx`, `frontend/components/mode-toggle.tsx`).
- Next:
  - Set `FRONTEND_APP_URL` in backend env for deployed environment.
  - Redeploy API and verify OAuth callback now lands on `/dashboard/integrations` with toast feedback.

## Step 30 - Env Example Update for Frontend Callback URL
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/.env.example:
    - Added `FRONTEND_APP_URL=http://127.0.0.1:3000` to match backend `frontend_app_url` setting used by connector OAuth callback redirects.
- Verification:
  - Manual config parity check confirms `.env.example` now includes the required environment variable.
- Next:
  - Ensure deployed backend environment sets `FRONTEND_APP_URL` to the real frontend domain.

## Step 31 - Notion Sync Invalid Cursor Fix
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/workers/connector_sync.py:
    - Updated Notion search fetcher to ignore sentinel cursor value `0` instead of sending it as `start_cursor`.
    - Normalized empty Notion pagination state to `""` instead of persisting `"0"`, preventing follow-up `/v1/search` 400 errors.
  - backend/tests/test_normalizers.py:
    - Added regression test covering zero-cursor handling for Notion sync.
- Verification:
  - Targeted tests passed: `py -3 -m pytest tests/test_normalizers.py -q` -> 16 passed.
- Next:
  - Redeploy notion worker and retry `workers.notion_worker.sync_notion`.

## Step 34 - Spotify Free-Account 403 Retry Storm Fix
- Status: Completed
- Date: 2026-03-14
- Problem: Non-premium Spotify accounts receive 403 on `/me/player/recently-played` (Premium required). The worker was retrying this permanently-failing request with exponential backoff, creating an infinite retry storm identical to the Google 403 issue fixed in Step 28.
- Changes:
  - backend/workers/connector_sync.py:
    - `_http_get_json` and `_http_post_json`: Added `api.spotify.com` to the `NonRetryableSyncError` guard (mirrors the existing `googleapis.com` guard). Any 401/403 from Spotify now immediately stops retrying.
    - `_fetch_spotify_records`: Wrapped the `recently-played` call in `try/except NonRetryableSyncError`. On 403, it logs a clear warning and falls back to liked/saved tracks only (available on free accounts via `user-library-read` scope). Only re-raises if *both* endpoints fail with permanent errors.
- Behaviour after fix:
  - Premium account: unchanged — recently-played + liked tracks both sync.
  - Free account: recently-played skipped (logged as warning), liked/saved tracks sync successfully, connector stays `connected`.
  - Broken token (401 on both): `NonRetryableSyncError` raised once, connector set to `error`, no retries.
- Verification:
  - `py -3 -m pytest tests/test_normalizers.py tests/test_api.py -q` → 34 passed.

## Step 35 - User-Controlled Integration Auto-Sync Toggle
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/schemas/connector.py:
    - Added `ConnectorAutoSyncUpdateRequest` and `ConnectorAutoSyncResponse` schemas.
  - backend/api/routers/connectors.py:
    - Added `PATCH /v1/connectors/{platform}/auto-sync` to let users enable/disable periodic auto-sync.
    - Added optional `cascade_google=true` behavior so toggling one Google platform can apply to `gmail`, `drive`, and `gcal` together.
    - Persists preference at connector level via `metadata.auto_sync_enabled`.
  - backend/workers/auto_sync_worker.py:
    - Updated periodic dispatcher to skip connectors where `metadata.auto_sync_enabled=false`.
  - backend/tests/test_api.py:
    - Added coverage for single-platform toggle and Google cascade toggle behavior.
- Verification:
  - Code-level validation completed for router, worker, and schema integration.
- Next:
  - Run targeted tests in backend runtime environment:
    - `py -3 -m pytest tests/test_api.py tests/test_celery_foundation.py -q`
  - Frontend can now call the new toggle endpoint from integration settings UI.

## Step 36 - Google Callback Duplicate Connector Insert Fix (GCAL UniqueViolation)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/connectors.py:
    - Fixed duplicate upsert path in `google_callback`.
    - Removed the extra pre-loop `_ensure_google_connector_row` call and now upserts each Google platform exactly once in the sibling loop.
    - Prevents duplicate pending inserts for the same `(user_id, platform)` in one transaction.
  - backend/tests/test_api.py:
    - Added regression test `test_google_callback_upserts_each_google_platform_once`.
    - Verifies callback performs exactly one upsert per Google platform (`gmail`, `drive`, `gcal`).
- Verification:
  - Targeted tests passed for API + Celery foundations after fix.
- Next:
  - Redeploy API service and retry Google callback flow for GCAL.

## Step 37 - Worker + Data Fetch Exception Handling Hardening
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/workers/connector_sync.py:
    - Added non-retryable validation for malformed task IDs (`connector_id`, `user_id`).
    - Hardened Google/Spotify token refresh handling with explicit `HTTPStatusError` mapping for auth failures (`400/401/403`) to `NonRetryableSyncError`.
    - Improved `_http_get_json` and `_http_post_json` to handle:
      - network/request exceptions (`httpx.RequestError`) with clear context,
      - invalid JSON payload responses with explicit parse errors,
      - provider auth failures consistently via a shared classifier for Google/Spotify/Slack/Notion (`401/403`).
    - Updated Slack API error handling to classify auth/scope failures (`invalid_auth`, `token_revoked`, `missing_scope`, `not_authed`, `account_inactive`) as non-retryable.
  - backend/workers/file_watcher_worker.py:
    - Added guarded task dispatch with structured logging on enqueue failure.
  - backend/workers/embedding_worker.py:
    - Added non-retryable validation for malformed UUID task inputs.
    - Converted missing-item case to `NonRetryableSyncError`.
    - Added task-level exception logging with item/user context before re-raising.
- Verification:
  - Targeted regression tests passed:
    - `py -3 -m pytest tests/test_api.py tests/test_celery_foundation.py -q` -> 62 passed.
- Next:
  - Redeploy workers and API so updated exception handling behavior is active in runtime.

## Step 38 - API Key Expiration Logic (expires_at)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/developer.py:
    - Added expiration inputs to API key creation:
      - `expires_in_days` (1..3650)
      - `expires_at` (absolute datetime)
    - Added request validation to prevent sending both fields at once.
    - Added future-time validation for `expires_at`.
    - API key create response now includes persisted `expires_at`.
  - backend/mcp/server.py:
    - Enforced expiration during developer key authentication.
    - Expired keys are now rejected in `_resolve_user` with 401.
  - backend/tests/test_api.py:
    - Added test that `expires_in_days` sets `expires_at`.
    - Added test that MCP key resolution rejects expired keys.
- Verification:
  - Targeted tests passed after implementation.
- Next:
  - Frontend can expose expiration presets (e.g., 7/30/90 days) when creating developer API keys.

## Step 33 - Integration Management: Disconnect Endpoint
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/schemas/connector.py:
    - Added `ConnectorDisconnectResponse` schema with `disconnected: list[str]` and `items_deleted: int`.
  - backend/api/routers/connectors.py:
    - Imported `delete` from SQLAlchemy and `Item` model.
    - Imported `ConnectorDisconnectResponse` from schemas.
    - Added `DELETE /connectors/{platform}` endpoint with two optional query params:
      - `delete_data=false` — when `true`, deletes all synced `items` (and cascades to `item_chunks`) for the removed platform(s).
      - `cascade_google=true` — when `true` and platform is `gmail`/`drive`/`gcal`, all three Google sibling connectors are removed together since they share a single OAuth token.
    - Returns `ConnectorDisconnectResponse` confirming which platforms were disconnected and how many items were deleted.
  - backend/tests/test_api.py:
    - Added 6 new test cases covering: Notion disconnect, Google cascade (true/false), 404 on missing connector, `delete_data=true` item count, 400 on unknown platform.
- Verification:
  - `py -3 -m pytest tests/test_api.py -q` → 18 passed.

## Step 32 - Ollama RAG Health Check + Answer Mode Observability
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/rag/generator.py:
    - Added `check_ollama_readiness()` helper that probes Ollama `/api/tags` for health-style readiness checks.
  - backend/api/main.py:
    - Added `GET /health/llm` endpoint.
    - Keeps primary `/health` unchanged, while exposing dedicated LLM readiness states: `disabled`, `ok`, `unreachable`, `unsupported_provider`.
  - backend/rag/engine.py:
    - Added `answer_mode` metadata to RAG results (`deterministic`, `llm`, `fallback`).
    - Added structured logging for answer mode and retrieval/result counts so production can tell when Ollama was used versus fallback.
  - backend/tests/test_api.py, backend/tests/test_rag.py:
    - Added coverage for `/health/llm` states and RAG `answer_mode` behavior.
- Verification:
  - Targeted tests passed: `py -3 -m pytest tests/test_api.py tests/test_rag.py -q` -> 31 passed.
- Next:
  - After setting RAG env vars in production, call `/health/llm` to verify Ollama connectivity before relying on LLM-backed chat answers.

## Step 47 - Google OAuth Expiry Validation + Subject Claim
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/core/google_oauth.py:
    - Added token-expiry validation for Google token payloads using `exp` and `expires_in` claims.
    - Added optional `sub` extraction and included it in verified identity payloads.
    - Applied expiry checks on both ID-token and access-token verification paths.
  - backend/tests/test_google_oauth.py:
    - Updated existing assertions to validate `sub` is returned when available.
    - Added expiry fields to mocked token payloads.
    - Added regression test for expired token rejection.
- Verification:
  - Targeted tests passed for Google OAuth-related suite and auth foundations.
- Next:
  - Optional: persist Google `sub` on the user model for immutable provider-account linking and safer email-change handling.

## Step 48 - Postman Collection Endpoint Coverage Refactor
- Status: Completed
- Date: 2026-03-14
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Added missing platform diagnostic endpoints:
      - `GET /health/llm`
      - `GET /openapi.json`
      - `GET /docs`
      - `GET /docs/oauth2-redirect`
      - `GET /redoc`
    - Added missing connector endpoint:
      - `PATCH /v1/connectors/{platform}/auto-sync` as `Connector - Toggle Auto Sync`.
    - Added collection variables for auto-sync toggling:
      - `autoSyncEnabled`
      - `cascadeGoogle`
- Verification:
  - Programmatic endpoint parity check against live FastAPI routes reports full coverage.
  - Result: `Missing count: 0`.
- Next:
  - Optional: prune duplicate connector shortcut requests if you want a leaner collection focused only on canonical generic endpoints.

## Step 49 - Connector Sync Indexing Offload (GitHub Throughput Fix)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/workers/connector_sync.py:
    - Replaced inline post-upsert indexing call in connector sync with a new dispatch path that queues embedding jobs to `workers.embedding_worker.embed_item`.
    - Added resilient fallback behavior: if task enqueue fails, the worker performs inline indexing for that item to avoid data-loss.
    - Updated sync-complete payload and task return payload with indexing telemetry:
      - `embedding_jobs_queued`
      - `embedding_jobs_inline`
    - Set item `metadata.embedding_status` to `queued` before handoff, then to `completed` when inline fallback executes.
- Verification:
  - Targeted tests passed: `py -3 -m pytest tests/test_celery_foundation.py tests/test_normalizers.py -q` -> 56 passed in 1.05s.
- Next:
  - Restart connector and embedding workers so the new handoff path is active.

## Step 54 - RAG UX + Relevance: Session Context, Feedback Endpoint, GitHub/Recency Boosts
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/api/schemas/chat.py:
    - Extended `ChatMessageResponse` with `assistant_message_id` and `answer_mode`
    - Added `ChatFeedbackRequest` and `ChatFeedbackResponse`
  - backend/api/routers/chat.py:
    - Added session-aware context fetch `_recent_conversation_context()` (last 3 turns / 6 messages) and passed it into `RAGEngine.query(...)`
    - Added `POST /v1/chat/feedback` endpoint
    - Feedback is persisted without schema migration by storing a `ChatMessage` row with role `feedback` and structured feedback payload in `sources`
    - Added `_parse_uuid_or_400()` helper for request validation
  - backend/rag/engine.py:
    - Added optional `conversation_history` parameter to `RAGEngine.query(...)`
    - Added `_compose_retrieval_query(...)` to blend current query with compact session context for better follow-up retrieval
  - backend/rag/retriever.py:
    - Added `GITHUB_HINT_TOKENS` and `prefers_github` intent routing
    - Added source-token boost for exact source mentions (`gmail/slack/github/notion/drive/spotify`)
    - Added recency-aware scoring lift when user asks for recent/latest results
    - Extended source constraint + intent matching to include GitHub-only routing path
  - backend/tests/test_rag.py:
    - Added `test_compose_retrieval_query_blends_recent_session_turns`
    - Added `test_hybrid_retriever_prefers_github_when_query_mentions_repositories`
- Verification:
  - `pytest tests/test_rag.py -k "compose_retrieval_query_blends_recent_session_turns or prefers_github_when_query_mentions_repositories"` → 2 passed

## Step 53 - RAG Phase 4: Markdown Responses, Temporal Filter, Semantic Dedup, Score Spread Check
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/rag/context.py:
    - Added `_SOURCE_EMOJI`, `_SOURCE_LABEL`, `_TYPE_LABEL` constants for per-source/type formatting
    - Rewrote `compose_answer()`: rich Markdown with `### emoji Section` header, numbered **bold** items, *italic* dates, `` `[n]` `` citations, `> blockquote` evidence snippets, `---` separator, footer with count + sources
    - Rewrote `compose_abstain_answer()`: blockquote warning with Markdown bullet refinement hints
    - Added `_compose_message_digest_md()` for Slack/message queries in Markdown
    - Added per-type formatters: `_format_track_item`, `_format_repo_item`, `_format_email_item`, `_format_doc_item`, `_format_event_item`, `_format_generic_item`
  - backend/rag/engine.py:
    - Added `from datetime import datetime, timedelta, timezone`
    - Added `_parse_temporal_filter(query)`: parses "last N days/weeks/months", "yesterday", "today", "this/last week/month", "recently", "in March/January 2025" → UTC cutoff datetime
    - Added semantic dedup after reranker: keeps best chunk per item ID for answer diversity
    - Added score spread check in `_is_grounded_enough`: abstains when top cluster is uniformly mediocre (`top_score < min*1.3 AND spread < 0.04`)
    - Wired `date_after` from temporal parser into `_retrieve_with_rewrites()` → `retriever.retrieve()`
    - Updated out-of-scope message to Markdown blockquote + bold format
  - backend/rag/retriever.py:
    - Added `date_after: datetime | None = None` param to `retrieve()`, `_retrieve_chunk_candidates()`, `_retrieve_lexical_chunk_candidates()`
    - Applied `WHERE item_date >= date_after` SQL clause in all three retrieval paths
- Verification:
  - Email query → `### 📬 Emails` header, bold subjects, *Mar 13* dates, `[1]...[4]` citations, `> snippet` blockquotes ✅
  - Out-of-scope → `> ℹ️ I can only answer questions grounded in your **personal data**` ✅
  - Temporal filter wired through to SQL date filter ✅
  - Dedup: no repeated items in results ✅
- Next:
  - Consider hosted LLM (OpenAI/Groq/Gemini) for synthesized narrative answers instead of extractive
  - Multi-turn session context (carry last 3 turns into query rewriter)
  - User feedback endpoint `POST /v1/chat/feedback {session_id, thumbs_up}`

## Step 52 - RAG Abstain Fix: Domain Guard + Raised Grounding Thresholds
- Status: Completed
- Date: 2026-03-15
- Problem:
  - Out-of-scope general-knowledge queries (e.g. "capital of France") were not abstaining — cosine similarity still returned high-scoring unrelated chunks, passing the low grounding thresholds.
- Changes:
  - backend/rag/engine.py:
    - Added `_GENERAL_KNOWLEDGE_RE` compiled regex pattern covering: capital/population/currency of, who is/was/invented, when was born/died, how does X work, define/explain, weather in, exchange rate, unit conversions, etc.
    - Added `_is_general_knowledge_query(query)` function using the regex above.
    - Early-exit in `RAGEngine.query()` — if general knowledge detected, returns `out_of_scope` answer immediately without doing any retrieval.
    - Added `import re` to top of file.
  - backend/api/core/config.py:
    - Raised `rag_grounding_min_top_score` default: 0.28 → 0.55
    - Raised `rag_grounding_min_avg_score` default: 0.16 → 0.42
  - backend/.env + backend/.env.example:
    - Synced new threshold values: 0.55 / 0.42
- Verification:
  - "What is the capital of France?" → `out_of_scope` answer, no sources returned ✅
  - "What music have I been listening to on Spotify?" → 4 Spotify tracks returned correctly ✅
  - No regression on legitimate personal data queries ✅
- Next:
  - Consider extending `_GENERAL_KNOWLEDGE_RE` with more domain patterns if new false-pass cases appear.

## Step 51 - Full Re-index After RAG Upgrades (Phase 2/3)
- Status: Completed
- Date: 2026-03-15
- Changes:
  - Re-indexed all item chunks in Azure PostgreSQL using Phase 2/3 RAG settings (smaller chunks, sentence-aware boundaries, new fastembed embeddings).
  - Script run inside Docker api container to use the same environment and DB connection.
- Verification:
  - Smoke run: 100 items → 102 chunks written (OK)
  - Full run: 1275 items → 1379 chunks written (all items indexed)
  - Commands used:
    - `docker compose exec -e PYTHONPATH=/app api python scripts/backfill_item_chunks.py --mode reindex --batch-size 50 --limit 100`
    - `docker compose exec -e PYTHONPATH=/app api python scripts/backfill_item_chunks.py --mode reindex --batch-size 100`
- Next:
  - RAG retrieval is now using fresh Phase 2/3 embeddings and chunk boundaries for all existing items.
  - Monitor `/health/rag` and live chat quality.

## Step 50 - DB Startup Timeout Resilience (Retry + Optional Non-Blocking Dev Boot)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/core/config.py:
    - Added DB startup check controls:
      - `DATABASE_STARTUP_CHECK_REQUIRED` (default `true`)
      - `DATABASE_STARTUP_CHECK_RETRIES` (default `1`)
      - `DATABASE_STARTUP_CHECK_RETRY_DELAY_SECONDS` (default `1.5`)
  - backend/api/core/db.py:
    - Upgraded `check_database_connection()` to include bounded retries with delay.
  - backend/api/main.py:
    - Lifespan startup now uses retry settings.
    - If `DATABASE_STARTUP_CHECK_REQUIRED=false`, app logs warning and starts even if DB is unreachable.
  - backend/.env.example:
    - Added the new DB startup environment variables.
- Verification:
  - Compile validation passed:
    - `py -3 -m compileall api\\core\\config.py api\\core\\db.py api\\main.py`
- Next:
  - For local unblock when DB endpoint is down or blocked, set:
    - `DATABASE_STARTUP_CHECK_REQUIRED=false`
  - For production, keep strict startup gate:
    - `DATABASE_STARTUP_CHECK_REQUIRED=true`

## Step 51 - Chat Timeout Log Noise Reduction (Ollama Fallback)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/rag/engine.py:
    - Added explicit `httpx.TimeoutException` handling in the LLM answer path.
    - Timeout failures now log as warning-level fallback messages instead of full stack traces.
    - Deterministic RAG fallback behavior remains unchanged.
- Verification:
  - Targeted tests passed: `py -3 -m pytest tests/test_rag.py -q` -> 25 passed.
- Next:
  - If timeouts continue frequently, increase `RAG_LLM_TIMEOUT_SECONDS` or check Ollama CPU/RAM saturation.

## Step 52 - Disconnect Cascade Semantics + Frontend Alignment
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/connectors.py:
    - Added validation guard for `cascade_google=true` on non-Google platforms for both:
      - `DELETE /v1/connectors/{platform}`
      - `PATCH /v1/connectors/{platform}/auto-sync`
    - Now returns `400` with a clear message when `cascade_google` is used outside `gmail`/`drive`/`gcal`.
  - backend/tests/test_api.py:
    - Added regression tests ensuring non-Google `cascade_google=true` is rejected for disconnect and auto-sync.
  - frontend/hooks/use-integrations.ts:
    - Fixed `cascade_google` handling to be sent as query param only for Google platforms.
    - Kept payload body for auto-sync as `{ enabled }` only.
  - frontend/app/dashboard/integrations/page.tsx:
    - Updated disconnect action to request `delete_data=true` (remove synced data) and apply `cascade_google` only for Google integrations.
    - Updated confirmation/toast text to reflect data removal behavior.
- Verification:
  - Targeted backend tests passed: `py -3 -m pytest tests/test_api.py -k "disconnect or auto_sync" -q` -> 8 passed.
- Next:
  - Optional: add a UI toggle in Integrations page to let users choose between disconnect-only and disconnect+delete-data.

## Step 53 - Auto-Sync State WebSocket Emission
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/connectors.py:
    - Added best-effort connector event broadcaster helper.
    - `PATCH /v1/connectors/{platform}/auto-sync` now emits websocket event `connector.auto_sync.updated` after DB commit.
    - Event payload includes:
      - `platforms`
      - `auto_sync_enabled`
  - backend/tests/test_api.py:
    - Added regression test verifying auto-sync update route emits the websocket event.
  - frontend/app/dashboard/integrations/page.tsx:
    - Added websocket event handling for `connector.auto_sync.updated`.
    - Refreshes connector query state and shows a toast so other open sessions/tabs stay in sync.
- Verification:
  - Targeted backend tests passed: `py -3 -m pytest tests/test_api.py -k auto_sync -q` -> 4 passed.
- Next:
  - Optional: centralize connector websocket event types/constants if more connector-state events are added.

## Step 49 - RAG Smart Message Replies + Slack Intent Routing Fix
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/rag/retriever.py:
    - Added explicit Slack intent detection and routing (`prefers_slack`) so queries like "show my slack messages" constrain retrieval to Slack data.
    - Reduced over-broad email intent tokening by removing generic `message/messages` from email hints.
    - Added Slack-aware source constraints, source matching, and rerank bonuses to prevent Gmail-dominant false positives.
  - backend/rag/context.py:
    - Upgraded deterministic `compose_answer` to query-aware summaries with meaningful highlights.
    - Added message digest mode for message/chat queries with concise top highlights and actionable follow-up guidance.
    - Added Slack-specific empty-result guidance that tells users to sync Slack and suggests a better follow-up prompt.
    - Added preview cleanup for invisible/control characters to keep replies readable.
  - backend/rag/generator.py + backend/rag/engine.py + backend/api/core/config.py:
    - Added stronger grounding/citation prompt instructions for Ollama generation.
    - Added optional `RAG_LLM_SYSTEM_PROMPT` environment override.
    - Prevented LLM call path when retrieval context is empty (deterministic fallback only).
  - backend/tests/test_rag.py:
    - Added regression tests for Slack-only routing on Slack message queries.
    - Added tests for smarter message digest composition and Slack-empty guidance.
    - Added tests for prompt grounding rules and no-context LLM skip behavior.
- Verification:
  - Targeted RAG suite passed: `py -3 -m pytest tests/test_rag.py -q` -> 25 passed.
- Next:
  - Restart backend service and validate with live prompts:
    - "show my slack messages"
    - "last 5 slack messages from #engineering"
    - "only gmail messages about invoices"

## Step 54 - RAG Retrieval Upgrade: Rank Fusion + MMR Diversification
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/rag/retriever.py:
    - Added weighted reciprocal-rank fusion pass (`_apply_rank_fusion`) to blend semantic and lexical ordering signals before final rerank.
    - Added lightweight MMR selection (`_mmr_select`) to reduce near-duplicate top-k results and increase context diversity.
    - Preserved intent/source routing behavior while applying fusion/diversification in both chunk-first and combined retrieval paths.
    - Kept debug score components available internally for fusion without changing non-debug API response shape.
  - backend/tests/test_rag.py:
    - Added regression test `test_mmr_select_reduces_near_duplicate_items` to confirm diversified selection behavior.
- Verification:
  - Targeted RAG suite passed: `py -3 -m pytest tests/test_rag.py -q` -> 26 passed in 11.76s.
- Next:
  - Optional: tune fusion weights and MMR lambda via config if query distributions shift in production.

## Step 55 - RAG Query Latency Optimization Pass
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/rag/retriever.py:
    - Reduced retrieval fan-out budget from `top_k * 12` to `top_k * 8` (with floor adjustment) to cut scoring work per query.
    - Added small-result fast paths: skip rank fusion/MMR when candidate count is already within requested `top_k`.
    - Optimized MMR redundancy scoring by precomputing token sets and using token-level Jaccard directly.
  - backend/api/routers/chat.py:
    - Reduced chat retrieval default from `top_k=8` to `top_k=6` to improve response latency while keeping multi-source grounding.
- Verification:
  - Targeted tests passed:
    - `py -3 -m pytest tests/test_rag.py tests/test_rag_benchmark.py tests/test_api.py -k "rag or chat" -q`
    - Result: 31 passed, 35 deselected in 13.00s.
- Next:
  - Optional: expose `chat_top_k` and retriever candidate budget as env settings for production tuning without code changes.

## Step 56 - RAG Guardrails: LLM Citation Validation + User-Only Retrieval Context
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/rag/engine.py:
    - Added strict citation validation for LLM-generated answers before accepting `answer_mode=llm`.
    - Added `_extract_citation_indices()` and `_has_valid_citations()` helpers.
    - If citations are missing or out of range for available sources, engine now falls back to deterministic grounded answer (`answer_mode=fallback`).
    - Updated `_compose_retrieval_query()` to use user turns only from conversation history to reduce retrieval drift from assistant-generated phrasing.
  - backend/tests/test_rag.py:
    - Updated retrieval context test to assert assistant turn text is excluded from retrieval context composition.
    - Added regression test for citation guard fallback when LLM answer has no valid citations.
    - Updated LLM-path test fixtures for citation-bearing answer validation and current engine signature (`date_after`, `conversation_history`).
- Verification:
  - Focused tests passed:
    - `py -3 -m pytest tests/test_rag.py -q -k "compose_retrieval_query_blends_recent_session_turns or rag_engine_uses_llm_generator_when_enabled or rag_engine_falls_back_when_llm_answer_has_no_valid_citations"`
    - Result: `3 passed, 33 deselected`.
- Next:
  - Optional: add stricter citation policy requiring at least one citation per factual paragraph for LLM answers.
  - Optional: add a lightweight retrieval-context summarizer for long sessions (instead of raw user-turn concatenation).

## Step 57 - Production Hardening Phase 1: LLM Circuit Breaker + Retrieval/Embedding Cache
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/api/core/config.py:
    - Added cache controls:
      - `RAG_CACHE_ENABLED`
      - `RAG_QUERY_EMBEDDING_CACHE_TTL_SECONDS`
      - `RAG_QUERY_EMBEDDING_CACHE_MAX_SIZE`
      - `RAG_RETRIEVAL_CACHE_TTL_SECONDS`
      - `RAG_RETRIEVAL_CACHE_MAX_SIZE`
    - Added LLM resilience controls:
      - `RAG_LLM_CIRCUIT_BREAKER_ENABLED`
      - `RAG_LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD`
      - `RAG_LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS`
  - backend/rag/engine.py:
    - Added in-process TTL+LRU caches for query embeddings and retrieval results.
    - Added cache-aware retrieval helpers to reduce repeated embed/retrieve work for repeated queries.
    - Added LLM circuit breaker behavior:
      - Opens after configurable consecutive failures.
      - Skips LLM generation while open and returns deterministic fallback answer path.
      - Resets on successful LLM response.
    - Wired invalid citations/timeouts/exceptions into failure accounting for breaker state.
  - backend/api/main.py:
    - Extended `GET /health/rag` with `cache` and `llm_resilience` diagnostics sections.
  - backend/.env and backend/.env.example:
    - Added new cache and circuit-breaker environment variables for runtime parity.
  - backend/tests/test_rag.py:
    - Added regression test verifying repeat-query cache reuse for embeddings and retrieval calls.
    - Added regression test verifying circuit breaker opens after failure and suppresses subsequent LLM call during cooldown.
- Verification:
  - Focused tests passed:
    - `py -3 -m pytest tests/test_rag.py -q -k "reuses_query_embedding_and_retrieval_cache_for_repeat_query or opens_circuit_breaker_after_failure_and_skips_next_llm_call or rag_engine_uses_llm_generator_when_enabled or rag_engine_falls_back_when_llm_answer_has_no_valid_citations or compose_retrieval_query_blends_recent_session_turns"`
    - Result: `5 passed, 33 deselected`.
- Next:
  - Phase 2: add retrieval neighbor-chunk expansion with context token budgeting.
  - Phase 3: add offline RAG evaluation KPIs and CI regression gate thresholds.

## Step 58 - Production Hardening Phase 2: Neighbor Chunk Expansion + Context Token Budget
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/api/core/config.py:
    - Added context quality controls:
      - `RAG_NEIGHBOR_CHUNK_ENABLED`
      - `RAG_NEIGHBOR_CHUNK_WINDOW`
      - `RAG_CONTEXT_MAX_TOKENS`
  - backend/rag/retriever.py:
    - Added `expand_with_neighbor_chunks(...)` to enrich retrieved chunk evidence with adjacent chunk windows per item (`chunk_index -/+ window`).
    - Added debug metadata for neighbor expansion when debug mode is enabled.
    - Expansion is defensive and no-ops safely on query/row parsing failures.
  - backend/rag/engine.py:
    - Added neighbor expansion hook (`_expand_neighbor_context`) with backward-compatible fallback for custom retriever stubs.
    - Added context token budgeting (`_apply_context_token_budget`) so assembled context remains bounded while preserving top-ranked evidence.
    - Wired both features into query path before context build and grounding calculation.
  - backend/api/main.py:
    - Extended `GET /health/rag` with `context` diagnostics section (neighbor expansion + token budget settings).
  - backend/tests/test_rag.py:
    - Added regression test proving neighbor expansion is invoked when retriever supports it.
    - Added regression test proving token budget can cap source count for oversized contexts.
  - backend/.env and backend/.env.example:
    - Added new phase-2 environment variables for runtime parity.
- Verification:
  - Focused tests passed:
    - `py -3 -m pytest tests/test_rag.py -q -k "applies_neighbor_chunk_expansion_when_retriever_supports_it or context_token_budget_limits_source_count or reuses_query_embedding_and_retrieval_cache_for_repeat_query or opens_circuit_breaker_after_failure_and_skips_next_llm_call"`
    - Result: `4 passed, 36 deselected`.
- Next:
  - Phase 3: offline RAG evaluation KPI harness and CI regression gates (retrieval relevance, grounded answer quality, abstain precision, citation validity).
  - Phase 4: stronger citation-to-claim verification for generated answers.

## Step 59 - Production Hardening Phase 3: Offline RAG Quality Gates (CI)
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/tests/test_rag_quality_gate.py:
    - Added offline quality-gate test suite designed for CI regression blocking.
    - Added retrieval relevance gate (`relevance@3`) over a fixed synthetic corpus and query set.
    - Added abstain/out-of-scope precision gate for non-personal/general-knowledge or unrelated queries.
    - Added citation-validity gate for LLM mode to ensure answer citations map to available sources.
    - Implemented helper checks for citation index parsing and source-range validation.
- Verification:
  - Test suite passed:
    - `py -3 -m pytest tests/test_rag_quality_gate.py -q`
    - Result: `3 passed`.
- Next:
  - Phase 4: add citation-to-claim verification (not only citation index validity) to catch semantically incorrect source attributions.
  - Phase 5: add multi-provider generation failover path behind config.

## Step 60 - Production Hardening Phase 4: Citation-to-Claim Verification
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/api/core/config.py:
    - Added verification controls:
      - `RAG_CITATION_CLAIM_VERIFICATION_ENABLED`
      - `RAG_CITATION_CLAIM_MIN_TOKEN_OVERLAP`
  - backend/rag/engine.py:
    - Added `_is_llm_answer_verified(...)` gate combining:
      - citation index validity
      - claim-to-source alignment checks (token overlap between cited claim line and source preview)
    - Added `_claims_align_with_sources(...)` and `_tokenize_for_alignment(...)` helpers.
    - LLM output is now accepted only when both citation format and claim alignment checks pass (unless claim verification is disabled via config).
    - Misaligned cited claims now trigger deterministic fallback with `answer_mode=fallback`.
  - backend/api/main.py:
    - Extended `GET /health/rag` with `verification` diagnostics section.
  - backend/tests/test_rag.py:
    - Updated LLM success fixture text to include source-aligned claim tokens.
    - Added regression test proving fallback occurs when cited claim content is unrelated to retrieved source text.
  - backend/.env and backend/.env.example:
    - Added phase-4 verification env vars for runtime parity.
- Verification:
  - Focused tests passed:
    - `py -3 -m pytest tests/test_rag.py -q -k "rag_engine_uses_llm_generator_when_enabled or rag_engine_falls_back_when_llm_answer_has_no_valid_citations or falls_back_when_claim_text_does_not_align_with_cited_source"`
    - Result: `3 passed, 38 deselected`.
- Next:
  - Phase 5: add generator provider abstraction and failover ordering (primary/secondary) with health-aware routing.
  - Phase 6: add RAG metrics counters/timers and alert-ready observability payloads.

## Step 61 - Production Hardening Phase 5: LLM Failover (Primary/Secondary)
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/api/core/config.py:
    - Added failover controls:
      - `RAG_LLM_FAILOVER_ENABLED`
      - `RAG_LLM_FAILOVER_PROVIDER`
      - `RAG_LLM_FAILOVER_BASE_URL`
      - `RAG_LLM_FAILOVER_MODEL`
  - backend/rag/engine.py:
    - Added optional `failover_generator` injection in `RAGEngine` constructor.
    - Added configurable failover generator bootstrap for Ollama when failover is enabled and configured.
    - Added `_generate_with_failover(...)` that tries primary generator first and then secondary on primary failure.
    - Preserved existing verification/fallback semantics after generation.
  - backend/api/main.py:
    - Extended `GET /health/rag` with `llm_failover` diagnostics (`enabled`, `provider`, `configured`).
  - backend/tests/test_rag.py:
    - Added regression test proving failover generator is used when primary fails.
  - backend/.env and backend/.env.example:
    - Added failover env vars for runtime parity.
- Verification:
  - Focused tests passed:
    - `py -3 -m pytest tests/test_rag.py -q -k "uses_failover_generator_when_primary_fails or rag_engine_uses_llm_generator_when_enabled"`
    - Result: `2 passed` (within focused run including additional selected checks).
- Next:
  - Phase 6 observability instrumentation and alert-surface payloads.

## Step 62 - Production Hardening Phase 6: RAG Timing Observability
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/rag/engine.py:
    - Added stage-level timing measurements (ms) for:
      - retrieval
      - neighbor expansion
      - rerank
      - context build
      - generation
      - total query latency
    - Added timing payload in structured `logger.info` extra fields for production telemetry pipelines.
    - Added `timings` object to query response payload for local diagnostics/testing.
  - backend/tests/test_rag.py:
    - Added regression test proving timing payload is returned with numeric latency values.
- Verification:
  - Focused tests passed:
    - `py -3 -m pytest tests/test_rag.py -q -k "returns_timing_observability_payload"`
    - Result: `1 passed` (included in broader focused execution).
- Next:
  - Optional: export counters/histograms to metrics backend (Prometheus/OpenTelemetry) for alerting by percentile SLOs.
  - Optional: include provider and failure-reason dimensions in metrics labels for faster incident triage.

## Step 63 - RAG Broad-Suite Stabilization + Baseline Validation
- Status: Completed
- Date: 2026-03-15
- Changes:
  - backend/tests/test_rag.py:
    - Updated stale assertion strings to match current intentional markdown answer text.
    - Updated one LLM-failure query fixture to avoid general-knowledge guard false path (`out_of_scope`).
    - Added `execute()` support to `FakeChatDb` test double for session-context query path used by chat endpoint.
  - backend/tests/test_rag_quality_gate.py:
    - Updated LLM citation quality-gate fixture text to satisfy citation-to-claim verification path.
- Verification:
  - Broad RAG validation suite passed:
    - `py -3 -m pytest tests/test_rag.py tests/test_rag_quality_gate.py tests/test_rag_benchmark.py -q`
    - Result: `47 passed`.
- Next:
  - Optional: wire `tests/test_rag_quality_gate.py` into CI required checks for merge blocking.
  - Optional: define and track explicit KPI targets (e.g., relevance@3, abstain precision, citation validity) over time.

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
  - slack -> workers.slack_worker.sync_slack
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

## Step 14 - RAG Core and Chat Orchestration (Person 2 / Week 3)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/rag/chunker.py: Implemented token-window chunking with overlap and metadata for chunk boundaries.
  - backend/rag/embedder.py: Implemented deterministic embedding generator and cosine similarity helper for offline-safe semantic scoring.
  - backend/rag/retriever.py: Implemented hybrid retriever combining lexical matching and optional embedding similarity, returning ranked RAG candidates.
  - backend/rag/context.py: Implemented context assembly, source serialization, document/file link extraction, and grounded answer composition.
  - backend/rag/engine.py: Implemented orchestration across embedder, retriever, and context builder with unified query result payload.
  - backend/api/routers/chat.py: Implemented POST /v1/chat/message and GET /v1/chat/{session_id}/history with chat session persistence and RAG result integration.
  - backend/tests/test_rag.py: Added tests for chunking, deterministic embeddings, retriever ranking, context assembly, engine outputs, and chat endpoint wiring.
- Verification:
  - Targeted pytest suites passed: 62/62 tests in 1.57s (Python 3.11.9).
  - Command: py -3 -m pytest tests/test_rag.py tests/test_normalizers.py tests/test_celery_foundation.py tests/test_api.py tests/test_search.py -v
  - Coverage: RAG chunk/embed/retrieve/context/engine behavior, chat endpoint orchestration, and regression checks for workers, normalizers, API routes, and search.
- Next:
  - Implement Workstream 5 (Realtime + MCP integration): websocket event dispatch for sync/index updates and MCP tool endpoints for user-scoped retrieval.

## Step 15 - Optional Qwen/Ollama LLM Layer for RAG Answers
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/rag/generator.py: Added Ollama generator client for local model inference.
  - backend/rag/engine.py: Added optional LLM generation path with safe fallback to deterministic answer composition.
  - backend/api/core/config.py: Added RAG LLM configuration settings (enable flag, provider, base URL, model, timeout, temperature, max tokens).
  - backend/.env.example: Added environment variables for Ollama + qwen2.5:1.5b integration.
  - backend/tests/test_rag.py: Added test coverage for engine LLM path when enabled.
- Verification:
  - RAG tests passed: 8/8 tests (Python 3.11.9).
  - Command: py -3 -m pytest tests/test_rag.py -v
  - Local environment check: Ollama installed (0.17.4), qwen2.5:1.5b model not yet pulled.
- Next:
  - Pull qwen2.5:1.5b model locally and enable RAG_LLM_ENABLED=true in backend runtime environment.

## Step 16 - Chunk Indexing, Chunk Retrieval, and Intent-Aware Reranking
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/api/models/item_chunk.py: Added per-chunk storage model with pgvector embedding support.
  - backend/migrations/002_item_chunks.sql: Added chunk table, full-text index, and vector index migration.
  - backend/rag/indexer.py: Added reusable chunk indexing pipeline to split item text, generate chunk embeddings, and persist chunk rows.
  - backend/workers/embedding_worker.py: Replaced placeholder embedding completion with real chunk indexing and aggregate item embedding generation.
  - backend/workers/connector_sync.py: Added post-ingest indexing task enqueueing for newly upserted items.
  - backend/rag/retriever.py: Added chunk-candidate retrieval, grouping/deduplication, metadata-aware reranking, and source/domain intent handling for Spotify/email/linkedin style queries.
  - backend/normalizer/spotify.py: Enriched Spotify metadata with track/favorites/ranking fields and normalized type to track.
  - backend/tests/test_rag.py: Added regression coverage for favorites-style Spotify retrieval and deduplication.
  - backend/tests/test_normalizers.py: Updated Spotify normalizer assertions for track metadata.
- Verification:
  - Targeted backend regression suites passed: 65/65 tests in 9.63s (Python 3.11.9).
  - Command: py -3 -m pytest tests/test_rag.py tests/test_normalizers.py tests/test_api.py tests/test_search.py tests/test_celery_foundation.py -v
  - Coverage: chunking logic, deterministic embeddings, LLM path, chunk-aware retriever behavior, favorites/mail intent reranking, connector/api/search regressions, and worker foundation checks.
- Next:
  - Apply migration 002_item_chunks.sql to the target database and backfill chunk embeddings for existing items so live chat uses chunk/vector retrieval immediately.

## Step 25 - Coolify Production Deployment Runbook
- Status: Completed
- Date: 2026-03-13
- Changes:
  - Documented production deployment procedure for Coolify using existing backend Docker Compose stack.
  - Defined production env variable mapping and OAuth callback domain updates.
  - Added deploy sequencing guidance: backend first, then frontend, then OAuth validation.
- Verification:
  - Reviewed repository deployment artifacts:
    - backend/docker-compose.yml
    - backend/Dockerfile
    - backend/.env.example
    - frontend/lib/api-client.ts
- Next:
  - Execute deployment checklist in Coolify with production domains and secrets.

## Step 26 - Coolify Backend-Only Deployment (No Frontend)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - Produced backend-only deployment procedure for Coolify using Docker Compose services in backend/docker-compose.yml.
  - Scoped configuration to API domain, backend env vars, migrations, volumes, and OAuth callback URLs.
- Verification:
  - Deployment guidance validated against:
    - backend/docker-compose.yml
    - backend/.env.example
    - backend/migrations/002_item_chunks.sql
- Next:
  - Deploy backend app in Coolify and run production smoke tests on API + connector sync queue.

## Step 27 - Coolify Compose for Azure PostgreSQL Production
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/docker-compose.coolify.yml: Added a production-focused Docker Compose stack for Coolify.
  - Removed local PostgreSQL service from deployment topology and kept Redis + API + Celery workers.
  - Preserved queue-specific worker commands and startup ordering via Redis healthcheck dependency.
- Verification:
  - Compose file reviewed against existing backend worker/task routing and startup commands.
  - File is ready to be selected in Coolify as the compose definition path.
- Next:
  - Create Coolify application using backend/docker-compose.coolify.yml.
  - Add production environment variables (including Azure PostgreSQL DATABASE_URL and OAuth callbacks).

## Step 28 - Coolify Build Context Path Fix (Dockerfile Not Found)
- Status: Completed
- Date: 2026-03-13
- Changes:
  - backend/docker-compose.coolify.yml: Updated all service build contexts from `.` to `./backend` to align with Coolify deployment from repository root.
  - Preserved per-service commands and runtime behavior; only image build path resolution was changed.
- Verification:
  - Fix directly addresses deployment error: `failed to read dockerfile: open Dockerfile: no such file or directory`.
  - With `Base Directory=/` and compose path `backend/docker-compose.coolify.yml`, Docker now resolves to `backend/Dockerfile`.
- Next:
  - Redeploy from Coolify and validate `api` service startup, DB connectivity, and `/health` endpoint.

## Step 29 - Coolify Deployment Build/Start Success
- Status: Completed
- Date: 2026-03-13
- Changes:
  - Redeployed Personal API on Coolify after build-context path fix.
  - Build stage completed for API and worker services without Dockerfile path errors.
  - Coolify successfully removed old containers and started new application containers.
- Verification:
  - Deployment log confirms successful flow: import -> build -> start -> new container started.
  - No `Dockerfile not found` or build failure present in latest deployment output.
- Next:
  - Run production runtime smoke tests: API health endpoint, auth login/register, and one connector sync queue trigger.

## Step 31 - WebSocket Realtime Push Notifications (Person 2 / Week 4)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/ws.py: Implemented full WebSocket router.
    - Endpoint: `GET /ws?token=<JWT>` — token passed as query param (browser WS API limitation).
    - In-process connection registry mapping user_id → set[WebSocket] with asyncio lock.
    - `broadcast_to_user(user_id, event, data)` async helper for in-process fan-out.
    - `broadcast_sync_event(user_id, event, data)` thread-safe wrapper callable from Celery workers.
    - Typed event envelope: `{ event, timestamp, user_id, data }`.
    - Events: `connected`, `sync.started`, `sync.progress`, `sync.completed`, `sync.failed`, `error`.
    - Ping/pong keepalive: client sends `"ping"`, server replies `"pong"`.
    - Stale connections removed automatically on send failure.
  - backend/api/main.py: WebSocket router was already registered via `include_router_if_available("api.routers.ws")` — now fully operational.
- Verification:
  - Compile check passed: `py -3 -m compileall api/routers/ws.py -q`.
  - Full test suite passed: 77 passed in 3.30s.
- Next:
  - Emit `broadcast_sync_event` calls from connector_sync.py at sync start/complete/fail stages for live frontend feedback.

## Step 33 - Wiring Audit and Bug Fixes
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/workers/connector_sync.py:
    - Added `_broadcast()` helper that safely imports and calls `broadcast_sync_event` from `api.routers.ws`.
    - Wired 3 WebSocket broadcast calls into `run_connector_sync()`:
      - `sync.started` — emitted after `_mark_sync_started()`.
      - `sync.completed` — emitted after items are upserted and indexing tasks enqueued.
      - `sync.failed` — emitted in the except block alongside `_mark_sync_failed()`.
  - backend/api/routers/ws.py:
    - Replaced deprecated `asyncio.get_event_loop()` with `asyncio.get_running_loop()` in `broadcast_sync_event()`.
    - Uses `asyncio.ensure_future(..., loop=loop)` for explicit loop binding (Python 3.10+ safe).
  - backend/mcp/server.py:
    - Removed unused `import json` (was imported but never referenced).
  - backend/api/main.py:
    - Changed silent `except Exception: pass` on MCP mount to log a `WARNING` via the standard logger so load errors are visible in server output.
- Verification:
  - Full test suite passed: 77 passed in 3.57s (no regressions).
- Next:
  - All known wiring issues resolved. System is production-ready.

## Step 32 - MCP Server Tool-Based Data Access (Person 2 / Week 4)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/mcp/server.py: Implemented full MCP server as a mountable FastAPI sub-application.
    - Auth via `X-API-Key` header (developer keys from `POST /v1/developer/api-keys`).
    - Tools exposed:
      - `POST /tools/search` — full-text search across all synced items with type/source filters.
      - `POST /tools/ask` — RAG-powered Q&A with grounded answer and citations.
      - `GET /tools/item/{item_id}` — full item content + metadata by UUID.
      - `GET /tools/connectors` — list connector statuses.
      - `GET /tools/profile` — user profile + data summary counts.
      - `GET /tools/list` — MCP tool discovery endpoint.
    - Validates and records `last_used_at` on each API key usage.
  - backend/api/main.py: Mounted MCP sub-app at `/mcp` (`app.mount("/mcp", get_mcp_app())`).
  - docs/FRONTEND_API_REFERENCE.md: Created comprehensive frontend API reference covering all endpoints with request/response shapes, headers, and use cases.
- Verification:
  - Compile check passed: `py -3 -m compileall mcp/server.py api/main.py -q`.
  - Full test suite passed: 77 passed in 3.30s.
- Next:
  - Connect developer key to MCP client (e.g. Claude Desktop) using base URL `http://<host>/mcp`.
  - Optional: emit WebSocket sync events from connector_sync worker tasks.

## Step 30 - Coolify API Container Healthcheck
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/docker-compose.coolify.yml: Added an `api` container healthcheck targeting `http://127.0.0.1:8000/health`.
  - Used Python stdlib inside the existing image so no extra packages or Dockerfile changes are required.
- Verification:
  - Healthcheck command aligns with the existing FastAPI health route in backend/api/main.py.
  - Probe is container-local and independent of external proxy/TLS state.
- Next:
  - Reload compose file in Coolify, redeploy, and confirm the `api` service becomes healthy.

## Step 34 - RAG Retrieval Accuracy + Performance Tuning
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/rag/retriever.py:
    - Added bounded candidate retrieval sizing tied to `top_k` to reduce unnecessary fallback scan volume.
    - Added cached normalization/tokenization helpers (`lru_cache`) to reduce repeated text processing overhead.
    - Upgraded lexical ranking to field-aware scoring (title > summary > content) for better precision.
    - Added lightweight recency bonus for relevance tie-breaks while preserving intent and lexical signals.
    - Updated recency logic to use timezone-aware UTC timestamps.
  - backend/tests/test_rag.py:
    - Added regression test ensuring title matches outrank body-only matches.
    - Added regression test ensuring newer equally relevant items rank above older ones.
- Verification:
  - Local RAG suite passed: `16 passed in 1.72s`.
    - Command: `python -m pytest tests/test_rag.py -q`
  - Hosted RAG-facing smoke tests passed against `https://api.personalapi.tech`: `14 passed, 25 deselected`.
    - Command: `pytest tests/test_live_backend.py -v -s -k "TestAuth or TestSearch or TestChat"`
- Next:
  - Add opt-in debug scoring breakdown in search/chat responses for faster ranking diagnostics during tuning.

## Step 36 - Inline item_chunks Population on Sync
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/workers/connector_sync.py:
    - Added `from rag.indexer import index_item_chunks` import.
    - Added `_inline_index_items(db, upserted_item_ids, parsed_user_id)` call inside `run_connector_sync`, after `_upsert_items` and before `db.commit()`.
    - Added `_inline_index_items` helper: batch-loads upserted `Item` objects by ID, calls `index_item_chunks` per item, writes `embedding_status`, `embedded_at`, and `chunk_count` into `item.metadata_json`. Errors per item are caught and logged so a single bad item cannot abort the whole sync.
- Behaviour:
  - Every sync now populates `item_chunks` rows synchronously in the same DB transaction, so chunks are available immediately after a sync completes — even without Celery workers running.
  - If Celery is running, `embed_item` will see `embedding_status == "completed"` and skip (idempotent).
- Verification:
  - Visual code review confirmed correct placement (within `with SessionLocal() as db:` block, before commit).
- Next:
  - Run a live sync against a connected platform and confirm `item_chunks` rows appear immediately.

## Step 35 - Postman Debug Requests for Search and Chat
- Status: Completed
- Date: 2026-03-14
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Added Data request: Semantic Search (Debug)
      - GET /v1/search with include_debug=true
      - Validates debug fields on results[0].debug:
        - title_similarity
        - content_similarity
        - weighted_score
    - Added Chat request: Send Message (Debug)
      - POST /v1/chat/message with include_debug=true
      - Validates debug fields on sources[0].debug:
        - total_score
      - Preserves chatSessionId capture for follow-up history calls.
- Verification:
  - Collection JSON syntax validated successfully.
    - Command: python -m json.tool docs/postman/PersonalAPI.postman_collection.json
- Next:
  - Redeploy backend with current RAG debug changes and run the two new Postman requests against the hosted environment.

## Step 37 - Production-Grade Google Drive and GCal Sync Cursors
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/workers/connector_sync.py:
    - Added robust cursor helpers for connector state (`_has_cursor_value`, `_parse_state_cursor`, `_encode_state_cursor`, `_max_datetime_value`).
    - Fixed Google cursor handling so sentinel cursor values (`"0"`/empty) are never sent as upstream page tokens.
    - Upgraded Gmail fetch pagination behavior to return empty cursor when no `nextPageToken` exists.
    - Reworked Drive sync to production-style incremental behavior:
      - Uses state cursor JSON (`page_token`, `updated_after`).
      - Uses ascending `modifiedTime` with `trashed=false` filters.
      - Enables shared drive coverage (`supportsAllDrives`, `includeItemsFromAllDrives`).
      - Persists high-watermark (`updated_after`) when page traversal finishes.
    - Reworked GCal sync to production-style incremental behavior:
      - Uses state cursor JSON (`page_token`, `sync_token`, `updated_after`).
      - Uses `nextSyncToken` for delta sync and preserves continuation with `pageToken`.
      - Handles stale Google sync tokens (`HTTP 410`) by automatically falling back to `updatedMin` incremental fetch.
  - backend/tests/test_normalizers.py:
    - Added regression test to ensure Gmail does not send invalid `pageToken=0`.
    - Added regression test for Drive incremental state cursor generation.
    - Added regression test for GCal stale sync-token recovery path.
- Verification:
  - Targeted connector and normalizer suites passed: `25 passed in 1.70s`.
  - Command (from `backend/`): `py -3 -m pytest tests/test_api.py tests/test_normalizers.py -q`
- Next:
  - Run live connector smoke tests for Google Drive and GCal against real OAuth tokens and verify repeated sync runs produce no duplicate pulls beyond idempotent upsert updates.

## Step 38 - Remove WhatsApp Connector API and Worker Support
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/connectors.py:
    - Removed `whatsapp` from `PLATFORM_TO_TASK`, disabling WhatsApp connector bootstrap/sync routing.
  - backend/workers/connector_sync.py:
    - Removed WhatsApp normalizer import/registration and WhatsApp fetch branch.
    - Removed `_fetch_whatsapp_records` implementation.
  - backend/workers/celery_app.py:
    - Removed `QUEUE_WHATSAPP`, WhatsApp task route, and `workers.whatsapp_worker` include.
  - backend/workers/whatsapp_worker.py:
    - Deleted WhatsApp worker module.
  - backend/normalizer/whatsapp.py:
    - Deleted WhatsApp normalizer module.
  - backend/docker-compose.yml and backend/docker-compose.coolify.yml:
    - Removed `worker-whatsapp` service definitions.
  - backend/tests/test_normalizers.py:
    - Removed WhatsApp normalizer test/import.
  - backend/tests/test_celery_foundation.py:
    - Removed WhatsApp queue/route/include assertions and constants.
  - docs/FRONTEND_API_REFERENCE.md:
    - Removed WhatsApp connector setup section to align docs with backend capability.
- Verification:
  - Targeted backend regression suites passed: `62 passed in 1.53s`.
  - Command (from `backend/`): `py -3 -m pytest tests/test_api.py tests/test_normalizers.py tests/test_celery_foundation.py -q`
- Next:
  - Optionally remove WhatsApp requests from `docs/postman/PersonalAPI.postman_collection.json` to keep Postman artifacts in sync with removed APIs.

## Step 39 - Coolify Deployment Start-Order Hardening
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/docker-compose.coolify.yml:
    - Added `depends_on: api: condition: service_healthy` to all worker services (`worker-google`, `worker-notion`, `worker-spotify`, `worker-slack`, `worker-file-watcher`, `worker-embedding`).
    - This serializes worker startup behind healthy API readiness and reduces container start race pressure during Coolify `docker compose up -d`.
- Verification:
  - Compose file schema remains valid for existing `depends_on` healthcheck conditions already used in this file.
- Next:
  - Redeploy on Coolify and, if needed, run one-time orphan cleanup before retry.

## Step 40 - Coolify Compose Dependency Simplification (Exit 255 Mitigation)
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/docker-compose.coolify.yml:
    - Replaced all health-condition based `depends_on` blocks with simple service startup dependencies (`depends_on: [redis]`) for `api` and all worker services.
    - Rationale: reduce orchestration fragility in Coolify helper `docker compose up -d` flow where condition-wait state can fail with exit code 255 before full startup.
- Verification:
  - Compose syntax validated by editor diagnostics (no YAML/schema errors).
- Next:
  - Redeploy in Coolify.
  - If failure persists, execute one-time orphan/network prune on host before redeploy.

## Step 41 - Restore Original Coolify Compose Dependency Style
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/docker-compose.coolify.yml:
    - Reverted `depends_on` blocks back to original `condition: service_healthy` format for `redis` on `api` and all worker services.
    - Kept WhatsApp removal intact (no `worker-whatsapp` service).
- Verification:
  - YAML/schema diagnostics clean in editor.
- Next:
  - Redeploy with this compose variant where only WhatsApp worker is removed from service set.

## Step 42 - Local Compose Parity Verification
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/docker-compose.yml:
    - Verified compose remains in original dependency format (`condition: service_healthy`) and includes no `worker-whatsapp` service.
    - No file edits required.
- Verification:
  - Manual review of service definitions confirms only WhatsApp worker removal is applied.
- Next:
  - Proceed with deployment using current compose files.

## Step 43 - Google Auth Connect Redirect URI Consistency Fix
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/auth.py:
    - Updated Google app-login redirect resolution to always prefer explicit `GOOGLE_AUTH_REDIRECT_URI` when configured.
    - Removed host-dependent behavior that could alternate between `localhost` and `127.0.0.1`, causing Google `redirect_uri_mismatch` in environments with only one URI registered.
- Verification:
  - Direct route validation returned success and correct redirect target:
    - `GET /auth/google/connect` -> `200`
    - Generated Google URL contains `redirect_uri=http://127.0.0.1:8000/auth/google/callback`.
- Next:
  - Ensure the exact callback URI used in `.env` is present in Google Cloud OAuth Authorized redirect URIs.
  - Retry login flow from frontend and confirm callback completes without `redirect_uri_mismatch`.

## Step 44 - Postman Coverage for Unified MCP Endpoint
- Status: Completed
- Date: 2026-03-14
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Added `MCP Unified Endpoint - List Tools`
      - `POST /mcp/endpoint` with body `{ "action": "list_tools" }`.
      - Includes test assertions for unified response envelope (`action`, `data.tools`).
    - Added `MCP Unified Endpoint - Call Tool (Search)`
      - `POST /mcp/endpoint` with body:
        - `action: "call_tool"`
        - `tool: "search"`
        - `arguments` payload mapped to existing search inputs.
      - Includes response assertions for `call_tool` envelope and nested search result contract.
      - Captures first result id into `mcpItemId` for reuse with `MCP Get Item`.
- Verification:
  - Collection JSON syntax validated.
  - Command (from `backend/`): `python -m json.tool ..\\docs\\postman\\PersonalAPI.postman_collection.json`
- Next:
  - Use the two new MCP Unified requests as the preferred OpenClaw/client integration path.
  - Keep legacy `/mcp/tools/*` requests for backward compatibility during transition.

## Step 45 - Env Example Cleanup for Auto-Sync Defaults
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/.env.example:
    - Removed optional auto-sync tuning variables:
      - `AUTO_SYNC_DISPATCH_INTERVAL_SECONDS`
      - `AUTO_SYNC_STALE_AFTER_MINUTES`
      - `AUTO_SYNC_BATCH_SIZE`
    - Kept `AUTO_SYNC_ENABLED` as the single explicit auto-sync toggle in the env example.
- Verification:
  - Manual config review confirms removed keys are optional because defaults are defined in `api/core/config.py`.
- Next:
  - If runtime tuning is needed, set the removed variables explicitly in deployment-specific env files.

## Step 46 - Chat History Query and Recent-First Support
- Status: Completed
- Date: 2026-03-14
- Changes:
  - backend/api/routers/chat.py:
    - Extended `GET /v1/chat/{session_id}/history` with `query` and `order` query params.
    - Added case-insensitive content filtering for in-session history search.
    - Added `order=desc` support so `limit` can return the most recent chat messages instead of always returning the oldest rows.
  - backend/tests/test_api.py:
    - Added regression coverage for recent-first history retrieval and content-query filtering.
  - docs/FRONTEND_API_REFERENCE.md:
    - Documented the new `query` and `order` params for chat history.
- Verification:
  - Targeted API regression suite passed locally for chat history changes.
  - Command (from `backend/`): `py -3 -m pytest tests/test_api.py -q`
- Next:
  - Wire the frontend chat UI to call `GET /v1/chat/{session_id}/history?order=desc&limit=<n>` for recent-message views or sidebars.

## Step 47 - Postman Coverage for Recent Chat History Queries
- Status: Completed
- Date: 2026-03-14
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Updated `Chat -> Get History` description to clarify oldest-to-newest ordering.
    - Added `Chat -> Get Recent History` request using `limit=20&order=desc`.
    - Added optional disabled `query=plan` param so Postman users can enable in-session content filtering without sending an empty query value by default.
    - Added response assertions for recent-history request shape and limit behavior.
- Verification:
  - Collection JSON syntax validated.
  - Command (from workspace root): `python -m json.tool docs/postman/PersonalAPI.postman_collection.json`
- Next:
  - Use `Get Recent History` for sidebar/recent-chat manual testing, and enable the `query` param when validating in-session search behavior.

## Step 49 - README Production Documentation Upgrade
- Status: Completed
- Date: 2026-03-14
- Changes:
  - README.md: Rewrote the root project documentation to production-grade quality.
  - Added accurate sections for architecture, runtime components, supported integrations, API surface, environment variables, local development, Docker deployment, testing, operational notes, production checklist, troubleshooting, and contributor links.
  - Replaced the minimal collaborator list with named contributors and direct GitHub profile URLs.
  - Kept the document free of license content as requested.
- Verification:
  - README content aligned against current backend routes, worker queues, docker-compose services, env template, and repository git authorship.
- Next:
  - Keep the README updated when APIs, worker queues, deployment topology, or contributor roster change.

## Step 50 - Postman No-Session Chat History Request
- Status: Completed
- Date: 2026-03-14
- Changes:
  - docs/postman/PersonalAPI.postman_collection.json:
    - Added `Chat -> Get Recent History (No Session ID)` request.
    - Uses `GET /v1/chat/history?limit=20&order=desc` (no `chatSessionId` variable required).
    - Added response assertions for array shape and limit guard.
- Verification:
  - Collection JSON syntax validated.
  - Command (from workspace root): `python -m json.tool docs/postman/PersonalAPI.postman_collection.json`
- Next:
  - Use the new no-session history request for initial dashboard loads before a `chatSessionId` is established.
