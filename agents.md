# AGENTS.md — SupportPilot

Real-time, AI-augmented support ticketing platform. Built to demonstrate every line
of the target JD at final-year-student depth: not production-hardened, but every
concept present, working, and explainable in an interview.

## 1. JD → Feature Mapping

| JD requirement | Where it lives |
|---|---|
| Python, Node.js, React.js | Backend = Python/FastAPI. Frontend = React+TS. Node.js = small gRPC worker (`services/notifier`) |
| REST + gRPC APIs | FastAPI REST for client-facing API. gRPC between `api` and `agent-worker` |
| Event-driven backend | Redis Pub/Sub: ticket-created → agent-worker triages → publishes result → WebSocket push |
| PostgreSQL, MongoDB, Redis, WebSockets | Postgres = users/tickets (relational). Mongo = chat message log (unstructured, high write). Redis = cache + pub/sub + rate limiting. WS = live ticket feed |
| Agentic AI / LLM | LangGraph agent in `agent-worker`: classifies ticket, drafts reply, decides escalate/auto-close, calls a "KB search" tool |
| Docker, CI/CD, cloud, security | `docker-compose.yml`, GitHub Actions, JWT auth + RBAC + rate limiting, deployable to any single free-tier VM/Render/Railway |

## 2. Architecture

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
                                 │  publishes "ticket.updated"
                                 ▼
                              Redis ──> FastAPI ──WS──> React (live update)

Postgres: users, tickets, ticket_events (source of truth)
MongoDB:  chat_messages (per-ticket message stream, flexible schema)
```

Why this shape (interview answer): REST for client CRUD (simple, cacheable),
gRPC for internal service calls (typed contract, low overhead, shows you know
when NOT to use REST), Redis pub/sub as a lightweight event bus (justify vs
Kafka: scale doesn't need it, but name Kafka as the production upgrade path),
WS for push instead of client polling.

## 3. Repo Structure

```
supportpilot/
├── apps/
│   ├── api/                 # FastAPI — REST + WS + orchestration
│   │   ├── main.py
│   │   ├── routers/         # tickets.py, auth.py, kb.py
│   │   ├── models/          # SQLAlchemy models (Postgres)
│   │   ├── schemas/         # Pydantic
│   │   ├── mongo/           # motor client, chat message repo
│   │   ├── ws/              # connection manager
│   │   ├── core/            # config, security (JWT, RBAC deps), redis client
│   │   └── tests/
│   ├── agent-worker/        # Python — LangGraph agent, gRPC client
│   │   ├── graph.py         # agent state machine
│   │   ├── tools.py         # kb_search, sentiment, priority_score
│   │   ├── grpc_client.py
│   │   └── main.py          # redis subscriber loop
│   └── notifier/            # Node.js/TS — gRPC server
│       ├── src/server.ts
│       └── proto/
├── web/                      # React + TS + Vite
│   ├── src/pages/            # Login, Dashboard, TicketDetail
│   ├── src/hooks/useWebSocket.ts
│   └── src/api/client.ts
├── proto/
│   └── ticket.proto           # shared gRPC contract
├── infra/
│   ├── docker-compose.yml     # postgres, mongo, redis, api, agent-worker, notifier, web
│   └── .github/workflows/ci.yml
└── AGENTS.md
```

## 4. Setup Commands

```bash
# one-time
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d postgres mongo redis

# backend
cd apps/api && pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000

# agent worker
cd apps/agent-worker && pip install -r requirements.txt
python main.py

# notifier (gRPC, Node)
cd apps/notifier && npm i && npm run dev

# frontend
cd web && npm i && npm run dev
```

Full stack in containers: `docker compose -f infra/docker-compose.yml up --build`

## 5. Core Data Model (Postgres)

- `users(id, email, hashed_password, role[agent|admin|customer], created_at)`
- `tickets(id, user_id, title, status[open|triaged|in_progress|resolved], priority, ai_summary, created_at, updated_at)`
- `ticket_events(id, ticket_id, type, payload_json, created_at)` — audit trail

MongoDB: `chat_messages { ticket_id, sender, text, embedding?, created_at }`

## 6. API Surface (REST, `apps/api/routers`)

- `POST /auth/login` → JWT
- `POST /tickets` / `GET /tickets` / `GET /tickets/{id}`
- `POST /tickets/{id}/messages` (writes Mongo, publishes `ticket.message`)
- `GET /kb/search?q=` (simple pgvector or keyword search — pick one, document why)
- `WS /ws/tickets/{id}` — live status + agent-drafted-reply stream

## 7. gRPC Contract (`proto/ticket.proto`)

```proto
service TicketAgent {
  rpc ClassifyTicket (TicketRequest) returns (ClassifyResponse);
  rpc DraftReply (TicketRequest) returns (DraftResponse);
}
```
`api` never calls this directly — `agent-worker` calls it on `notifier` to push
the final result out (demonstrates gRPC used for internal service-to-service,
not client-facing).

## 8. Agentic AI Design (`agent-worker/graph.py`)

LangGraph state machine, 4 nodes:
1. `classify` — LLM call, outputs category + priority
2. `search_kb` — tool call against KB (pgvector or keyword)
3. `draft_reply` — LLM drafts response using KB context
4. `decide` — auto-resolve if confidence high, else escalate to human agent

Be ready to explain: why a graph over a single prompt (multi-step, tool use,
conditional branching), how state/memory is passed between nodes, and the
fallback when the LLM call fails/times out.

## 9. Security (enterprise-flavored, not production-grade)

- JWT access token + refresh token, `core/security.py`
- Role-based `Depends()` guards (`require_role("agent")`)
- Redis-based rate limiting per IP/user on auth + ticket-create endpoints
- Input validation via Pydantic everywhere; no raw SQL
- Secrets via `.env` (never committed), CORS locked to frontend origin

## 10. CI/CD (`.github/workflows/ci.yml`)

- On PR: lint (ruff, eslint) → unit tests (pytest, vitest) → build Docker images
- On merge to main: build + push images (tag = short SHA) — stop before actual
  cloud deploy step; document the deploy step as a manual/optional stretch goal

## 11. Testing

- `apps/api/tests`: pytest + httpx for REST, pytest-asyncio for WS
- `agent-worker`: mock LLM calls, test graph transitions deterministically
- `web`: vitest + React Testing Library for key components

## 12. Build Order (milestones)

1. Postgres models + auth + ticket CRUD (REST only)
2. React shell: login, ticket list, ticket detail
3. WebSocket live updates (skip AI, just status changes)
4. Mongo chat log + message endpoint
5. Redis pub/sub wiring between api ↔ agent-worker
6. LangGraph agent (start with 1 node: classify) → grow to full graph
7. gRPC contract + notifier service
8. Dockerize everything, docker-compose up end-to-end
9. GitHub Actions CI
10. Rate limiting + RBAC pass

## 13. Explicit Non-Goals (say this in the interview, don't hide it)

No Kafka, no k8s, no multi-region, no real enterprise SSO — named as the
"production upgrade path" for each, not implemented, to keep scope at
final-year-project level while proving you know what's missing and why.
