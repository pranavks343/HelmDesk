# agents.md — SupportPilot v2

> Build spec for a coding agent. Read the whole file before writing code.
> Follow the phases in §17 in order. Do not skip a phase gate.

---

## 0. Rules for the coding agent

1. **Every one of the 31 concepts in §3 must exist as working, tested code.** No concept may be
   "mentioned in a comment" only. Each has a named test (§15) and a CLI demo (§14).
2. **No contrived usage.** Each concept is placed where a real support system would need it
   (§2 explains why). If you find yourself forcing a feature somewhere it doesn't belong, stop and
   re-read the node spec.
3. **Verify APIs against the installed version.** Target is `langgraph>=1.2,<2`. Before using any
   import listed in §4.2, confirm it exists in the installed package. Record every confirmed
   import, every renamed/moved API, and every default value you relied on (e.g. default
   recursion limit) in `docs/API_NOTES.md`. If an API differs from this spec, adapt the code and
   note it there. **Never drop a concept because an API moved.**
4. **Deterministic by default.** The whole project, including all tests, must run offline with
   no API key using the fake LLM (§8). The real `ChatAnthropic` path is opt-in.
5. **Existing code first.** Concepts 1–13 are already built and tested in the current repo.
   Phase 0 (§17) is an audit and migration, not a rewrite. Keep what works; move it into the
   new layout; keep its tests green throughout.
6. Type hints everywhere. `ruff` and `mypy` clean. No `print` in library code — use the `rich`
   console in the CLI layer and the stream writer inside nodes.
7. Small commits, one per logical step, with messages like `feat(c19): time-travel fork`.

---

## 1. What we are building

**SupportPilot** is a multi-agent customer-support desk for a fictional SaaS company,
**Nimbus Cloud**. A customer types a message in a CLI chat. The system:

- screens the message with an **input guardrail** (PII redaction, prompt-injection block);
- recalls who the customer is from **long-term memory** (exact profile + semantic facts);
- keeps the thread short with **trimming + rolling summary**;
- lets an LLM **supervisor** route to one of three specialist agents:
  - **KB agent** — agentic RAG over docs/forum/changelog with fan-out retrieval,
    caching, retries, a deferred merge node, and a grade → rewrite loop;
  - **Tech agent** — a tool-calling ReAct loop (service status, order lookup, error codes) that
    can **hand off** to billing mid-conversation;
  - **Billing agent** — a subgraph with its **own private schema** that proposes refunds;
- pauses for **human approval** (two sequential interrupts: approve/reject, then edit reply)
  before any refund is executed;
- runs an **output guardrail** before replying;
- streams progress events and **LLM tokens** live to the terminal;
- persists every step to SQLite so a thread can be **resumed after a crash, inspected,
  replayed, and forked**;
- exposes a **Functional-API** "daily digest" workflow, a **Studio** config, a **Mermaid**
  export, and an **evaluation harness**.

### Non-goals (do not build)
No web framework, no frontend, no Docker, no Postgres, no auth, no deployment. The only server
is `langgraph dev` for Studio (concept 30).

---

## 2. Why each concept lives where it does

| Need in a real support desk | Concept that solves it |
|---|---|
| Messages accumulate, other fields overwrite, citations must dedupe | Reducers (1, 2) |
| Search several knowledge sources in parallel | `Send` (3) |
| One node both decides and updates state | `Command(goto)` (4) |
| Customer returns tomorrow to the same ticket | Threads + checkpointers (5, 6) |
| Refunds need a human | Interrupts (7, 18) |
| Forum API is flaky; LLM API has transient errors | `RetryPolicy` (8) |
| Reusable RAG pipeline / isolated billing logic | Subgraphs (9, 17) |
| User should see progress, not a frozen terminal | Streaming (10, 22) |
| Remember plan tier and preferences across tickets | Store (11, 21) |
| Some paths are fixed pipelines, some need judgement | Workflow vs agent (12) |
| Answers must be grounded and self-correcting | Agentic RAG (13) |
| Tech agent must call real functions | Tool loop (14) |
| Tech issue turns into a billing issue | Handoff via `Command.PARENT` (15) |
| Routing/grading must be machine-readable | Structured output (16) |
| Debugging "why did it refund?" | Time travel (19) |
| Long threads blow the context window | Trim + summary (20) |
| Same question asked 50 times a day | Node caching (23) |
| Sources finish at different speeds; merge once | Deferred node (24) |
| Per-request config (user, model, limits) that is not state | Runtime context (25) |
| PII and jailbreaks | Guardrails (26) |
| Agent stuck in a loop must degrade gracefully | Recursion limit + fallback (27) |
| Offline tests, real model in prod | Swappable LLM (28) |
| Simple batch job doesn't need a graph | Functional API (29) |
| Visual debugging, docs | Studio + Mermaid (30) |
| Prove it works, catch regressions | Eval harness (31) |

---

## 3. Concept checklist (all 31 required)

**Already built (migrate, keep green):**
1 Reducers (`add` + custom) · 2 `add_messages` · 3 `Send` · 4 `Command(update, goto)` ·
5 Persistence (threads, `get_state`, `get_state_history`, `update_state`) ·
6 Checkpointers (`SqliteSaver` vs `InMemorySaver`/`MemorySaver`) · 7 Interrupts + `Command(resume)` ·
8 `RetryPolicy` · 9 Subgraphs · 10 Streaming (`values`, `updates`, `debug`, sync + async) ·
11 Long-term memory (`Store`, namespaces) · 12 Workflow vs agent routing · 13 Agentic RAG

**New in v2:**
14 Tool loop (`ToolNode`, `tools_condition`) · 15 Supervisor + handoffs (`Command.PARENT`) ·
16 Structured output (Pydantic) · 17 Subgraph with different schema + explicit mapping ·
18 Multiple sequential interrupts · 19 Time travel (replay, fork) · 20 Trimming + rolling summary ·
21 Semantic memory (`store.search`) · 22 Custom + token streaming · 23 `CachePolicy` ·
24 `defer=True` · 25 `context_schema` / `Runtime` · 26 Guardrails node ·
27 Recursion limit + fallback · 28 Fake vs `ChatAnthropic` · 29 Functional API ·
30 Studio / dev server + Mermaid export · 31 pytest evaluation harness

The full traceability matrix is in §16.

