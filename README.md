# SupportPilot v2

A multi-agent customer-support desk for a fictional SaaS company, **Nimbus Cloud**, built with
[LangGraph](https://github.com/langchain-ai/langgraph) to exercise 31 distinct LangGraph/LangChain
concepts in one coherent, realistic system rather than 31 toy snippets. See
[`agents.md`](agents.md) for the full build spec and [`docs/CONCEPTS.md`](docs/CONCEPTS.md) for a
one-page-per-concept explainer (what/where/why/gotcha/test).

## What it does

A customer types a message in a CLI chat. The system screens it (PII redaction, prompt-injection
block), recalls who they are from long-term memory, keeps the thread short with trimming + a
rolling summary, and routes it via an LLM supervisor to one of three specialists:

- **KB agent** - agentic RAG over docs/forum/changelog with parallel retrieval, caching, retries,
  a deferred merge, and a grade → rewrite loop.
- **Tech agent** - a tool-calling ReAct loop (service status, order lookup, error codes) that can
  hand off to billing mid-conversation.
- **Billing agent** - a subgraph with its own private schema that proposes refunds, which pause
  for human approval (and then for reply editing) before anything executes.

Every step is persisted to SQLite, so a thread can be resumed after a simulated crash, inspected,
replayed from any point, or forked into a counterfactual branch. Progress and LLM tokens stream
live to the terminal.

Everything runs **offline by default** against a deterministic fake LLM - `pytest` needs no API
key. The real `ChatAnthropic` path is opt-in via `SUPPORTPILOT_LLM=anthropic`.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # SUPPORTPILOT_LLM=fake by default
```

## Run it

```bash
supportpilot chat --user u_alice --thread t1
supportpilot chat --user u_alice --thread t1 --provider anthropic   # needs ANTHROPIC_API_KEY
supportpilot state --thread t1
supportpilot history --thread t1
supportpilot replay --thread t1 --checkpoint <checkpoint_id>
supportpilot fork --thread t1 --checkpoint <checkpoint_id> --set refund.amount=5
supportpilot memory --user u_alice --search "contact preference"
supportpilot digest --date 2026-09-22
supportpilot export-graph
supportpilot demo all
```

`data/crm.json` ships three sample customers - `u_alice` (Pro, a $49 duplicate charge on file),
`u_bob` (Free, a $15 duplicate charge - auto-approved), `u_carol` (Enterprise, INR). Try:

```bash
supportpilot chat --user u_alice --thread t1
you> I was charged twice, please refund me
```

## Test

```bash
pytest                       # offline, no API key, ~150 tests
pytest -m live                # also exercises the real Anthropic path (needs ANTHROPIC_API_KEY)
python evals/run_eval.py      # writes evals/report.md
supportpilot demo all         # scripted demo for every one of the 31 concepts
```

## Studio

```bash
langgraph dev
```

Loads both graphs declared in `langgraph.json`: `supportpilot` (the main chat graph) and
`daily_digest` (the Functional-API batch job). `docs/graph.mmd` (regenerate with
`supportpilot export-graph`) is the Mermaid export, including subgraph internals.

## Architecture

```
START → input_guardrail ──(blocked)──► blocked_reply ──► END
  │ (ok)
  ▼
load_memory → manage_context → supervisor ──┬──► kb_agent        (agentic RAG subgraph)
                                    ▲        ├──► tech_agent      (ReAct tool loop, can hand off)
                                    │        ├──► billing_agent   (own schema, → human_review)
                                    │        ├──► fallback
                                    └────────┴──► compose_reply ──► output_guardrail ──► save_memory ──► END
```

Full diagram: [`docs/graph.mmd`](docs/graph.mmd) (render at https://mermaid.live or in any
Markdown viewer with Mermaid support).

## Repository layout

See `agents.md` §6 for the intended layout; `src/supportpilot/` mirrors it. Notable non-obvious
files:

- `src/supportpilot/serde.py` - a shared, explicitly-allowlisted serializer for every
  checkpointer/cache in the project (see `docs/API_NOTES.md` for why).
- `src/supportpilot/crash.py` - the `SUPPORTPILOT_CRASH_AFTER=<node>` crash-injection hook used to
  demo resume-after-crash.
- `src/supportpilot/demos.py` - the 31 scripted concept demos behind `supportpilot demo`.
- `src/supportpilot/nodes/tech_wrapper.py` - why `tech_agent` is a plain wrapper function rather
  than a raw compiled-subgraph node (a real LangGraph gotcha, see `docs/API_NOTES.md`).

## Non-goals

No web framework, no frontend, no Docker, no Postgres, no auth, no deployment. The only server is
`langgraph dev` (Studio).
