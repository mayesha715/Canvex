# Canvex

Canvex is a collaborative whiteboard project built around FastAPI, PostgreSQL, Redis, and React. The backend uses PostgreSQL JSONB for flexible canvas element state, an append-only event log for auditability, and pgvector for later semantic search.

## Current Phase

Phase 2 is implemented as backend auth foundation:

- SQLAlchemy 2.0 async models
- Alembic migration setup
- Initial PostgreSQL schema migration
- Seed script with users, channel, pages, elements, and element events
- Password hashing with bcrypt
- JWT access tokens and rotating refresh tokens
- Auth endpoints for registration, login, refresh, logout, and current user lookup

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