---

## 4. Tech stack

### 4.1 Dependencies (`pyproject.toml`, Python 3.11+)

```toml
[project]
name = "supportpilot"
requires-python = ">=3.11"
dependencies = [
  "langgraph>=1.2,<2",
  "langgraph-checkpoint-sqlite",
  "langchain-core>=1.0",
  "langchain-anthropic>=1.0",
  "pydantic>=2.7",
  "typer>=0.12",
  "rich>=13",
  "python-dotenv>=1.0",
  "aiosqlite>=0.20",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "pytest-cov>=5", "ruff", "mypy"]
studio = ["langgraph-cli[inmem]"]

[project.scripts]
supportpilot = "supportpilot.cli:app"
```

No vector DB, no embedding API. Retrieval (TF-IDF) and embeddings (feature hashing) are
implemented in-repo so everything runs offline.

### 4.2 Imports to verify (record results in `docs/API_NOTES.md`)

```python
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages, REMOVE_ALL_MESSAGES
from langgraph.types import Send, Command, interrupt, RetryPolicy, CachePolicy
from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.memory import InMemorySaver          # MemorySaver is the older alias
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.memory import InMemoryStore
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langgraph.managed import RemainingSteps
from langgraph.errors import GraphRecursionError
from langgraph.func import entrypoint, task

from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage, ToolMessage,
                                     RemoveMessage, AnyMessage, trim_messages)
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.embeddings import Embeddings
from langchain_anthropic import ChatAnthropic
```

Also note in `API_NOTES.md`: the `add_node` keyword for retries (`retry_policy=` in 1.x),
the default recursion limit, how cache hits surface in the `updates` stream, and whether the
opt-in `version="v2"` stream/invoke format is available (introduced in 1.1).

---

## 5. Architecture

### 5.1 Parent graph

```
START
  │
  ▼
input_guardrail ──(blocked)──────────────────────────────► blocked_reply ──► END
  │ (ok)
  ▼
load_memory            (Store: exact profile + semantic search)
  │
  ▼
manage_context         (trim + rolling summary, RemoveMessage)
  │
  ▼
supervisor ──Command(goto)──┬──► kb_agent        [subgraph, SHARED schema]  ──┐
  ▲                         ├──► tech_agent      [subgraph, tool loop]      ──┤
  │                         ├──► billing_agent   [wrapper → subgraph, OWN schema]
  │                         ├──► fallback        (low confidence / step budget)
  │                         └──► compose_reply                                │
  │                                                                           │
  └────────────────── (agent returns control) ◄───────────────────────────────┘
                                   tech_agent ──Command.PARENT──► billing_agent (handoff)
billing_agent ──► human_review (interrupt #1 approve, interrupt #2 edit) ──► execute_refund
                                                                               │
compose_reply ◄────────────────────────────────────────────────────────────────┘
  │
  ▼
output_guardrail ──(fail, 1st time)──► compose_reply
  │ (pass / fail twice → safe fallback text)
  ▼
save_memory ──► END
```

### 5.2 KB agent subgraph (shared schema with parent)

```
START ► plan_retrieval ─Send×3─► retrieve_source  (cache + retry)
                                    │ docs, changelog: 1 hop ───────────────┐
                                    │ forum: ► rerank_forum (extra hop) ─────┤
                                                                             ▼
                                                   merge_sources (defer=True)
                                                             ▼
                                                        generate  (token-streamed)
                                                             ▼
                                                          grade   (structured)
                                   ┌──── relevant ───────────┤
                                   ▼                         └── not relevant & rewrites < 2 ► rewrite ► plan_retrieval
                                  END                        └── not relevant & rewrites ≥ 2 ► END (flag low_confidence)
```

### 5.3 Tech agent subgraph (ReAct)

```
START ► tech_llm ─tools_condition─► tools (ToolNode) ─► tech_llm
                       └─ no tool calls ─► END
tools may execute `transfer_to_billing` → Command(goto="billing_agent", graph=Command.PARENT)
```

### 5.4 Billing subgraph (private `BillingState`)

```
START ► load_account ► assess_refund (structured: RefundProposal) ► END
```
Called from parent node `billing_agent` via explicit `to_billing()` / `from_billing()` mappers.

---

## 6. Repository layout

```
supportpilot/
├── agents.md
├── README.md
├── pyproject.toml
├── langgraph.json                       # Studio config (c30)
├── .env.example                         # SUPPORTPILOT_LLM=fake, ANTHROPIC_API_KEY=, ANTHROPIC_MODEL=
├── data/
│   ├── kb/{docs,forum,changelog}/*.md   # 14–18 short articles total
│   └── crm.json                         # customers, orders, invoices, service status
├── src/supportpilot/
│   ├── __init__.py
│   ├── config.py                        # env loading, paths, constants
│   ├── context.py                       # SupportContext dataclass (c25)
│   ├── schemas.py                       # Pydantic models (c16)
│   ├── state.py                         # ParentState, KBState alias, reducers (c1, c2)
│   ├── reducers.py                      # merge_citations, append_unique (c1)
│   ├── llm/
│   │   ├── gateway.py                   # LLMGateway protocol (c28)
│   │   ├── fake.py                      # FakeGateway, deterministic (c28)
│   │   ├── anthropic.py                 # AnthropicGateway (c28)
│   │   └── factory.py                   # get_gateway(runtime.context)
│   ├── retrieval/
│   │   ├── tfidf.py                     # in-repo TF-IDF retriever
│   │   └── embeddings.py                # HashingEmbeddings for Store index (c21)
│   ├── tools/
│   │   ├── crm.py                       # lookup_order, lookup_invoice, check_service_status
│   │   ├── errors.py                    # get_error_code_doc
│   │   └── handoff.py                   # transfer_to_billing (c15)
│   ├── guardrails/
│   │   ├── input.py                     # PII redaction, injection, length (c26)
│   │   └── output.py                    # grounding, PII leak, refund-amount consistency (c26)
│   ├── memory/
│   │   ├── store.py                     # build_store(), namespaces (c11, c21)
│   │   └── short_term.py                # trim + summarize helpers (c20)
│   ├── nodes/
│   │   ├── guard_nodes.py               # input_guardrail, blocked_reply, output_guardrail
│   │   ├── memory_nodes.py              # load_memory, save_memory
│   │   ├── context_nodes.py             # manage_context
│   │   ├── supervisor.py                # supervisor, fallback (c4, c12, c15, c16, c27)
│   │   ├── human_review.py              # two interrupts (c7, c18)
│   │   ├── refund.py                    # execute_refund (idempotent)
│   │   └── compose.py                   # compose_reply (token-streamed)
│   ├── subgraphs/
│   │   ├── kb_agent.py                  # c3, c8, c9, c13, c23, c24
│   │   ├── tech_agent.py                # c14, c15
│   │   └── billing_agent.py             # c17
│   ├── graph.py                         # build_graph(), make_graph() for Studio
│   ├── persistence.py                   # checkpointer factories, history/replay/fork (c5, c6, c19)
│   ├── streaming.py                     # renderers for all stream modes (c10, c22)
│   ├── functional/
│   │   └── daily_digest.py              # @entrypoint / @task (c29)
│   └── cli.py                           # Typer app (§14)
├── evals/
│   ├── golden.jsonl                     # 30 labelled cases (c31)
│   ├── metrics.py
│   └── run_eval.py                      # writes evals/report.md
├── scripts/
│   └── export_graph.py                  # Mermaid export (c30)
├── docs/
│   ├── API_NOTES.md
│   ├── CONCEPTS.md                      # 1 section per concept: what, where, why, gotcha
│   └── graph.mmd                        # generated
└── tests/
    ├── conftest.py
    ├── unit/                            # reducers, guardrails, tools, retriever, embeddings, schemas
    ├── concepts/test_c01_*.py … test_c31_*.py   # exactly one file per concept
    └── e2e/test_scenarios.py            # the 8 end-to-end stories in §15.3
```

