# Backend Implementation Plan - Person 1 (Core API + Data Layer)

## Role Scope
Own the FastAPI foundation, database layer, authentication, and core read/query endpoints.

## Timeline
- Week 1: Project baseline + core infrastructure
- Week 2: Auth + models + schemas
- Week 3: Core routers + API hardening
- Week 4: Integration support + tests

## Workstream 1: Project Foundation
### Tasks
- Initialize backend runtime dependencies in requirements.txt.
- Set up backend/api/main.py with FastAPI app, middleware, and router registration.
- Create backend/api/core/config.py for environment settings.
- Create backend/api/core/db.py for SQLAlchemy engine/session management.
- Add backend/.env.example with required keys.

### Deliverables
- App starts locally with uvicorn.
- DB session dependency usable in routes.
- Config values load from env safely.

## Workstream 2: Security and Auth
### Tasks
- Implement backend/api/core/security.py for token hashing/encryption helpers.
- Implement backend/api/core/auth.py for user auth dependencies.
- Build backend/api/routers/auth.py with register/login/me flows.
- Define auth request/response schemas in backend/api/schemas/auth.py.

### Deliverables
- JWT-based auth working for protected routes.
- Passwords hashed and never stored plaintext.
- Unauthorized requests blocked consistently.

## Workstream 3: Database Models and Schemas
### Tasks
- Implement models:
  - backend/api/models/user.py
  - backend/api/models/connector.py
  - backend/api/models/item.py
  - backend/api/models/api_key.py
  - backend/api/models/chat_session.py
  - backend/api/models/access_log.py
- Implement schemas:
  - backend/api/schemas/item.py
  - backend/api/schemas/search.py
  - backend/api/schemas/connector.py
  - backend/api/schemas/chat.py
- Draft initial schema in backend/migrations/001_initial.sql.

### Deliverables
- Models align with architecture docs and relationships.
- Migration script can bootstrap schema from empty DB.

## Workstream 4: Core API Routers
### Tasks
- Implement read/query routers:
  - backend/api/routers/emails.py
  - backend/api/routers/documents.py
  - backend/api/routers/search.py
- Implement developer key APIs in backend/api/routers/developer.py.
- Add consistent error handling and response structure.

### Deliverables
- Core endpoints return paginated, validated responses.
- Semantic search endpoint contract finalized for frontend.

## Workstream 5: Quality and Integration Support
### Tasks
- Add tests:
  - backend/tests/test_api.py
  - backend/tests/test_search.py
- Provide API contract notes for Person 2 integration points:
  - Connector trigger API
  - Chat endpoint payloads
  - WebSocket event envelope

### Deliverables
- Passing baseline tests for auth and core endpoints.
- Stable contracts for workers and realtime/chat integrations.

## Dependencies on Person 2
- Person 2 needs finalized DB models and search contracts by end of Week 2.
- Person 2 consumes auth dependency and DB session patterns from core modules.

## Handoff Checklist
- API router registration merged in main.py.
- Auth middleware and dependencies documented.
- Migration script reviewed with Person 2 before worker integration.
