# Canvex

Canvex is a collaborative whiteboard project built around FastAPI, PostgreSQL, Redis, and React. The backend uses PostgreSQL JSONB for flexible canvas element state, an append-only event log for auditability, and pgvector for later semantic search.

## Current Phase

Phase 5 backend is implemented as the realtime whiteboard transport layer:

- SQLAlchemy 2.0 async models
- Alembic migration setup
- Initial PostgreSQL schema migration
- Seed script with users, channel, pages, elements, and element events
- Password hashing with bcrypt
- JWT access tokens and rotating refresh tokens
- Auth endpoints for registration, login, refresh, logout, and current user lookup
- Channel CRUD
- Channel membership RBAC
- Invite generation and acceptance
- Whiteboard page create/list/update/soft-delete endpoints
- Element create/list/update/soft-delete endpoints
- Element JSONB type and text search filters
- Append-only element event logging for every element mutation
- Element-level permission checks for role-specific edit/delete locks
- WebSocket room manager for page-scoped collaboration
- Authenticated `WS /ws/{page_id}` endpoint
- WebSocket element create/update/delete operations backed by the Phase 4 event log
- Redis-backed element locks with disconnect cleanup
- Cursor presence broadcast and `GET /pages/{id}/presence`

## Local Backend Setup

1. Copy `backend/.env.example` to `backend/.env`.
2. Start PostgreSQL and Redis:

```powershell
docker compose up -d postgres redis
```

3. Install Python dependencies in `backend/`.
4. Run migrations:

```powershell
cd backend
alembic upgrade head
```

5. Seed development data:

```powershell
python scripts/seed.py
```

6. Start the API:

```powershell
uvicorn app.main:app --reload
```

The smoke test endpoint is `GET /health`.
