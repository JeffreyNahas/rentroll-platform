# API

Read-only HTTP layer over the gold views. Two consumers, one API:

- **Dashboard** — populates tiles and drill-downs.
- **Agent** (future) — treats the same endpoints as tools.

`make api` runs the dev server on `:8000`. Swagger UI at `/docs`, ReDoc at
`/redoc`.

The design rules that shape this layer are in `CLAUDE.md`; the underlying
views are in `docs/architecture.md`. This file documents *what the API
returns* — the endpoint catalogue, the envelope, and the guard.

---

## Envelope

Every query endpoint returns the same shape:

```json
{
  "data": [ /* typed rows */ ],
  "sources": [
    {
      "snapshot_id": 1,
      "property_code": "115r",
      "report_type": "rent_roll",
      "filename": "ResAnalytics_Rent_Roll_with_Lease_Charges_115r.xlsx",
      "as_of_date": "2026-02-25"
    }
  ],
  "row_count": 288,
  "query_time_ms": 14,
  "warnings": []
}
```

- **`sources`** — one entry per `(property, report_type)` at the latest
  snapshot that contributed to the response. Property-scoped endpoints cite
  their two files; portfolio endpoints cite all 50. The paginated leases
  endpoint attaches an extra `pagination` block.
- **`warnings`** — populated only when something notable is being conveyed.
  The escape-hatch endpoint always includes one warning explaining why
  `sources` is `null`.

## Endpoint catalogue

| Method | Path | Backing view | Filters |
|---|---|---|---|
| `GET` | `/health` | — | — |
| `GET` | `/portfolio/summary` | `v_portfolio_summary_by_type` | — |
| `GET` | `/portfolio/data-quality` | `v_data_quality_summary` | — |
| `GET` | `/properties` | `property` | `?property_type=` |
| `GET` | `/properties/{code}` | `v_occupancy_by_property` + `v_charge_mix_by_property` + `v_delinquency_by_property` + `v_loss_to_lease` | — |
| `GET` | `/properties/{code}/leases` | `v_lease_detail` | `?limit= &offset=` (PII masked) |
| `GET` | `/occupancy` | `v_occupancy_by_property` | `?property_type= &property_code=` |
| `GET` | `/loss-to-lease` | `v_loss_to_lease` | `?property_type= &property_code=` |
| `GET` | `/delinquency` | `v_delinquency_by_property` | `?property_type= &property_code=` |
| `GET` | `/charge-mix` | `v_charge_mix_by_property` | `?property_type= &property_code=` |
| `GET` | `/expirations` | `v_expirations_by_month` | `?property_type= &property_code= &from= &to=` |
| `POST` | `/run-readonly-sql` | guarded escape hatch | body: `{sql, question?}` |

Row shapes match the corresponding gold view columns 1:1; the source of
truth for column meanings is `db/migrations/004_gold_views.sql`.

## Governance

- **Two connection pools.** `readonly_conn()` binds to `rri_readonly` (SELECT
  only, 5s statement timeout enforced at the role level in migration 003).
  `privileged_conn()` exists solely for writes to `query_audit`; no query
  endpoint touches it.
- **PII masking.** `MASK_PII=true` (default) rewrites `display_name` to
  `Resident #<resident_id>` at serialization time. Applied by
  `api/pii.py`, called in `/properties/{code}/leases`. Storage stays
  unmasked; masking is a boundary concern.
- **CORS.** Allowed for `http://localhost:3000` (Next.js) and
  `http://localhost:8501` (Streamlit) by default. Adjust
  `Settings.cors_origins` in `api/config.py`.

## The escape hatch: `POST /run-readonly-sql`

Body:

```json
{
  "sql": "SELECT property_type, count(*) FROM property GROUP BY 1",
  "question": "how many properties per type"
}
```

**Guard order** (any failure short-circuits with a 400 and writes a
`query_audit` row with `blocked=true`):

1. Parse with sqlglot (Postgres dialect). Reject on parse error.
2. Exactly one statement.
3. Root expression must be `Select`, `With`, `Subquery`, or `Union`. Any
   `Insert`, `Update`, `Delete`, `Merge`, `Drop`, `Create`, `Alter`,
   `Truncate`, `Grant`, or `Command` node anywhere in the AST rejects.
4. No forbidden function calls. The deny list is in `api/sql_guard.py` —
   currently `pg_read_file`, `pg_read_binary_file`, `pg_read_server_files`,
   `pg_ls_dir`, `pg_stat_file`, `lo_import`, `lo_export`, `dblink`,
   `dblink_exec`, `pg_terminate_backend`, `pg_cancel_backend`,
   `current_setting`, `set_config`.
5. Wrap in `SELECT * FROM (…) _guarded LIMIT 1000` so the row cap is
   enforced regardless of what the user asks for.
6. Execute via `rri_readonly`. The role-level 5s `statement_timeout`
   handles runaway queries; the failure surfaces as a 400 with the DB
   error text as `block_reason`.

**Response**:

- On success: standard envelope with `sources: null`, one warning
  (`code: unprovenanced`), plus `row_cap` and `wrapped_sql` fields.
- On block: `400` with `{blocked: true, reason: "...", hint: "..."}`.

**Every attempt** — allowed or blocked — writes one row to `query_audit`
so the audit trail is the source of truth for what was asked.

## Running

```bash
make api                              # dev server on :8000, --reload
uvicorn api.app:app --port 8000       # equivalent
python -m api                         # equivalent (uses uvicorn under the hood)
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health | jq
```

Example: portfolio summary + a property drill-in:

```bash
curl -s http://127.0.0.1:8000/portfolio/summary | jq
curl -s http://127.0.0.1:8000/properties/115r | jq
curl -s "http://127.0.0.1:8000/properties/115r/leases?limit=5" | jq
```

Example: escape hatch:

```bash
curl -s -X POST http://127.0.0.1:8000/run-readonly-sql \
  -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT category, sum(sum_amount) FROM v_charge_mix_by_property GROUP BY 1", "question":"charge mix rollup"}' | jq
```

## Not yet built

- Auth / rate limiting (take-home, single user).
- Websocket streaming.
- Response caching (measure first; gold views are fast).
- Formal pytest suite (TODO item; smoke testing is via `/docs` and curl).
- `POST /ingest` — the privileged pool exists to make this trivial, but
  loading stays a CLI (`make load`) for now.