---

## 7. State, context, and schemas

### 7.1 Pydantic models (`schemas.py`, c16)

```python
class RouteDecision(BaseModel):
    next: Literal["kb_agent", "tech_agent", "billing_agent", "compose_reply", "fallback"]
    confidence: float = Field(ge=0, le=1)
    reason: str

class GradeResult(BaseModel):
    relevant: bool
    grounded: bool
    missing: str | None = None       # what the answer lacked; feeds rewrite

class RewrittenQuery(BaseModel):
    query: str

class Citation(BaseModel):
    doc_id: str
    source: Literal["docs", "forum", "changelog"]
    title: str
    score: float
    snippet: str

class RefundProposal(BaseModel):
    invoice_id: str
    amount: float = Field(ge=0)
    currency: Literal["USD", "INR", "EUR"]
    reason: str
    auto_approvable: bool

class MemoryFact(BaseModel):
    text: str                        # "Prefers email over phone"
    category: Literal["preference", "account", "issue_history"]

class ExtractedMemories(BaseModel):
    facts: list[MemoryFact]

class GuardrailVerdict(BaseModel):
    allowed: bool
    flags: list[str]
    redacted_text: str
```

### 7.2 Custom reducers (`reducers.py`, c1)

```python
def merge_citations(left: list[Citation], right: list[Citation]) -> list[Citation]:
    """Union by doc_id, keep the higher score, sort by score desc. Pure, no mutation."""

def append_unique(left: list[str], right: list[str]) -> list[str]:
    """Append preserving order, skip duplicates. Used for guardrail flags and audit trail."""
```

Both must handle `left` being empty/None and must be unit-tested for idempotence
(`r(r(a, b), b) == r(a, b)`) and associativity on sample data.

### 7.3 Parent state (`state.py`)

```python
from operator import add

class ParentState(TypedDict, total=False):
    # c2 — conversation
    messages: Annotated[list[AnyMessage], add_messages]
    summary: str                                             # c20 rolling summary

    # routing
    route: RouteDecision | None                              # c16
    active_agent: str
    hops: Annotated[int, add]                                # c1 built-in `add` on ints: supervisor loop counter

    # KB agent (shared with kb subgraph)
    query: str
    raw_hits: Annotated[list[Citation], add]                 # c1 `add`: Send branches append
    citations: Annotated[list[Citation], merge_citations]    # c1 custom
    draft_answer: str
    grade: GradeResult | None
    rewrite_count: int
    low_confidence: bool

    # memory (c11, c21)
    profile: dict
    recalled_facts: list[str]

    # billing / HITL
    refund: RefundProposal | None
    review: dict                                             # {"decision": ..., "edited_reply": ...}
    refund_executed: bool

    # guardrails & audit
    guardrail_flags: Annotated[list[str], append_unique]     # c1 custom
    audit: Annotated[list[str], append_unique]
    output_retry: int

    final_answer: str
    remaining_steps: RemainingSteps                          # c27 managed value
```

The KB subgraph is compiled against a `KBState` that is a **subset** of these keys with the
**same names and reducers** (shared-schema pattern, c9). The billing subgraph uses a
**disjoint** schema (c17).

### 7.4 Runtime context (`context.py`, c25)

```python
@dataclass(frozen=True)
class SupportContext:
    user_id: str
    plan_tier: Literal["free", "pro", "enterprise"] = "free"
    llm_provider: Literal["fake", "anthropic"] = "fake"
    model_name: str = "claude-sonnet-5"                  # overridable via ANTHROPIC_MODEL
    refund_auto_approve_limit: float = 20.0
    max_context_tokens: int = 1200
    summarize_after_messages: int = 12
    flaky_forum_failures: int = 1                        # c8 demo knob
    fake_behavior: Literal["normal", "tool_loop", "bad_answer"] = "normal"   # test knobs
```

Rules:
- `StateGraph(ParentState, context_schema=SupportContext)`.
- Nodes that need it take `runtime: Runtime[SupportContext]` and read `runtime.context`,
  `runtime.store`, and `runtime.stream_writer`.
- Invoke with `graph.invoke(inputs, config, context=SupportContext(...))`.
- **Context is never written to state.** `CONCEPTS.md` must explain state vs config vs context.

---

## 8. LLM layer (c16, c28)

### 8.1 Gateway protocol (`llm/gateway.py`)

All LLM access goes through one interface so the rest of the code never knows which model runs.

