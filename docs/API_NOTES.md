# API notes

Verified against the installed versions (see `pip list` in the project venv):

```
langgraph                    1.2.11
langgraph-checkpoint         4.2.0
langgraph-checkpoint-sqlite  3.1.1
langgraph-prebuilt            1.1.0
langgraph-sdk                0.4.4
langchain-core                1.6.3
langchain-anthropic           1.7.2
pydantic                      2.13.5
python 3.14.3
```

## Confirmed imports (all of §4.2 exists as specified, nothing renamed/moved)

Every import listed in agents.md §4.2 exists at the given path in this install and was exercised
directly: `StateGraph, START, END`, `add_messages, REMOVE_ALL_MESSAGES`, `Send, Command,
interrupt, RetryPolicy, CachePolicy`, `InMemoryCache`, `InMemorySaver`, `SqliteSaver`,
`AsyncSqliteSaver`, `InMemoryStore`, `ToolNode, tools_condition`, `Runtime`, `get_stream_writer`,
`RemainingSteps`, `GraphRecursionError`, `entrypoint, task`, the `langchain_core.messages` set,
`count_tokens_approximately`, `tool, InjectedToolCallId`, `GenericFakeChatModel`, `Embeddings`,
`ChatAnthropic`.

Additionally used (not in the original §4.2 list but needed): `langgraph.store.sqlite.SqliteStore`
(exists, see below), `langgraph.types.Overwrite` (see below), `langgraph.errors.ParentCommand`,
`langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer`, `langgraph.config.get_config`.

## `add_node` retry/cache/defer kwargs

`retry_policy=`, `cache_policy=`, and `defer=` are all keyword arguments directly on
`StateGraph.add_node` in 1.2.x (not nested under some other config object). `destinations=` is
also a first-class kwarg, used purely for graph rendering - it has **no effect on routing**
(confirmed empirically, see the Mermaid/`get_graph` gotcha below).

## Default recursion limit

`langgraph._internal._config.DEFAULT_RECURSION_LIMIT = 10007` (env-overridable via
`LANGGRAPH_DEFAULT_RECURSION_LIMIT`). This is *far* larger than the `25` a lot of older
LangGraph docs/examples assume. Two consequences we hit directly:

- A runaway loop (`fake_behavior="tool_loop"`, c27) does not hit `GraphRecursionError` quickly -
  it would iterate ~10,000 times first, which is a *de facto* hang in a demo/test even though it
  isn't a true infinite loop. `RemainingSteps` (read from state, decremented every step relative
  to whatever `recursion_limit` is configured for *that* invoke) has to be checked *inside* the
  node doing the looping (`tech_llm`, see `subgraphs/tech_agent.py`) to degrade gracefully well
  before the hard limit - it is not automatically enforced per-agent.
- We set our own default via `supportpilot.config.DEFAULT_RECURSION_LIMIT = 25` and pass it
  explicitly as `config["recursion_limit"]` from the CLI and in any demo/test that wants a
  "normal-sized" recursion budget.

## `cache hits` in the `updates` stream

A `CachePolicy` cache hit does **not** produce a visibly different shape in `stream_mode="updates"`
- the node's return value looks identical whether it ran or was served from cache. The only
way we found to *prove* a hit is to instrument the underlying work (here: a module-level
`Counter` in `retrieval/tfidf.py` that only increments on a real TF-IDF search) and show the
counter does not increase on a repeat call. `c23`'s test and demo both do this.

## `version="v2"` stream/invoke format

`Pregel.stream`/`.invoke` accept `version: Literal["v1", "v2"] = "v1"`, so the flag exists, but we
did not find it changes payload shape in any way that affects this project's rendering - the CLI
does not expose a `--v2` flag since there was nothing user-visible to switch. Noted for
completeness rather than left silently unimplemented.

## `Overwrite`

`langgraph.types.Overwrite(value)` bypasses a channel's reducer for exactly one write. This isn't
mentioned in agents.md but was *necessary*: `hops` is `Annotated[int, operator.add]` and needs to
reset to `0` at the start of every new turn (not accumulate across the whole thread), so
`input_guardrail` writes `"hops": Overwrite(0)` instead of a plain `0` (which the `add` reducer
would just add to the running total). Confirmed empirically: `{"hops": 0}` against an `add`
reducer adds 0 (no-op on the total); `{"hops": Overwrite(0)}` actually resets it.

## `SqliteStore`

`langgraph.store.sqlite.SqliteStore` exists and supports a vector `index=` config
(`SqliteIndexConfig`) in this install, so `memory/store.py`'s `build_store("sqlite")` uses it for
real rather than falling back to `InMemoryStore`. It needs `.setup()` called once after
construction (creates its tables).

