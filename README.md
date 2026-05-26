# Canvex

Canvex is a collaborative whiteboard project built around FastAPI, PostgreSQL, Redis, and React. The backend uses PostgreSQL JSONB for flexible canvas element state, an append-only event log for auditability, and pgvector for later semantic search.

## Current Phase

Phase 6 is implemented with offline-first canvas persistence and reconnect sync:

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
- React + Fabric.js canvas UI with select, rectangle, ellipse, and text tools
- WebSocket client for element ops, locks, and live cursors
- Channel/page shell with authentication flow
- Yjs document per whiteboard page
- IndexedDB persistence for local page element state
- Offline operation queue for create/update/delete element operations
- Online/offline detection with a visible workspace status chip
- Reconnect replay of queued operations through the existing authenticated WebSocket
- `protocol: "canvas"` marker on realtime messages for future protocol expansion

## Local Full-Stack Setup

The backend and frontend run as separate development servers:

- FastAPI API: `http://localhost:8000`
- Vite frontend: `http://localhost:5173`
- PostgreSQL: Docker service `postgres`
- Redis: Docker service `redis`

Start infrastructure first, then run the backend and frontend in separate terminals.

## Local Backend Setup

1. Copy `backend/.env.example` to `backend/.env`.
2. Start PostgreSQL and Redis:

```powershell
docker compose up -d postgres redis
```

3. Install Python dependencies in the shared project virtual environment, if needed:

```powershell
C:\Users\Istiak\Desktop\Projects\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

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

## Local Frontend Setup

1. Copy `frontend/.env.example` to `frontend/.env` and adjust `VITE_API_URL` if needed.
2. Install frontend dependencies:

```powershell
cd frontend
npm install
```

3. Start the Vite dev server:

```powershell
npm run dev
```

Open `http://localhost:5173` in the browser. The frontend expects the API URL from `frontend/.env`:

```text
VITE_API_URL=http://localhost:8000
```

## Useful Checks

Backend:

```powershell
C:\Users\Istiak\Desktop\Projects\.venv\Scripts\python -m ruff check backend
C:\Users\Istiak\Desktop\Projects\.venv\Scripts\python backend\scripts\check_phase5_ws.py
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
```

## Phase 6 Notes

- Element create/update/delete operations are persisted through the backend WebSocket route and still write to the append-only event log.
- Create acknowledgements use a client operation id so rapid local creates are matched to the correct Fabric object.
- The canvas stores a local Yjs `elements` map in IndexedDB for each page, so cached elements can be restored when the network is unavailable.
- While offline, element operations are queued locally. When the browser reconnects and the page WebSocket opens, queued operations are replayed with their original vector clocks.
- The installed `y-websocket` dependency is reserved for a later binary Yjs transport. The current Phase 6 implementation keeps the existing JSON WebSocket contract and adds a `protocol` field so protocol routing can evolve without breaking canvas messages.