```python
class LLMGateway(Protocol):
    def route(self, messages, summary, profile) -> RouteDecision: ...
    def grade(self, question, answer, citations) -> GradeResult: ...
    def rewrite(self, question, missing) -> RewrittenQuery: ...
    def generate_answer(self, question, citations) -> AIMessage: ...          # token-streamable
    def compose_reply(self, messages, context_blob) -> AIMessage: ...         # token-streamable
    def tech_step(self, messages, tools) -> AIMessage: ...                    # may carry tool_calls
    def assess_refund(self, account, complaint) -> RefundProposal: ...
    def summarize(self, prior_summary, messages) -> str: ...
    def extract_memories(self, messages) -> ExtractedMemories: ...
```

`factory.get_gateway(ctx: SupportContext) -> LLMGateway` picks the implementation from
`ctx.llm_provider` (default from env `SUPPORTPILOT_LLM`, default `fake`).

### 8.2 `AnthropicGateway`
- `ChatAnthropic(model=ctx.model_name, temperature=0)`.
- Structured methods use `.with_structured_output(<PydanticModel>)`.
- `tech_step` uses `.bind_tools(TECH_TOOLS)`.
- `generate_answer` / `compose_reply` call the model normally inside the node so
  `stream_mode="messages"` captures tokens.
- Tests that hit it are marked `@pytest.mark.live` and skipped when `ANTHROPIC_API_KEY` is unset.

### 8.3 `FakeGateway` (deterministic, the default)
- **Structured methods**: rule-based. `route` uses keyword/regex rules
  (refund/charge/invoice → billing; error code / outage / order # → tech; how/what/why → kb;
  greetings/thanks → compose_reply; gibberish → fallback with confidence 0.3).
  Returns a real `RouteDecision` instance — Pydantic validation is exercised either way.
- **Token streaming**: `generate_answer` and `compose_reply` build the reply text
  deterministically (template + top citations), then return
  `GenericFakeChatModel(messages=iter([AIMessage(content=text)])).invoke(prompt)` so
  LangGraph's `messages` stream mode yields real token chunks with no network.
- **Tool calls**: `tech_step` returns `AIMessage(content="", tool_calls=[...])` built from regexes
  (`ORD-\d+` → `lookup_order`, `E\d{3}` → `get_error_code_doc`, "down/outage" →
  `check_service_status`, "charged twice / refund" → `transfer_to_billing`). When the last message
  is a `ToolMessage` it returns a final text answer.
- `fake_behavior="tool_loop"` makes `tech_step` call `check_service_status` forever (c27 test).
- `fake_behavior="bad_answer"` makes the first `generate_answer` ungrounded so the grade → rewrite
  loop and output guardrail both trigger (c13, c26 tests).

---

## 9. Data and tools

### 9.1 Knowledge base (`data/kb/`)
14–18 Markdown files, each with front-matter `id`, `title`, `source`. Topics: SSO setup, API rate
limits, error codes E101–E120, backups, billing cycles, refund policy, plan comparison, a known
outage post-mortem (changelog), community workarounds (forum). Write realistic content,
120–250 words each.

### 9.2 Retriever (`retrieval/tfidf.py`)
Pure-Python TF-IDF with cosine similarity, per-source index, `search(query, source, k=3)
-> list[Citation]`. Normalise query (lowercase, strip punctuation) — the same normaliser is used
by the cache key (c23).

### 9.3 CRM (`data/crm.json`) and tools (`tools/`)
Tools are LangChain `@tool` functions reading `crm.json`:

| Tool | Args | Returns |
|---|---|---|
| `check_service_status` | `service: str` | status, since, incident id |
| `lookup_order` | `order_id: str` | plan, seats, status |
| `get_error_code_doc` | `code: str` | meaning, fix |
| `lookup_invoice` | `invoice_id: str` (billing subgraph only, called directly, not via ToolNode) | amount, date, status |
| `transfer_to_billing` | `reason: str`, `tool_call_id: Annotated[str, InjectedToolCallId]` | `Command` (see §10.4) |

`execute_refund` is **not** a tool the LLM can call. Only the graph calls it, after approval.

---

## 10. Node specifications

Each spec lists: inputs read → outputs written, concept tags, and the exact return style.

### 10.1 `input_guardrail` (c26)
- Reads last `HumanMessage`.
- Redacts emails, phone numbers, 13–19 digit card numbers (Luhn-checked) → `[EMAIL]`, `[PHONE]`,
  `[CARD]`. Replaces the message **by ID** (`add_messages` replaces when IDs match — c2 demo).
- Blocks on prompt-injection patterns ("ignore previous instructions", "system prompt",
  "you are now") or length > 4000 chars.
- Returns `Command(update={...guardrail_flags, messages}, goto="load_memory" | "blocked_reply")`.

### 10.2 `load_memory` (c11, c21, c25)
- Namespace from context: `("users", ctx.user_id, "profile")` key `"profile"` → `profile`.
- Semantic: `runtime.store.search(("users", ctx.user_id, "facts"), query=<last user text>, limit=3)`
  → `recalled_facts`.
- Plain dict return.

### 10.3 `manage_context` (c2, c20)
- If `len(messages) > ctx.summarize_after_messages`: call `gateway.summarize(summary, old)`,
  write new `summary`, and return `RemoveMessage(id=m.id)` for everything except the last 4
  messages. Never split an `AIMessage` with `tool_calls` from its `ToolMessage`s — adjust the cut
  point.
- Separately, a helper `llm_view(state, ctx)` (used by every LLM call site, not a node) applies
  `trim_messages(strategy="last", max_tokens=ctx.max_context_tokens,
  token_counter=count_tokens_approximately, start_on="human", include_system=True)` and prepends
  a `SystemMessage` containing `summary` + `recalled_facts`. **State is not modified by
  trimming**; only the model's view is. `CONCEPTS.md` must explain trimming vs deleting.

### 10.4 `supervisor` (c4, c12, c15, c16, c27)
- If `state["remaining_steps"] < 6` → `Command(goto="fallback", update={"audit": ["step budget"]})`.
- If `hops >= 4` → `goto="compose_reply"` (prevent ping-pong).
- Else `decision = gateway.route(...)` (structured). If `decision.confidence < 0.5` → deterministic
  **rule-based** router picks instead (this is the workflow-vs-agent contrast, c12).
- Returns `Command(update={"route": decision, "active_agent": ..., "hops": 1,
  "query": <last user text>}, goto=decision.next)`.