**Gotcha**: with a plain `sqlite3.connect(...)` (Python's default *deferred* isolation level),
`store.setup()`'s migration DDL (`conn.executescript(...)`) leaves an implicit transaction open,
and the store's own first `.put()`/`.get()` afterward fails trying to issue its own `BEGIN`
(`sqlite3.OperationalError: cannot start a transaction within a transaction`). Fix: connect with
`isolation_level=None` (autocommit) so the store manages its own transactions exclusively - see
`memory/store.py:build_store`. `SqliteSaver` (`persistence.py`) never hit this because we never
call its `.setup()` explicitly (it lazily self-initializes per-call in a way that doesn't
collide); `SqliteStore.setup()` does, if called with a connection in the default isolation mode.

## `update_state(..., checkpoint_id=...)` needs `checkpoint_ns` explicitly

Calling `update_state`/`invoke(None, ...)` (replay/fork, c19) with a config of just
`{"thread_id": ..., "checkpoint_id": ...}` (no `checkpoint_ns`) causes
`SqliteSaver.put_writes` to raise `KeyError: 'checkpoint_ns'` in this version - it indexes the
writes table on `config["configurable"]["checkpoint_ns"]` without defaulting it. Always include
`"checkpoint_ns": ""` explicitly in configs built for replay/fork (`persistence.py:_cfg`).

## `update_state(as_node=...)` cannot recompute a `Command`'s `goto`

This is the most consequential gotcha we hit. `update_state(cfg, values, as_node="X")` writes
`values` as if node `X` had just produced them, then determines the *next* task using whatever
static/conditional routing is registered for `X` in the graph. If `X`'s routing is a
`Command(goto=...)` returned from inside the node's own Python body, `update_state` **cannot**
re-run that Python logic against the new values - the recorded pending task (from the original
run) is reused as-is, so a fork that changes a value which *would* change a `Command`'s decision
(e.g. `refund.amount` flipping `auto_approvable`) silently has **no effect** on routing.

A **conditional edge** (`add_conditional_edges`, i.e. a plain function registered separately from
the node body) *is* re-evaluated correctly against the forked values.

Fix applied: `billing_agent` (`nodes/billing_wrapper.py`) is a **plain node returning a dict**,
with routing done by a separate `route_after_billing` conditional edge
(`add_conditional_edges("billing_agent", route_after_billing, [...])`) instead of the node
returning `Command(goto=...)` itself. This is the only reason the "fork changes an
auto-approve decision" demo (§12, agents.md) actually works as specified.

## A compiled subgraph node + a static outgoing edge does not compose with an inner `Command(graph=Command.PARENT)`

`tech_agent` was originally added straight as a compiled subgraph node
(`add_node("tech_agent", build_tech_graph())`) with a static `add_edge("tech_agent",
"supervisor")`, mirroring `kb_agent`. When `transfer_to_billing` (deep inside the tech ReAct loop,
via `ToolNode`) raises `Command(graph=Command.PARENT, goto="billing_agent")`, **both** things
happened in one run: the parent-crossing `Command` correctly landed on `billing_agent`, *and* the
static `tech_agent -> supervisor` edge *also* fired (with the subgraph node's own, now-truncated
completion), running `supervisor` (and everything downstream of it) a second, spurious time -
double `save_memory`, wrong final `active_agent`, etc. `kb_agent` never has this problem because
none of its internal routing crosses `Command.PARENT`.

Fix applied (`nodes/tech_wrapper.py`): `tech_agent` is now a **plain wrapper function** that
`.invoke()`s the compiled tech subgraph internally and returns its own explicit
`Command(goto="supervisor", update=...)` for the normal-completion case. It has **no static
outgoing edge**, so there is nothing for the inner `ParentCommand` to race against - a genuine
`Command(graph=Command.PARENT)` raised inside `_tech_graph.invoke(...)` simply propagates as a
Python exception straight through the wrapper to the parent Pregel loop, unopposed.

## `get_state(...).next` can misreport `()` on the *second* `interrupt()` within one re-entrant node call

`human_review` calls `interrupt()` twice in one node body (c18). After resuming the *first*
interrupt (so the node re-runs from the top and immediately hits the *second* `interrupt()`),
`graph.get_state(cfg).next` reads back as `()` even though `graph.get_state(cfg).tasks[*]` clearly
shows a pending task with a real `Interrupt`. The first interrupt (before any resume) reports
`.next` correctly as `("human_review",)`; only the second, re-entrant one is affected. We did not
find a public flag to fix this - the workaround is to treat `any(t.interrupts for t in
snap.tasks)` as authoritative for "is anything paused right now", never bare truthiness of
`.next`. Both `cli.py` (`_pending_interrupts`) and the concept demos/tests use this check.

## `get_graph(xray=True)` (Mermaid export) only traverses *reachable* edges from `START`

A node that returns `Command(goto=...)` with **no** `destinations=` hint registered on
`add_node(...)` is invisible to `get_graph()`'s traversal beyond that node - everything
downstream of it (even nodes reached only via perfectly ordinary `add_edge`/
`add_conditional_edges`, several hops later) silently disappears from the rendered graph, because
the BFS never gets there. `input_guardrail` originally had no `destinations=` and the entire rest
of the parent graph (everything from `load_memory` onward) vanished from `docs/graph.mmd` as a
result. Fix: every `Command`-returning node needs an explicit `destinations=(...)` tuple/dict.

`get_graph(xray=True)` also probes every node's `cache_policy.key_func` with a placeholder/blank
payload while enumerating possible tasks (not just real `Send` args), so a `key_func` that
indexes a dict without `.get(..., default)` raises a `KeyError` during rendering alone, with no
graph ever actually running. `retrieve_source`'s `cache_policy.key_func` uses `.get()` with
defaults specifically to survive this probing.

## Gateway statefulness across nodes within one run

`llm.factory.get_gateway(ctx)` is `functools.lru_cache`-memoized keyed on the (frozen, hashable)
`SupportContext` value, so every node within one graph run that shares an equal context gets the
*same* `FakeGateway` instance - this is what lets `fake_behavior="bad_answer"` track "first call"
state (`_bad_answer_used`) across the `generate -> grade -> rewrite -> generate` loop. Tests/demos
that run more than one scenario in the same process call `get_gateway.cache_clear()` between them
to avoid cross-contamination; a context with a different `user_id` also naturally misses the cache.

## Functional-API entrypoints can't bake in their own checkpointer/store either

Just like `graph.make_graph()` (StateGraph) must omit `checkpointer=`/`store=` for `langgraph dev`
(the platform supplies them), a `@entrypoint`-decorated Functional API graph gets the same
treatment: `langgraph dev` refuses to load `daily_digest` with `ValueError: ... includes a custom
checkpointer ... and store ...` if it was decorated with `checkpointer=memory_checkpointer(),
store=InMemoryStore()` directly. Fix (`functional/daily_digest.py`): keep the undecorated workflow
function (`_digest_workflow`) separate from its decoration, and decorate it twice - `daily_digest`
(with local persistence, for the CLI/tests, which need `interrupt()`/resume to work standalone)
and `make_daily_digest()` (no persistence args, for `langgraph.json`, pointed at the *factory*
rather than a pre-built object - same pattern as `make_graph`). Both need the same node name for
consistency, which `entrypoint()` derives from `func.__name__` - set that explicitly on the shared
undecorated function before decorating, since the factory pattern otherwise names it after the
inner function (`_digest_workflow`) instead.

## `langgraph dev` and this machine's editable install

On this machine, `langgraph dev` intermittently fails to import `supportpilot` at all
(`ModuleNotFoundError: No module named 'supportpilot'`) even though `pip install -e .` succeeded
and `python -c "import supportpilot"` works fine in the same venv moments before. This tracks a
macOS-specific quirk we hit repeatedly through this build: the editable-install `.pth` file
(`.venv/lib/.../__editable__.supportpilot-*.pth`) intermittently gets Finder's "hidden" extended
attribute set on it (`chflags nohidden <path>` clears it), which is enough to make some Python
startup paths skip processing it. `langgraph dev` appears to load the graph *file* via a fresh
`importlib` spec rather than going through the normal package-import machinery, and re-triggers
this in a way a plain `python -c "import supportpilot"` doesn't reliably reproduce. We were not
able to get a `langgraph dev` session to reach "Ready" in this sandboxed environment; `langgraph
validate` does pass cleanly (config is well-formed, both graph entries resolve), and both
`make_graph()` and `make_daily_digest()` are exercised directly and pass in
`tests/concepts/test_c30_mermaid.py` and `tests/concepts/test_c29_functional.py`. If you hit the
same error running `langgraph dev` locally: `chflags nohidden` the `.pth` file, or reinstall with
`pip install -e . --force-reinstall --no-deps` right before starting the server.

## Misc

- `langchain_core.tools.ToolNode` natively supports a tool function returning a `Command` (not
  just a plain value/`ToolMessage`) and correctly special-cases `Command(graph=Command.PARENT)` -
  no custom plumbing needed on our side beyond the subgraph-embedding gotcha above.
- `InMemoryStore`/`SqliteStore` both warn ("NumPy not found... pure Python implementation") when
  `numpy` isn't installed; harmless for this project's tiny fact counts, left as a warning rather
  than adding a `numpy` dependency the spec doesn't list.
- Pydantic model instances (`RouteDecision`, `Citation`, `RefundProposal`, ...) stored directly in
  checkpointed state trigger a `"Deserializing unregistered type ... from checkpoint"` warning
  under the default `JsonPlusSerializer` allowlist behaviour (`allowed_msgpack_modules=True`,
  i.e. "permissive with a warning"). We pass an explicit `allowed_msgpack_modules=[...]` (our
  actual schema classes) via `serde.py`'s shared `make_serde()` everywhere a checkpointer or
  cache is constructed, which silences the warning and is the documented way to declare "these
  are our own trusted types".
