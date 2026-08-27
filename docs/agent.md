# Agent

Curated tool-use layer over the read-only API. `agent/` is a sibling of
`api/` and `web/`/`dashboard-app/` (see `docs/architecture.md`'s data-flow
diagram), mounted into the same FastAPI process as `POST /agent/ask` (plain
JSON) and `POST /agent/ask/stream` (Server-Sent Events, live progress --
what the command dock uses).

The design rules that shape this layer are `CLAUDE.md` #1 and #2: the
model never computes a number, and there is no raw text-to-SQL -- only a
named toolbelt plus the existing guarded `run_readonly_sql` escape hatch.

---

## How it works

1. `POST /agent/ask` (`api/agent_routes.py`) takes `{question, history}`
   and calls `agent.run.answer()`.
2. `agent/client.py` runs the Anthropic tool-use loop: send the system
   prompt + tool schemas + conversation → the model responds with
   `tool_use` block(s) → `agent/tools.py` dispatches each one as an HTTP
   call to the *running* API (`API_BASE_URL`, default `:8000`) → results
   go back to the model → repeat until it returns final text, capped at
   `MAX_TOOL_ROUNDS = 6` rounds.
3. `agent/grounding.py` extracts every numeric token from the draft
   answer and checks it against every number that actually appeared
   somewhere in this turn's tool results (structured values *and* prose
   inside `warnings[].message` / `note` fields -- an API-authored note is
   a legitimate source for a figure). Anything ungrounded triggers one
   retry with a corrective instruction; still ungrounded after that →
   the response is replaced with the fixed sentence *"I can't verify
   that figure from the data."*
4. The response is `{answer, sources, warnings, tool_calls}` --
   `sources`/`warnings` are the de-duplicated union of every tool call's
   own envelope fields for the turn, and `tool_calls` is a trace (tool
   name + input + latency) of what was actually queried.