- Declare destinations for graph rendering:
  `builder.add_node("supervisor", supervisor, destinations=(...))` (verify the kwarg; note in
  API_NOTES).

### 10.5 `kb_agent` subgraph (c3, c8, c9, c13, c23, c24)
Added to the parent **directly as a compiled graph node** (`builder.add_node("kb_agent", kb_graph)`)
— shared keys flow automatically.

- `plan_retrieval` → returns `[Send("retrieve_source", {"query": q, "source": s}) for s in
  ("docs", "forum", "changelog")]` via conditional edge. (c3)
- `retrieve_source`:
  - `retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.05, retry_on=TransientSourceError)`
    (c8). The forum source raises `TransientSourceError` for the first
    `ctx.flaky_forum_failures` attempts per (thread, query) — use a module-level counter keyed
    on that tuple, reset in tests.
  - `cache_policy=CachePolicy(key_func=lambda s: f"{s['source']}::{normalize(s['query'])}",
    ttl=300)` (c23). Compile the **parent** with `cache=InMemoryCache()`.
  - Emits `writer({"event": "retrieve", "source": ..., "hits": n})` (c22).
  - Returns `{"raw_hits": [...]}` (append reducer).
  - Routes forum results through `rerank_forum` (extra hop); docs/changelog go straight to
    `merge_sources`.
- `merge_sources` — `defer=True` (c24). Without `defer`, it would run once the 1-hop branches
  finish and again after the forum branch. With it, it runs **exactly once**. Writes
  `citations` (custom reducer, top 5).
- `generate` — `gateway.generate_answer` → `draft_answer`, tokens stream.
- `grade` — `GradeResult`; route: relevant & grounded → END; else `rewrite_count < 2` → `rewrite`;
  else END with `low_confidence=True`. (c13)
- `rewrite` — `RewrittenQuery`, increments `rewrite_count`, clears nothing (explain in CONCEPTS.md
  why `raw_hits` keeps accumulating and why `citations` dedupes).

### 10.6 `tech_agent` subgraph (c14, c15)
- `tech_llm` → `gateway.tech_step(llm_view(...), TECH_TOOLS)`; returns `{"messages": [ai_msg]}`.
- `tools` = `ToolNode(TECH_TOOLS)`; edge `tech_llm → tools_condition`; `tools → tech_llm`.
- **Handoff (c15)**: `transfer_to_billing` returns
  ```python
  Command(
      goto="billing_agent",
      graph=Command.PARENT,
      update={"messages": [ToolMessage("Transferring to billing", tool_call_id=tool_call_id)],
              "active_agent": "billing_agent", "audit": ["handoff tech→billing"]},
  )
  ```
  The `ToolMessage` is mandatory to keep the tool-call/tool-result pairing valid. Any key updated
  from a subgraph via `Command.PARENT` that also exists in the subgraph must have a reducer in the
  parent (`messages`, `audit` do). Document this gotcha.
- On normal completion (no tool calls) the subgraph ends and the parent edge returns to
  `supervisor`.

### 10.7 `billing_agent` wrapper + subgraph (c17)
```python
class BillingState(TypedDict):          # disjoint from ParentState — no shared keys
    customer_id: str
    complaint: str
    account: dict
    invoices: list[dict]
    proposal: RefundProposal | None

def to_billing(state: ParentState, ctx: SupportContext) -> BillingState: ...
def from_billing(result: BillingState) -> dict: ...   # -> {"refund": ..., "audit": [...]}

def billing_agent(state: ParentState, runtime: Runtime[SupportContext]) -> Command:
    result = billing_graph.invoke(to_billing(state, runtime.context))
    update = from_billing(result)
    goto = "human_review" if not update["refund"].auto_approvable else "execute_refund"
    return Command(update=update, goto=goto)
```
`auto_approvable = amount <= ctx.refund_auto_approve_limit`.

### 10.8 `human_review` (c7, c18)
Two sequential interrupts in one node:
```python
decision = interrupt({"type": "approve_refund", "proposal": refund.model_dump()})
if decision not in ("approve", "reject"): raise ValueError(...)
edited = interrupt({"type": "edit_reply", "draft": default_reply(decision, refund)})
return Command(update={"review": {"decision": decision, "edited_reply": edited or None}},
               goto="execute_refund" if decision == "approve" else "compose_reply")
```
- Resumed with `graph.invoke(Command(resume="approve"), config)` then
  `graph.invoke(Command(resume="<text or empty>"), config)`.
- **The node re-runs from the top on every resume.** Nothing above an `interrupt()` may have
  side effects. Resume values are matched to interrupts **by order**. Both facts go in
  CONCEPTS.md with a test that proves it (count node entries).

### 10.9 `execute_refund`
- Idempotency key = `f"{thread_id}:{invoice_id}"`; writes to a JSON ledger
  `data/refund_ledger.json` only if the key is absent. Calling it twice must not double-refund
  (tested, including via replay in c19).
- Sets `refund_executed=True`, goes to `compose_reply`.

### 10.10 `compose_reply`
Uses `review.edited_reply` if present, else `gateway.compose_reply(llm_view(...), blob)` where
`blob` includes `draft_answer`, citations, tool results, refund outcome, `low_confidence`.
Tokens stream. Writes `final_answer` and appends the `AIMessage`.

### 10.11 `output_guardrail` (c26)
Checks: no unredacted PII; if route was KB, at least one `[doc_id]` citation appears and every
cited id exists in `citations`; any refund amount mentioned equals `refund.amount`; if
`low_confidence`, reply contains an uncertainty phrase.
Fail + `output_retry == 0` → `Command(goto="compose_reply", update={"output_retry": 1, ...})`.
Fail twice → replace `final_answer` with a safe templated message, flag it, continue.

### 10.12 `save_memory` (c11, c21)
- `gateway.extract_memories(last 6 messages)` → `store.put(("users", uid, "facts"), uuid, {"text": f.text,
  "category": f.category})`, skipping facts whose top `store.search` hit has score ≥ 0.9 (dedupe).
- Updates `profile` (`plan_tier`, `last_topic`, `ticket_count+1`) with `store.put` on the exact key.

### 10.13 `fallback` / `blocked_reply` (c27, c26)
Deterministic, no LLM: apologise, give ticket reference = `thread_id`, offer human handoff.

