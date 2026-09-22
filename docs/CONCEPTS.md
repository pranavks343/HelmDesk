# CONCEPTS.md

One section per concept: **what** it is · **where** in this repo (file:function) · **why** it's
needed here · **one gotcha** · **the test that proves it**. See `docs/API_NOTES.md` for the deeper
version-specific dives referenced below.

---

### 1. Reducers (`add` + custom)

**What**: a function `(left, right) -> merged` attached to a state key via `Annotated[T, fn]`, run
by LangGraph instead of last-write-wins whenever two updates to that key land in the same or
different supersteps.
**Where**: `state.py` (`hops`, `raw_hits` → `operator.add`; `citations` → `merge_citations`;
`guardrail_flags`/`audit` → `append_unique`), `reducers.py` (the two custom ones).
**Why**: `raw_hits` must accumulate across three parallel `Send` branches; `citations` must dedupe
by `doc_id` keeping the best score; a loop counter (`hops`) needs simple addition.
**Gotcha**: without a reducer, two parallel branches writing the *same* key in one superstep raise
`InvalidUpdateError` - demonstrated deliberately in the test below before showing the fix.
**Test**: `tests/concepts/test_c01_reducers.py`.

### 2. `add_messages` (append, replace-by-id, remove)

**What**: the built-in reducer for `messages`: appends by default, *replaces* an existing message
when the incoming one shares its `id`, and deletes when given a `RemoveMessage(id=...)`.
**Where**: `nodes/guard_nodes.py:input_guardrail` (replaces the human message by id after PII
redaction), `nodes/context_nodes.py:manage_context` (emits `RemoveMessage` for trimmed history).
**Why**: redaction must edit the stored message in place, not leave the raw PII *and* a redacted
copy both in history; trimming must actually shrink what's persisted, not just what's shown to
the model.
**Gotcha**: `RemoveMessage` needs the message's real `id` (assigned by `add_messages` on first
append) - removing "by content" doesn't work.
**Test**: `tests/concepts/test_c02_add_messages.py`.

### 3. `Send`

**What**: returned from a conditional-edge function to dynamically fan a single node out into N
parallel tasks, each with its own input payload.
**Where**: `subgraphs/kb_agent.py:fanout_sources`, fanning `retrieve_source` out over
`("docs", "forum", "changelog")`.
**Why**: the three KB sources are independent and should be searched concurrently, not one after
another.
**Gotcha**: the fanned-out node's *input* is whatever dict `Send(node, payload)` carries - not the
graph's full state - so `retrieve_source(payload, runtime)` only ever sees `{"query", "source"}`.
**Test**: `tests/concepts/test_c03_send.py` (asserts 3 distinct tasks via the `debug` stream, not
just the final merged output).

### 4. `Command(update, goto)`

**What**: a node return value that updates state *and* picks the next node in one step, replacing
a separate conditional edge.
**Where**: `nodes/supervisor.py:supervisor`, `nodes/guard_nodes.py:input_guardrail`,
`nodes/human_review.py:human_review`.
**Why**: the supervisor's routing decision and the state update that records it (`route`,
`active_agent`, `hops`, `query`) are one atomic decision - splitting them into "update node" +
"separate router function" would just be more code for the same effect.
**Gotcha**: a `Command`'s `goto` is *not* replayable by `update_state(as_node=...)` (see concept 19
and `docs/API_NOTES.md`) - a node whose routing needs to be forkable should use a conditional edge
instead (see `billing_agent`, concept 17).
**Test**: `tests/concepts/test_c04_command.py`.

### 5. Persistence (threads, `get_state`, `get_state_history`, `update_state`)

**What**: every graph run against a `thread_id` is checkpointed; `get_state`/`get_state_history`
read that timeline back, `update_state` writes into it.
**Where**: `persistence.py`.
**Why**: `supportpilot state`/`history` CLI commands, and the whole replay/fork story (concept 19),
depend on this.
**Gotcha**: `update_state`/`invoke(None, cfg)` need `checkpoint_ns` explicitly present in the
config's `configurable` dict in this langgraph version, or `SqliteSaver.put_writes` raises
`KeyError` - see `persistence.py:_cfg`.
**Test**: `tests/concepts/test_c05_persistence.py`.

