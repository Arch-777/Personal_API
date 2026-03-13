# Backend Implementation Plan - Person 2 (Workers + RAG + Integrations)

## Role Scope
Own connector workers, normalization pipeline, RAG engine, chat flow, WebSocket updates, and MCP integration.

## Timeline
- Week 1: Worker framework + queue setup
- Week 2: Connector ingestion + normalization
- Week 3: Embeddings + retrieval + chat pipeline
- Week 4: Realtime + MCP + validation

## Workstream 1: Async Processing Foundation
### Tasks
- Implement backend/workers/celery_app.py with queue routing and task settings.
- Configure worker startup commands aligned with docker-compose services.
- Add baseline retry, timeout, and dead-letter handling strategy.

### Deliverables
- Celery workers start and consume service-specific queues.
- Queue names standardized for all connectors.

## Workstream 2: Connector Workers
### Tasks
- Implement connector workers:
  - backend/workers/google_worker.py
  - backend/workers/whatsapp_worker.py
  - backend/workers/notion_worker.py
  - backend/workers/spotify_worker.py
- Implement file and embedding support workers:
  - backend/workers/file_watcher_worker.py
  - backend/workers/embedding_worker.py
- Integrate with connector records and token handling from Person 1 models.

### Deliverables
- Manual sync trigger processes data end-to-end.
- Worker tasks are idempotent and resumable.

## Workstream 3: Normalization Pipeline
### Tasks
- Define shared base interface in backend/normalizer/base.py.
- Implement platform normalizers:
  - backend/normalizer/gmail.py
  - backend/normalizer/drive.py
  - backend/normalizer/gcal.py
  - backend/normalizer/whatsapp.py
  - backend/normalizer/notion.py
  - backend/normalizer/spotify.py
- Ensure normalized payload maps to unified item schema.

### Deliverables
- All connectors emit consistent item structure.
- Data persisted to file-per-document layout and DB upsert path.

## Workstream 4: RAG and Chat Engine
### Tasks
- Implement RAG modules:
  - backend/rag/chunker.py
  - backend/rag/embedder.py
  - backend/rag/retriever.py
  - backend/rag/context.py
  - backend/rag/engine.py
- Implement chat endpoints in backend/api/routers/chat.py.
- Connect chat sessions/messages with retrieval results and citations.

### Deliverables
- Query returns answer, sources, and linked documents.
- Chat endpoint supports session creation/resume.

## Workstream 5: Realtime + MCP Integration
### Tasks
- Implement backend/api/routers/ws.py for push notifications.
- Implement backend/mcp/server.py exposing tool-based data access.
- Validate event payloads consumed by frontend hooks.

### Deliverables
- Frontend receives sync progress and completion events.
- MCP server can query/search user-scoped data securely.

## Workstream 6: Quality and Operational Readiness
### Tasks
- Add tests:
  - backend/tests/test_normalizers.py
  - backend/tests/test_rag.py
- Validate docker services:
  - backend/docker-compose.yml
  - backend/Dockerfile
- Confirm worker and API interoperability in local stack.

### Deliverables
- Test coverage for normalization and retrieval behavior.
- Local docker stack starts with healthy API, DB, Redis, and workers.

## Dependencies on Person 1
- Requires stable DB models and migration by end of Week 2.
- Requires auth/user context dependencies for secured chat and ws endpoints.
- Requires finalized search response schema for consistent RAG output formatting.

## Handoff Checklist
- Worker queue map shared with Person 1 for connector trigger API.
- RAG output schema synced with frontend and API contracts.
- Deployment notes added for scaling workers by queue load.