### 10.14 Wiring (`graph.py`)
```python
def build_graph(checkpointer=None, store=None, cache=None) -> CompiledStateGraph: ...
def make_graph():            # for langgraph.json — NO checkpointer/store; the server provides them
    return build_graph(cache=InMemoryCache())
```
Retries on `supervisor`, `generate`, `compose_reply`, `tech_llm` with a `RetryPolicy` that retries
only on transient API errors (rate limit, overloaded, timeout) — never on validation errors.

---

## 11. Memory store (c11, c21)

```python
class HashingEmbeddings(Embeddings):
    """Deterministic feature-hashing bag-of-words (dims=256), L2-normalised.
    Shares tokens → similar vectors, so semantic search is testable offline."""

def build_store(backend: Literal["memory", "sqlite"] = "memory"):
    index = {"embed": HashingEmbeddings(), "dims": 256, "fields": ["text"]}
    ...
```
- `memory`: `InMemoryStore(index=index)` — tests and default CLI.
- `sqlite`: use `langgraph.store.sqlite.SqliteStore` if the installed version provides it **and**
  supports the vector index; otherwise keep `memory` and write the limitation in API_NOTES.
- Namespaces: `("users", uid, "profile")` exact-key, `("users", uid, "facts")` semantic.
  A second `user_id` must see nothing from the first (test).
- The functional digest (c29) writes to `("digests", date)`.

---

## 12. Persistence and time travel (c5, c6, c19)

`persistence.py`:
```python
def sqlite_checkpointer(path="supportpilot.db") -> SqliteSaver
async def async_sqlite_checkpointer(path) -> AsyncSqliteSaver        # used by async streaming
def memory_checkpointer() -> InMemorySaver

def show_state(graph, thread_id)                       # get_state: values, next, tasks, interrupts
def list_history(graph, thread_id) -> list[dict]       # get_state_history: step, node, checkpoint_id, key diffs
def replay(graph, thread_id, checkpoint_id)            # invoke(None, {thread_id, checkpoint_id})
def fork(graph, thread_id, checkpoint_id, values, as_node=None)
    # update_state({thread_id, checkpoint_id}, values, as_node=...) -> new config; then invoke(None, new_config)
```
Required demonstrations:
- **Crash + resume**: env `SUPPORTPILOT_CRASH_AFTER=<node>` makes that node raise `SimulatedCrash`
  *after* its first successful superstep is checkpointed. Re-running `resume` with the same
  `thread_id` continues from the last checkpoint; completed nodes do not re-run (test with
  entry counters).
- **Replay**: re-executes from a past checkpoint; nodes after it run again; `execute_refund` does
  not double-refund.
- **Fork**: from the checkpoint before `billing_agent`, set `refund.amount=5` → auto-approved
  branch, no interrupt. Original branch untouched (both visible in history).
- **SqliteSaver vs InMemorySaver**: a test runs the same thread across two separately
  constructed graphs; with SQLite state survives, with in-memory it does not.

---

## 13. Streaming (c10, c22)

`streaming.py` exposes one renderer per mode, used by the CLI:

| Mode | What the CLI shows |
|---|---|
| `values` | full state after each step (keys only, truncated) |
| `updates` | `node → changed keys`; marks cache hits |
| `debug` | task / checkpoint events |
| `custom` | progress lines from `get_stream_writer()` / `runtime.stream_writer` |
| `messages` | live tokens, filtered to nodes `generate` and `compose_reply` via `metadata["langgraph_node"]` |

- Default chat run: `stream_mode=["updates", "custom", "messages"], subgraphs=True`; handle the
  `(namespace, mode, chunk)` tuple shape; show which subgraph an event came from.
- Async path: `astream(...)` with `AsyncSqliteSaver`, selectable via `--async`.
- Interrupts: detect `__interrupt__` in `updates`, prompt the human, resume with
  `Command(resume=...)`, keep streaming.
- Optional: if `version="v2"` exists (see API_NOTES), add `--v2` flag rendering typed parts.

---

## 14. CLI (`cli.py`, Typer + rich)

```
supportpilot chat      --user U --thread T [--provider fake|anthropic] [--async] [--mode updates,custom,messages]
supportpilot resume    --thread T                     # continue after crash/interrupt
supportpilot state     --thread T                     # c5 get_state
supportpilot history   --thread T                     # c5/c19 table of checkpoints
supportpilot replay    --thread T --checkpoint C      # c19
supportpilot fork      --thread T --checkpoint C --set refund.amount=5 [--as-node billing_agent]
supportpilot memory    --user U [--search "text"]     # c11/c21 inspect store
supportpilot digest    --date YYYY-MM-DD              # c29 functional API
supportpilot export-graph [--xray]                    # c30 writes docs/graph.mmd
supportpilot demo      <c01..c31|all>                 # runs the scripted demo for one concept
```
`demo all` runs every concept demo in sequence and prints a pass/fail table. Each demo is ≤ 40
lines and reuses the same functions the tests use.

---

## 15. Functional API, Studio, evaluation

### 15.1 Daily digest (`functional/daily_digest.py`, c29)
```python
@task
def summarize_ticket(ticket: dict) -> str: ...        # gateway.summarize

@task
def classify_sentiment(summary: str) -> str: ...

@entrypoint(checkpointer=InMemorySaver(), store=...)
def daily_digest(tickets: list[dict], *, previous: dict | None = None):
    futures = [summarize_ticket(t) for t in tickets]              # parallel
    summaries = [f.result() for f in futures]
    sentiments = [classify_sentiment(s).result() for s in summaries]
    approved = interrupt({"type": "approve_digest", "preview": summaries[:3]})
    if not approved:
        return entrypoint.final(value={"sent": False}, save=previous)
    digest = {...}
    return entrypoint.final(value={"sent": True, "digest": digest}, save=digest)
```
Tickets come from `list_history` of stored threads. `CONCEPTS.md` explains when to pick the
Functional API over `StateGraph` (linear/batch logic, no need to visualise, plain Python control
flow) and that `@task` results are checkpointed so a resume doesn't redo them (tested).