### 6. Checkpointers (`SqliteSaver` vs `InMemorySaver`)

**What**: pluggable backends for the same checkpoint protocol.
**Where**: `persistence.py:sqlite_checkpointer`, `memory_checkpointer`.
**Why**: SQLite for `supportpilot chat` (survives process restarts, enables crash+resume); memory
for tests (fast, isolated).
**Gotcha**: a *new* `InMemorySaver()` instance shares nothing with a previous one, even for the
same `thread_id` - it's process-local state, not a real store.
**Test**: `tests/concepts/test_c06_checkpointers.py` (same thread, two separately constructed
graphs: survives with SQLite, doesn't with a fresh in-memory saver).

### 7. Interrupt + resume

**What**: `interrupt(payload)` pauses the graph mid-node and surfaces `payload` to the caller;
`graph.invoke(Command(resume=value), cfg)` continues from exactly that point.
**Where**: `nodes/human_review.py:human_review` (refund approval).
**Why**: a refund must never execute without a human in the loop.
**Gotcha**: the node *re-runs from the top* on resume - anything before the `interrupt()` call
must be side-effect-free (see concept 18).
**Test**: `tests/concepts/test_c07_interrupt.py`.

### 8. `RetryPolicy`

**What**: `add_node(..., retry_policy=RetryPolicy(max_attempts=N, retry_on=ExcType))` retries a
node automatically on a matching exception.
**Where**: `subgraphs/kb_agent.py:retrieve_source` (retries `TransientSourceError`),
`nodes/supervisor.py`/`nodes/compose.py` (retry `TransientLLMError`).
**Why**: the forum API is flaky (simulated); real LLM APIs have transient failures.
**Gotcha**: retry only on *transient* errors - retrying a `pydantic.ValidationError` just burns
calls for a guaranteed-repeat failure. `retry_on=` is set to specific exception types, never a
bare `Exception`.
**Test**: `tests/concepts/test_c08_retry.py` (asserts *attempt count* = failures + 1, not just the
final success).

### 9. Subgraphs (shared schema)

**What**: a compiled `StateGraph` embedded directly as a parent node
(`add_node("kb_agent", compiled_graph)`); shared key names flow through automatically.
**Where**: `subgraphs/kb_agent.py` (`KBState`, a subset of `ParentState` with identical key names
and reducers).
**Why**: the KB pipeline is reusable and independently testable, but shouldn't need any explicit
mapping when embedded, since it only touches keys the parent already has.
**Gotcha**: "shared schema" only works because the key *names and reducer types* match exactly -
any mismatch silently drops or misinterprets data. Contrast with concept 17 (`billing_agent`),
which deliberately uses a disjoint schema instead.
**Test**: `tests/concepts/test_c09_subgraph_shared.py`.

### 10. Streaming (all modes, sync + async)

**What**: `stream_mode` in `{"values", "updates", "debug", "custom", "messages"}`, singly or as a
list (which yields `(namespace, mode, chunk)` tuples with `subgraphs=True`).
**Where**: `streaming.py`, used by `cli.py:chat`.
**Why**: the terminal shows live progress, not a frozen screen during a multi-second run.
**Gotcha**: a *single* (non-list) `stream_mode` with `subgraphs=True` yields `(namespace, chunk)`
pairs, not `(namespace, mode, chunk)` triples - the shape depends on whether `stream_mode` was a
list, independent of `subgraphs`.
**Test**: `tests/concepts/test_c10_streaming.py` (both the sync and the async path).

### 11. Long-term memory (`Store`, namespaces)

**What**: a key-value(+vector) store outside the checkpointed thread, namespaced by tuple.
**Where**: `memory/store.py` (`("users", uid, "profile")`, `("users", uid, "facts")`),
`nodes/memory_nodes.py`.
**Why**: plan tier and prior issues should be known on a customer's *next* ticket, in a brand-new
thread.
**Gotcha**: namespaces are exact-match on their tuple - a typo'd or missing `user_id` silently
returns nothing rather than erroring.
**Test**: `tests/concepts/test_c11_store.py`.

### 12. Workflow vs agent routing

**What**: some control flow is a fixed pipeline (a "workflow" - same steps, same order, every
time); some needs judgement (an "agent" - an LLM decides what happens next).
**Where**: the KB subgraph (`subgraphs/kb_agent.py`) is a workflow - `plan → fanout → merge →
generate → grade` always in that order. The supervisor (`nodes/supervisor.py`) is agentic - an LLM
call decides the next node, with a deterministic rule-based router as a low-confidence fallback.
**Why**: this contrast is the whole point of concept 12 - not every part of a "multi-agent system"
benefits from being agentic; RAG retrieval order is not a judgement call.
**Gotcha**: conflating the two leads either to over-engineering a fixed pipeline with an LLM
decision it doesn't need, or under-specifying a genuinely ambiguous routing decision as a rigid
if/elif chain.
**Test**: `tests/concepts/test_c12_workflow_vs_agent.py`.

### 13. Agentic RAG

**What**: retrieval that grades its own answer and rewrites the query to try again, rather than
returning whatever the first retrieval found.
**Where**: `subgraphs/kb_agent.py:grade`/`rewrite`, looping back to `plan_retrieval` up to
`REWRITE_LIMIT` (2) times.
**Why**: a single-shot RAG answer that's ungrounded should self-correct instead of confidently
citing the wrong doc.
**Gotcha**: `raw_hits` keeps accumulating across rewrites (an `add` reducer - useful debugging
history of every hit ever seen); `citations` (the *current* top-5, via `merge_citations`) is what
actually feeds the answer - conflating the two would leak stale, lower-scored hits into the reply.
**Test**: `tests/concepts/test_c13_agentic_rag.py`.

### 14. Tool loop

**What**: `tools_condition` routes a model's tool calls into `ToolNode(tools)` and back, until a
response with no tool calls ends the loop.
**Where**: `subgraphs/tech_agent.py`.
**Why**: the tech agent needs to actually call `lookup_order`/`check_service_status`/
`get_error_code_doc`, not just describe what it would do.
**Gotcha**: an unbounded tool loop (a model that never stops calling tools) doesn't raise on its
own - see concept 27 for why `RemainingSteps` has to be checked *inside* `tech_llm`.
**Test**: `tests/concepts/test_c14_tool_loop.py`.

### 15. Supervisor + `Command.PARENT` handoff

**What**: a tool deep inside a subgraph's `ToolNode` can return
`Command(graph=Command.PARENT, goto="other_node")`, reaching a node that doesn't exist in its own
subgraph's graph.
**Where**: `tools/handoff.py:transfer_to_billing`, invoked from within `tech_agent`.
**Why**: a "my order is fine, actually I was double-charged" mid-conversation pivot should reach
billing directly, not force the customer to repeat themselves in a new turn.
**Gotcha** (the big one - see `docs/API_NOTES.md` for the full story): embedding the tech subgraph
directly as a node (`add_node("tech_agent", compiled_graph)`) *alongside* a static outgoing edge
does **not** correctly suppress that edge when the inner `Command.PARENT` fires - both the handoff
*and* the static edge end up executing, double-running everything downstream. Fixed by making
`tech_agent` a plain wrapper node (`nodes/tech_wrapper.py`) with no static outgoing edge of its
own, so the inner `ParentCommand` exception has nothing to race against.
**Test**: `tests/concepts/test_c15_handoff.py`.

### 16. Structured output

**What**: LLM calls that return a validated Pydantic instance, not free text to parse.
**Where**: `schemas.py` (all the models), every `LLMGateway` method that returns one.
**Why**: routing/grading/refund decisions are consumed by *code*, not read by a human - they must
be machine-reliable.
**Gotcha**: `FakeGateway` still constructs and validates real `RouteDecision`/`GradeResult`/etc.
instances (not raw dicts) even though it's rule-based - the validation guarantee holds regardless
of which gateway is behind it.
**Test**: `tests/concepts/test_c16_structured.py`.

### 17. Different-schema subgraph + explicit mapping

**What**: a subgraph compiled against a schema with **no keys in common** with the parent; a
wrapper node maps between them explicitly.
**Where**: `subgraphs/billing_agent.py` (`BillingState`), `nodes/billing_wrapper.py`
(`to_billing`/`from_billing`).
**Why**: billing logic (account, invoices, proposal) is a self-contained concern that shouldn't
leak its own working fields into `ParentState`.
**Gotcha**: because `billing_agent` is a *plain node* (not `Command`-returning) with routing done
via a separate conditional edge (`route_after_billing`), forking a checkpoint and changing
`refund.amount` *does* correctly flip the auto-approve decision on replay - see concept 19 and the
`update_state(as_node=...)` gotcha in `docs/API_NOTES.md`.
**Test**: `tests/concepts/test_c17_subgraph_mapping.py`.

### 18. Multiple sequential interrupts

**What**: two `interrupt()` calls in one node body, resolved one at a time across separate
`invoke(Command(resume=...))` calls.
**Where**: `nodes/human_review.py:human_review` (approve/reject, then edited reply text).
**Why**: two genuinely different human decisions (approve vs. what to actually say back) shouldn't
be crammed into one payload.
**Gotcha**: the node **re-runs from the top on every resume** - confirmed by counting real
function entries (3 for 1 initial call + 2 resumes). Resume values are matched to `interrupt()`
calls *by call order*, not by any explicit id.
**Test**: `tests/concepts/test_c18_multi_interrupt.py`.

### 19. Time travel (replay, fork)

**What**: **replay** re-executes a thread from a past checkpoint (`invoke(None, {thread_id,
checkpoint_id})`); **fork** writes new values into a past checkpoint via `update_state(...,
as_node=...)` and continues from there, leaving the original branch untouched in history.
**Where**: `persistence.py:replay`/`fork`.
**Why**: "why did it refund?" needs to be answerable by literally re-running the decision, and "what
if the amount had been smaller?" needs to be answerable without destroying the real run.
**Gotcha**: replaying past `execute_refund` re-runs it - it's only safe because it's idempotent
(keyed on `thread_id:invoice_id`, see concept 8's sibling note on `execute_refund`). Also: fork
only actually changes downstream *routing* when the target node used a conditional edge, not a
`Command` (see concept 17's gotcha and `docs/API_NOTES.md`).
**Test**: `tests/concepts/test_c19_time_travel.py`.

### 20. Trim + rolling summary

**What**: two distinct mechanisms often confused: **trimming** (`trim_messages`, changes what the
*model sees* for one call) vs. **deleting** (`RemoveMessage`, changes what's *stored*).
**Where**: `memory/short_term.py:llm_view` (trim, used at every LLM call site),
`nodes/context_nodes.py:manage_context` (delete + fold into `summary`, run once per turn as a
node).
**Why**: every LLM call needs a bounded context window (`llm_view`); the *stored* thread should
also not grow forever, but only needs pruning occasionally, not per-call.
**Gotcha**: the deletion boundary must never split an `AIMessage(tool_calls=...)` from its
`ToolMessage`s - `keep_tail_boundary` walks the cut point back past any `ToolMessage` it would
otherwise land on.
**Test**: `tests/concepts/test_c20_short_term.py`.

### 21. Semantic memory (`store.search`)

**What**: vector similarity search over the fact `Store`, using `HashingEmbeddings` (deterministic
feature-hashing, no embedding API needed).
**Where**: `retrieval/embeddings.py`, `nodes/memory_nodes.py:load_memory` (recall),
`save_memory` (dedupe near-identical facts before writing new ones).
**Why**: "prefers email" said three tickets ago should surface for "how should I contact you"
today, without an exact-string match.
**Gotcha**: search is strictly namespace-scoped - a second, unrelated `user_id` searching the same
text gets zero hits, proven directly (not just asserted).
**Test**: `tests/concepts/test_c21_semantic_memory.py`.

### 22. Custom + token streaming

**What**: `get_stream_writer()` for arbitrary progress events (`custom` mode);
`GenericFakeChatModel` for real token-by-token chunks with no network (`messages` mode).
**Where**: writer calls throughout `subgraphs/kb_agent.py` and `nodes/guard_nodes.py`;
`llm/fake.py:_fake_stream`.
**Why**: the terminal should show "retrieving from forum..." *and* the answer typing out live, not
just a spinner.
**Gotcha**: `messages`-mode chunks are `(AIMessageChunk, metadata)` pairs - filtering to just the
customer-facing nodes (`generate`, `compose_reply`) requires checking
`metadata["langgraph_node"]`, or you'd also stream the supervisor's internal routing "thoughts".
**Test**: `tests/concepts/test_c22_custom_token_stream.py`.

### 23. `CachePolicy`

**What**: `add_node(..., cache_policy=CachePolicy(key_func=..., ttl=...))` skips re-running a node
entirely if an identical cache key was already computed.
**Where**: `subgraphs/kb_agent.py:retrieve_source`, keyed on `f"{source}::{normalize(query)}"`.
**Why**: "how do I reset my password" asked 50 times a day shouldn't re-run TF-IDF search 50
times.
**Gotcha**: the cache key **must** use the same normaliser as everything else (`normalize()`) - a
literal-string key would make `"SSO setup"` and `"sso setup"` miss each other, silently defeating
the cache for real users who just capitalize differently. Also: `key_func` is probed with
placeholder input during graph *rendering* (not just real runs) - it must not raise on a missing
key (see `docs/API_NOTES.md`).
**Test**: `tests/concepts/test_c23_cache.py` (proves a hit via an instrumented call counter, not
just "the answer looks the same").

### 24. `defer=True`

**What**: `add_node(..., defer=True)` makes a fan-in node wait for *every* incoming branch to
finish before running, even when the branches take different numbers of hops.
**Where**: `subgraphs/kb_agent.py:merge_sources` (waits for docs/changelog's 1 hop *and*
forum's extra `rerank_forum` hop).
**Why**: without it, `merge_sources` would run once when docs/changelog finish, then again when
forum finishes - double work, and `citations` would briefly be incomplete.
**Gotcha**: `defer=True` is invisible in the node's own code - it's purely a scheduling directive
on `add_node`, easy to forget when adding a new uneven branch later.
**Test**: `tests/concepts/test_c24_deferred.py` (asserts an exact call count of 1, via
instrumentation, not inference from output).

### 25. Runtime context (`context_schema` / `Runtime`)

**What**: per-request configuration (`user_id`, model choice, limits) passed via
`invoke(..., context=SupportContext(...))` and read via `runtime.context` inside nodes - distinct
from both state (checkpointed) and `config["configurable"]` (plumbing).
**Where**: `context.py`, every node that takes a `runtime: Runtime[SupportContext]` parameter.
**Why**: `refund_auto_approve_limit` is a policy knob for *this run*, not a fact about the
conversation that should be saved and replayed.
**Gotcha**: context is **never written into state** - proven directly by asserting none of its
field names appear as state keys after a run, not just "trust me".
**Test**: `tests/concepts/test_c25_context.py`.

### 26. Guardrails node

**What**: dedicated input/output screening nodes, not inline checks scattered through business
logic.
**Where**: `guardrails/input.py` + `nodes/guard_nodes.py:input_guardrail` (PII redaction,
prompt-injection block, length cap); `guardrails/output.py` + `output_guardrail` (grounding, PII
leak, refund-amount consistency, uncertainty phrasing when `low_confidence`).
**Why**: security/compliance checks that live in one place are auditable; scattered throughout
node logic they're easy to miss adding to a new node.
**Gotcha**: a blocked input must never reach the LLM gateway at all - proven by making
`get_gateway` raise if called during a blocked turn, not just checking the final output looks
safe.
**Test**: `tests/concepts/test_c26_guardrails.py`.

### 27. Recursion limit + fallback

**What**: `RemainingSteps` (a managed value, auto-decremented from state) lets a node degrade
*before* hitting the hard `recursion_limit`; `GraphRecursionError` is the last line of defence when
nothing degrades in time.
**Where**: `subgraphs/tech_agent.py:tech_llm` (stops calling tools and returns a final message
below `DEGRADE_BELOW_STEPS`); `nodes/supervisor.py:supervisor` (checks
`state["remaining_steps"]` too); `cli.py:chat` (catches `GraphRecursionError` around each turn).
**Why**: a model stuck calling the same tool forever (or a genuine bug) shouldn't burn the
project's real ~10,000-step default recursion limit before surfacing - see `docs/API_NOTES.md`.
**Gotcha**: `RemainingSteps` is **not** automatically enforced per-subgraph or per-agent - it has
to be explicitly read and acted on inside whichever node is doing the looping; discovered the hard
way when `fake_behavior="tool_loop"` first hung for real before this fix.
**Test**: `tests/concepts/test_c27_recursion.py`.

### 28. Swappable LLM (fake vs. `ChatAnthropic`)

**What**: `LLMGateway` is a `Protocol`; `factory.get_gateway(ctx)` picks `FakeGateway` (default,
offline, deterministic) or `AnthropicGateway` (opt-in, `SUPPORTPILOT_LLM=anthropic`) - no other
code knows which one is running.
**Where**: `llm/gateway.py`, `llm/fake.py`, `llm/anthropic.py`, `llm/factory.py`.
**Why**: the entire test suite, `demo all`, and the eval harness must run with zero API key and
zero network calls, while production usage swaps in a real model with one env var.
**Gotcha**: live-Anthropic tests are marked `@pytest.mark.live` and are excluded by default
(`addopts = "-m 'not live'"` in `pyproject.toml`) - they're skipped, not silently passing, when no
key is set.
**Test**: `tests/concepts/test_c28_swappable_llm.py`.

### 29. Functional API

**What**: `@entrypoint`/`@task` for plain-Python-control-flow batch jobs, as an alternative to
`StateGraph` when there's no branching logic worth visualising.
**Where**: `functional/daily_digest.py`.
**Why**: a nightly digest (summarize N tickets in parallel, classify sentiment, pause once for
approval, save) is a linear pipeline - modeling it as a graph with nodes/edges would be pure
ceremony over the same three lines of Python.
**Gotcha**: `@task` results *are* individually checkpointed - resuming after the `interrupt()`
does not re-run `summarize_ticket` for tickets already summarized, proven by an instrumented call
counter across an initial call + a resume.
**Test**: `tests/concepts/test_c29_functional.py`.

### 30. Studio / dev server + Mermaid export

**What**: `langgraph dev` loads graphs declared in `langgraph.json`; `get_graph(xray=True
).draw_mermaid()` renders the graph (including subgraph internals) to `docs/graph.mmd`.
**Where**: `langgraph.json`, `scripts/export_graph.py`, `graph.py:make_graph` (no
checkpointer/store - the dev server supplies its own).
**Why**: visual debugging and this very documentation's architecture diagram both come from the
same source of truth as the actual compiled graph, not a hand-drawn diagram that can drift.
**Gotcha**: `get_graph()` only traverses edges *reachable* from `START` - any `Command`-returning
node needs an explicit `destinations=(...)` hint on `add_node`, or everything downstream of it
silently vanishes from the render (this bit us on `input_guardrail` - see `docs/API_NOTES.md`).
**Test**: `tests/concepts/test_c30_mermaid.py`.

### 31. Evaluation harness

**What**: a golden set of labelled cases scored on route accuracy, tool precision/recall, citation
validity, guardrail precision, and interrupt correctness; thresholds enforced in CI via a normal
pytest test.
**Where**: `evals/golden.jsonl` (30 cases), `evals/metrics.py`, `evals/run_eval.py` (writes
`evals/report.md`), `tests/test_eval_thresholds.py`.
**Why**: "does the router still work" needs a number that goes down when someone breaks it, not a
vibe check re-read by hand after every change.
**Gotcha**: a case's expected route has to match what the *actual* deterministic fake router does
for that exact wording, not what seems intuitively "correct" - several golden cases needed
rewording (or their expectation corrected) after real routing priority decisions were made (e.g.
"how are billing cycles calculated" genuinely routes to `billing_agent`, not `kb_agent`, because it
contains a billing keyword - that's the router working as designed, not a bug to route around).
**Test**: `tests/test_eval_thresholds.py` (fails the build below threshold);
`tests/concepts/test_c31_eval_harness.py` (mechanism-level).
