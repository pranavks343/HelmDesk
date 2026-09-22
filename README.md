# SupportPilot

A real-time, AI-augmented support ticketing platform. Built to demonstrate every line of the
target JD at final-year-student depth: every concept present, working, and explainable, not
production-hardened. See [agents.md](agents.md) for the full spec and design rationale.

## Architecture

```
React (Vite+TS) ──REST/WS──> FastAPI (api)
                                 │  publishes "ticket.created"
                                 ▼
                              Redis (pub/sub + cache)
                                 │
                                 ▼
                         agent-worker (Python, LangGraph)
                                 │  gRPC call: ClassifyTicket / DraftReply
                                 ▼
                         notifier (Node.js gRPC server)
                                 │  publishes "ticket.updated" + persists via api
                                 ▼
                              Redis ──> FastAPI ──WS──> React (live update)

Postgres: users, tickets, ticket_events (source of truth)
MongoDB:  chat_messages (per-ticket message stream, flexible schema)
```

Five services: `api` (FastAPI), `agent-worker` (Python/LangGraph), `notifier` (Node.js/gRPC),
`web` (React), plus Postgres/MongoDB/Redis.

## Quickstart (Docker)

```bash
cp .env.example .env   # edit JWT_SECRET / INTERNAL_SERVICE_TOKEN for anything shared
docker compose -f infra/docker-compose.yml up --build
```

- API: http://localhost:8000/docs
- Web: http://localhost:8080
- notifier gRPC: localhost:50051

## Quickstart (local, no Docker)

```bash
# datastores only
docker compose -f infra/docker-compose.yml up -d postgres mongo redis

# api
cd apps/api
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn main:app --reload --port 8000

# agent-worker (needs the shared proto compiled once - see below)
cd apps/agent-worker
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py

# notifier
cd apps/notifier && npm install && npm run dev

# web
cd web && npm install && npm run dev
```

### Generating the gRPC stubs

`apps/agent-worker/pb/` (Python) is generated, not committed:

```bash
cd apps/agent-worker
.venv/bin/python -m grpc_tools.protoc -I ../../proto \
  --python_out=pb --grpc_python_out=pb --pyi_out=pb ../../proto/ticket.proto
touch pb/__init__.py
```

`apps/notifier` loads `proto/ticket.proto` dynamically at runtime via `@grpc/proto-loader` - no
codegen step needed on the Node side.

## Testing

```bash
cd apps/api && .venv/bin/pytest -q            # 26 tests, sqlite+mongomock+fakeredis, no infra needed
cd apps/agent-worker && .venv/bin/pytest -q   # 27 tests, mocked LLM gateway + real FakeLLM/kb_search
cd apps/notifier && npm test                  # 8 tests (vitest)
cd web && npx vitest run                      # 7 tests (Testing Library)
```

Every test suite runs fully offline - no real Postgres/Mongo/Redis/LLM needed. `LLM_PROVIDER`
defaults to `fake` (deterministic, offline); set it to `anthropic` with `ANTHROPIC_API_KEY` to use
a real model.

## Repository layout

See [agents.md §3](agents.md) for the intended layout - `apps/`, `web/`, `proto/`, `infra/` mirror
it directly.

## Deviations from agents.md

- **CI workflow location**: agents.md §3 places it at `infra/.github/workflows/ci.yml`, but GitHub
  Actions only ever reads workflows from `<repo-root>/.github/workflows/` - it lives at
  [`.github/workflows/ci.yml`](.github/workflows/ci.yml) instead so it actually runs.
- **gRPC contract semantics**: `proto/ticket.proto`'s `TicketRequest` carries whichever fields
  matter for that call (classify fields for `ClassifyTicket`, draft fields for `DraftReply`)
  rather than the server computing anything - `agent-worker`'s own LangGraph pipeline
  (`graph.py`) does all the classification/drafting; `notifier` is a push/relay sink, not a
  second compute step. See the proto file's own comment for the full reasoning.
- **KB search**: keyword-based, not pgvector - agents.md §6 explicitly says "pick one, document
  why"; see `apps/api/core/kb_search.py`'s docstring.

## Security notes (enterprise-flavored, not production-grade)

- JWT access + refresh tokens, bcrypt password hashing, role-based `Depends()` guards
  (customer/agent/admin)
- Redis-backed rate limiting on auth + ticket-create
- `notifier -> api` internal calls use a shared-secret header (`X-Internal-Token`), not a user
  JWT - documented in `apps/api/core/internal_auth.py` as needing real mTLS/service identity for
  production
- No Kafka, no k8s, no multi-region, no real enterprise SSO - named as the production upgrade
  path for each, not implemented, to keep scope at final-year-project level (agents.md §13)