### 15.2 Studio + Mermaid (c30)
`langgraph.json`:
```json
{
  "dependencies": ["."],
  "graphs": {
    "supportpilot": "./src/supportpilot/graph.py:make_graph",
    "daily_digest": "./src/supportpilot/functional/daily_digest.py:daily_digest"
  },
  "env": ".env"
}
```
- `langgraph dev` must start and show both graphs. `README.md` documents it.
- `scripts/export_graph.py` writes `graph.get_graph(xray=True).draw_mermaid()` to `docs/graph.mmd`;
  a test asserts every parent node and every subgraph node name appears in the output.

### 15.3 Tests and evaluation harness (c31)

**Unit** (`tests/unit/`): reducers (property-style on fixed samples), guardrail regexes (≥ 15
cases incl. Luhn), TF-IDF ranking, HashingEmbeddings similarity ordering, schema validation,
each tool.

**Concept tests** (`tests/concepts/test_cNN_*.py`): one per concept, each asserting the
*mechanism*, not just the output. Examples: c3 asserts three `retrieve_source` tasks in the
`debug` stream; c8 asserts attempt count = failures + 1; c23 asserts the underlying retriever
call counter does not increase on the second identical query; c24 asserts `merge_sources` ran
once; c27 asserts `fake_behavior="tool_loop"` ends in `fallback` without raising, and that a
tiny `recursion_limit` raises `GraphRecursionError` which the CLI wrapper catches and converts
to the fallback message.

**E2E stories** (`tests/e2e/test_scenarios.py`), all with the fake LLM and `InMemorySaver`:
1. KB question answered with citations, one rewrite on `bad_answer`.
2. Tech question with an error code → tool loop → answer.
3. Tech → "I was charged twice" → handoff → billing → approve → edit → refund once.
4. Small refund ≤ limit → auto-approved, no interrupt.
5. Injection attempt → blocked, no LLM called (spy on gateway).
6. Returning user in a new thread → profile + semantic facts recalled.
7. 20-turn conversation → summary exists, message count bounded, tool pairs intact.
8. Crash after `billing_agent` → resume → completes, no duplicate refund.

**Eval harness** (`evals/`):
- `golden.jsonl`: 30 cases
  `{"id","input","user_id","expected_route","expected_tools":[],"must_cite":bool,
  "must_contain":[],"must_not_contain":[],"expect_interrupt":bool,"expect_blocked":bool}`.
- `metrics.py`: route accuracy, tool-call precision/recall, citation validity rate,
  guardrail block precision, interrupt correctness, mean steps per run.
- `run_eval.py --provider fake|anthropic` → `evals/report.md` with a per-case table and totals.
- `tests/test_eval_thresholds.py` fails the build if (fake provider) route accuracy < 0.95,
  tool recall < 0.95, citation validity < 1.0, any blocked-case leak.
- `pytest -m live` runs the same harness with Anthropic; thresholds are reported, not enforced.
- Coverage target: ≥ 85 % on `src/`.

---

## 16. Traceability matrix (fill in exact function names as you build)

| # | Concept | Primary location | Proving test | Demo |
|---|---|---|---|---|
| 1 | Reducers (`add`, custom) | `state.py`, `reducers.py` | `test_c01_reducers` | `demo c01` |
| 2 | `add_messages` (append, replace-by-id, remove) | `input_guardrail`, `manage_context` | `test_c02_add_messages` | `demo c02` |
| 3 | `Send` fan-out | `kb_agent.plan_retrieval` | `test_c03_send` | `demo c03` |
| 4 | `Command(update, goto)` | `supervisor`, `input_guardrail`, `billing_agent` | `test_c04_command` | `demo c04` |
| 5 | Threads / state APIs | `persistence.py` | `test_c05_persistence` | `state`, `history` |
| 6 | SqliteSaver vs InMemorySaver | `persistence.py` | `test_c06_checkpointers` | `demo c06` |
| 7 | Interrupt + resume | `human_review` | `test_c07_interrupt` | `chat` |
| 8 | `RetryPolicy` | `retrieve_source`, LLM nodes | `test_c08_retry` | `demo c08` |
| 9 | Subgraph (shared schema) | `kb_agent` | `test_c09_subgraph_shared` | `demo c09` |
| 10 | Streaming modes, sync + async | `streaming.py` | `test_c10_streaming` | `chat --mode ...` |
| 11 | Store + namespaces | `memory/store.py`, memory nodes | `test_c11_store` | `memory` |
| 12 | Workflow vs agent | KB pipeline vs supervisor/tech loop, rule fallback | `test_c12_workflow_vs_agent` | `demo c12` |
| 13 | Agentic RAG | `kb_agent` grade/rewrite | `test_c13_agentic_rag` | `demo c13` |
| 14 | Tool loop | `tech_agent` | `test_c14_tool_loop` | `demo c14` |
| 15 | Supervisor + `Command.PARENT` handoff | `supervisor`, `tools/handoff.py` | `test_c15_handoff` | `demo c15` |
| 16 | Structured output | `schemas.py`, gateways | `test_c16_structured` | `demo c16` |
| 17 | Different-schema subgraph + mapping | `billing_agent.py` | `test_c17_subgraph_mapping` | `demo c17` |
| 18 | Sequential interrupts | `human_review` | `test_c18_multi_interrupt` | `chat` |
| 19 | Replay + fork | `persistence.py` | `test_c19_time_travel` | `replay`, `fork` |
| 20 | Trim + rolling summary | `manage_context`, `llm_view` | `test_c20_short_term` | `demo c20` |
| 21 | Semantic memory | `store.search` in memory nodes | `test_c21_semantic_memory` | `memory --search` |
| 22 | Custom + token streaming | node writers, `messages` mode | `test_c22_custom_token_stream` | `chat` |
| 23 | `CachePolicy` | `retrieve_source` | `test_c23_cache` | `demo c23` |
| 24 | `defer=True` | `merge_sources` | `test_c24_deferred` | `demo c24` |
| 25 | Runtime context | `context.py`, all nodes | `test_c25_context` | `demo c25` |
| 26 | Guardrails | `guardrails/`, guard nodes | `test_c26_guardrails` | `demo c26` |
| 27 | Recursion limit + fallback | `supervisor`, `RemainingSteps`, CLI | `test_c27_recursion` | `demo c27` |
| 28 | Swappable LLM | `llm/` | `test_c28_swappable_llm` | `chat --provider` |
| 29 | Functional API | `functional/daily_digest.py` | `test_c29_functional` | `digest` |
| 30 | Studio + Mermaid | `langgraph.json`, `export_graph.py` | `test_c30_mermaid` | `export-graph` |
| 31 | Eval harness | `evals/`, `tests/` | `test_eval_thresholds` | `run_eval.py` |