5. The system prompt (rule #8) also has the model cite inline, in the
   answer text itself, right after each figure it backs --
   `(property_code, report_type, as of YYYY-MM-DD)` -- using the same
   `sources` data every tool result already carries. A portfolio-wide
   rollup cites the report types/date generally instead of listing every
   property. This is prose the model writes, not app-generated markup, so
   it's guided rather than guaranteed -- the `sources` block is still the
   authoritative citation list.

### Streaming (`POST /agent/ask/stream`)

Same orchestration as `/agent/ask`, but `agent.run.answer_stream()` yields
progress events as the tool-use loop runs, sent as SSE (`data: {...}\n\n`
per event, `api/agent_routes.py`). Progress only -- the answer text itself
is never streamed token-by-token, because it can still be discarded by the
grounding check and replaced with the fail-closed sentence; showing text
that might get retracted a moment later would be worse than a short wait.

Event `type`s:

| Type | Fields | When |
|---|---|---|
| `tool_start` | `tool`, `label` | Right before a named tool is called (`agent/tools.py`'s `TOOL_LABELS`, e.g. "Looking up occupancy") |
| `tool_done` | `tool`, `label`, `ok` | Right after -- `ok` is `false` if the tool result carried an `error` |
| `status` | `message` | A free-text progress note; currently only emitted around a grounding retry ("Double-checking the numbers…") |
| `error` | `message` | Something failed (network, Anthropic API); always immediately followed by a `done` event -- never a bare dropped connection |
| `done` | `answer`, `sources`, `warnings`, `tool_calls` | Terminal event, always exactly one per request -- same shape `/agent/ask` returns in one shot |

`agent.run.answer()` (used by `/agent/ask` and, later, evals) is now a
thin wrapper that drains `answer_stream()` and returns its `done` event --
one implementation of the orchestration logic, not two.

**Grounding is membership, not correctness.** The check verifies every
number in the draft appeared *somewhere* in this turn's tool output; it
cannot verify the number is the *semantically right* one. A model that
hand-counts rows from `list_properties` instead of reading
`portfolio_summary.n_properties` can still miscount and land on a wrong
total that happens to satisfy membership (e.g. by picking a different,
also-present number after a failed retry). Two mitigations are in place
-- `agent/grounding.py` excludes `*_id` fields from the grounded pool
specifically because small identifiers (property_id 1-25, snapshot_id
1-50) were found to coincidentally "ground" miscounted totals during
testing, and `agent/prompts.py` tells the model to prefer a
pre-aggregated tool over tallying row-level ones -- but neither
guarantees semantic correctness. That's what the evals harness
(`TODO.md`, not built here) is for: golden questions with known-correct
numeric answers, scored exactly, across enough runs to see past a single
model sample.

**The right fix for a missing aggregate is a new tool, not a looser
check.** "How many units in total" originally failed closed because no
tool returned a portfolio-wide grand total -- the model summed
`portfolio_summary`'s five per-type rows itself, which is exactly the
computation rule #1 forbids, and grounding correctly rejected it (the
summed figure also happened to be a genuinely different, arguably worse
number than the source-reconciled total -- see `portfolio_totals`
below). The fix was `v_portfolio_totals` / `GET /portfolio/totals` /
the `portfolio_totals` tool, not relaxing the grounding check: keeping
"never let the LLM compute a number" intact and closing the actual tool
gap it was pointing at.

Because tools call the API rather than the database, every answer
inherits PII masking (`MASK_PII`), the response envelope, and the sqlglot
guard for free -- there is no separate DB credential or new SQL surface
for the agent.

## Toolbelt

One tool per endpoint in `docs/api.md`'s catalogue:

| Tool | Endpoint |
|---|---|
| `portfolio_summary` | `GET /portfolio/summary` |
| `portfolio_totals` | `GET /portfolio/totals` |
| `data_quality_summary` | `GET /portfolio/data-quality` |
| `data_quality_failures` | `GET /portfolio/data-quality/failures` |
| `list_properties` | `GET /properties?property_type=` |
| `property_detail` | `GET /properties/{code}` |
| `property_leases` | `GET /properties/{code}/leases?section=&limit=&offset=` |
| `occupancy` | `GET /occupancy?property_type=&property_code=` |
| `loss_to_lease` | `GET /loss-to-lease?...` |
| `delinquency` | `GET /delinquency?...` |
| `charge_mix` | `GET /charge-mix?...` |
| `expirations` | `GET /expirations?...&from=&to=` |
| `run_readonly_sql` | `POST /run-readonly-sql` -- last resort; the system prompt tells the model to prefer a named tool whenever one applies |

Tool schemas and dispatch both live in `agent/tools.py`, generated by
hand from the same catalogue -- no tool exists that isn't also a
documented API endpoint.

## Audit trail

`run_readonly_sql` calls still write to `query_audit` exactly as they did
before the agent existed (`api/sql.py`'s existing guard path -- unchanged).
Named-tool calls are not (yet) written to `query_audit`; their trace is
the `tool_calls` field returned on every `/agent/ask` response instead.
If per-call DB auditing of named tools is wanted later, `query_audit`
already has generic `tool_name`/`question` columns for it -- see
`db/migrations/001_initalize_schema.sql`.

## Config

Set in `.env` (see `.env.example`):

```
ANTHROPIC_API_KEY=...
AGENT_MODEL=claude-haiku-4-5          # optional, this is the default
API_BASE_URL=http://127.0.0.1:8000    # optional, this is the default
```

## Running

```bash
make api                                  # the agent's tools call this
curl -s -X POST http://127.0.0.1:8000/agent/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "which properties are on a rent-roll-derived occupancy source, and why?"}' | jq
```

## Not yet built

- Evals harness (`TODO.md`) -- `agent.run.answer()`'s signature is
  deliberately evals-ready (plain question/history in, a typed
  `AgentResponse` out, no FastAPI import) but the harness itself isn't
  built here.
- Per-call `query_audit` rows for named tools (see above).
- Dynamic agent-authored charts / pin-to-canvas.
- Token-by-token streaming of the answer text (deliberately out of scope
  -- see "Streaming" above).