---

## 17. Build phases (each ends with a gate: all tests green, ruff + mypy clean)

| Phase | Work | Gate |
|---|---|---|
| **P0 Audit** | Run existing tests. Map each of the 13 built concepts to its new home in §6. Move code into `src/supportpilot/`, keep behaviour. Write `docs/API_NOTES.md` by verifying §4.2. | Old tests pass in new layout |
| **P1 Foundation** | `pyproject`, `config`, `context` (c25), `schemas` (c16), `reducers`/`state` (c1, c2), `crm.json`, KB files, TF-IDF, HashingEmbeddings, LLM gateway + FakeGateway + AnthropicGateway (c28) | Unit tests pass |
| **P2 KB agent** | Send, retry, cache, deferred merge, grade/rewrite (c3, c8, c9, c13, c23, c24); run standalone first | c03 c08 c09 c13 c23 c24 |
| **P3 Tech agent** | ToolNode loop, tools (c14) | c14 |
| **P4 Billing + HITL** | Billing subgraph + mappers (c17), two interrupts (c7, c18), idempotent refund | c07 c17 c18 |
| **P5 Parent graph** | guardrails (c26), supervisor + routing + handoff (c4, c12, c15), compose, fallback, `RemainingSteps` (c27) | c04 c12 c15 c26 c27 |
| **P6 Memory** | Store, namespaces, semantic search, save/load (c11, c21), trim + summary (c20) | c11 c20 c21 |
| **P7 Persistence** | Checkpointer factories, crash/resume, history, replay, fork (c5, c6, c19) | c05 c06 c19 |
| **P8 Streaming + CLI** | All modes sync/async, custom + tokens, interrupt handling in stream (c10, c22), Typer CLI, `demo` | c10 c22, `demo all` passes |
| **P9 Functional API** | Daily digest (c29) | c29 |
| **P10 Studio + Mermaid** | `langgraph.json`, `make_graph`, export script (c30); run `langgraph dev` manually | c30 |
| **P11 Evaluation** | golden set, metrics, report, thresholds (c31); E2E stories | full suite, coverage ≥ 85 % |
| **P12 Docs** | README (setup, run, architecture diagram from `graph.mmd`), CONCEPTS.md (31 sections) | review against §18 |

Always build and test a subgraph in isolation before adding it to the parent.

---

## 18. Definition of done

- [ ] `pip install -e ".[dev]"` then `pytest` passes offline with no API key.
- [ ] `supportpilot demo all` shows 31/31 passing.
- [ ] `supportpilot chat` streams progress events and tokens live; refunds pause for approval
      and then for reply editing.
- [ ] Killing the process mid-run and running `resume` completes the ticket with no repeated
      side effects.
- [ ] `history`, `replay`, `fork` work on a real SQLite thread; forked and original branches both
      appear in history.
- [ ] A new thread for an existing user recalls profile and relevant facts; a different user
      recalls nothing.
- [ ] `SUPPORTPILOT_LLM=anthropic` with a key runs the same flows; `pytest -m live` runs the eval.
- [ ] `langgraph dev` loads both graphs; `docs/graph.mmd` shows all nodes including subgraph
      internals.
- [ ] `evals/report.md` generated; thresholds met.
- [ ] `docs/CONCEPTS.md` has 31 sections, each: *what it is · where in this repo (file:function) ·
      why it's needed here · one gotcha · the test that proves it*.
- [ ] `docs/API_NOTES.md` lists every verified import and every deviation from this spec.

---

## 19. Gotchas the implementation must handle (and CONCEPTS.md must explain)

1. A node with `interrupt()` **re-executes from the start** on resume; code before it must be
   side-effect-free. Multiple interrupts are matched to resume values **by order**.
2. `Command.PARENT` updates to keys shared with the subgraph need a **reducer in the parent**.
3. A handoff tool must return a `ToolMessage` for its `tool_call_id`, or the next LLM call fails
   on an unmatched tool call.
4. `RemoveMessage` needs message IDs; `add_messages` assigns them. Never remove an `AIMessage`
   with `tool_calls` while keeping its `ToolMessage`s, or vice versa.
5. `trim_messages` changes what the model sees; `RemoveMessage` changes what is stored.
6. Without a reducer, two parallel `Send` branches writing the same key raise
   `InvalidUpdateError` — c01 test must demonstrate this failure, then the fix.
7. Retry only on transient errors. Retrying a Pydantic `ValidationError` just burns calls.
8. Cache keys must be built from **normalised** input or the cache never hits.
9. Without `defer=True`, a fan-in node after uneven branches runs more than once.
10. Never pass a checkpointer to the graph served by `langgraph dev`; the server supplies one.
11. Context (`runtime.context`) is read-only per run and not checkpointed; anything that must
    survive a resume belongs in state.
12. Replaying past a side-effecting node re-runs it — side effects must be idempotent.
13. `GraphRecursionError` is a last line of defence; `RemainingSteps` lets the graph exit
    gracefully *before* hitting it.

---

## 20. Interview self-check (for Pranav, after the build)

You understand this project when you can answer, without looking at the code:

1. Why does `raw_hits` use `add` while `citations` uses a custom reducer, and `route` uses none?
2. Why does `supervisor` return a `Command` while `load_memory` returns a dict?
3. Why is `kb_agent` added as a graph node but `billing_agent` called from inside a function?
4. What exactly happens, step by step, when you resume the second interrupt in `human_review`?
5. How does the tech agent's handoff reach a node that doesn't exist in its own graph?
6. Where does `user_id` live — state, config, or context — and why there?
7. Why does `merge_sources` need `defer=True`, and what breaks without it?
8. What is the difference between replaying and forking, and why doesn't replay double-refund?
9. What does the cache key contain, and what bug appears if you drop the normaliser?
10. When would you choose the Functional API over `StateGraph` in a real project?
11. How would you swap `SqliteSaver` for `PostgresSaver`, and what else would change?
12. Which parts of this system are a *workflow* and which are an *agent*, and why is that split
    deliberate?


after you complete writing the code push the code into this one :- https://github.com/pranavks343/HelmDesk.git
