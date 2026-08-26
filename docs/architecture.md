# Architecture

Schema design decisions and how data flows through the system. Read this
before designing new tables, views, or services.

For the parser-facing view of the raw files, see `docs/data_quality.md`.

---

## Data flow

```
Excel files
    |
    v  scripts/discover.py        structure validation, no DB writes
    v  ingest/parsers/            stateful row classifiers -> pydantic records
    v  ingest/loader.py           idempotent load + reconciliation
    |
Postgres    bronze (raw_row) -> silver (typed entities) -> gold (views)
    |
    v  api/                       FastAPI, every response carries citations
    v  web/  or  agent/           dashboard and/or governed tool-calling agent
    v  evals/                     golden set, trajectory + numeric scoring
```

---

## Schema design decisions

**Snapshot grain.** The files are point-in-time reports, not master data.
Every fact row references a `report_snapshot`. This makes reloads idempotent,
allows a future month of files to land alongside this one, and is the honest
answer to *"what if we hand you next month's 50 files?"*

**`lease` is snapshot-grained, not SCD2.** The exports carry no lease
identifier. Threading a lease across snapshots would require fuzzy matching
on (unit, resident, move-in) that cannot be validated. With the Yardi API
instead of exports, true SCD2 would be right.

**`lease.reported_total`** stores the block's own Total row, so reconciliation
is a SQL query over loaded data rather than a transient check during parsing.

**Bronze layer.** `raw_row` keeps every source row as JSONB so any parse can
be replayed without re-reading spreadsheets.

**One transaction per file at load time.** A bad row in 462a doesn't roll
back the files loaded before it. Within a file, everything commits or nothing
does — no half-loaded snapshots.

**SHA-256 file hash for idempotency.** `make load` is a no-op on re-run:
files already present in `source_file` are skipped without reparsing.

---

## Tables

```
DIMENSIONS   property (property_type)  unit_type  unit  resident
             charge_code (category)
PROVENANCE   source_file (file_hash, n_rows)  report_snapshot  raw_row
FACTS        lease (section, lease_status, reported_total)
             lease_charge (no unique constraint on code)
             property_availability (unclassified_units, states_reconcile)
AUDIT        ingest_error  ingest_audit  query_audit  schema_migration
```

`charge_code.category` ∈ `base_rent | subsidy | concession | amenity |
utility | fee | recovery`. All 32 codes are seeded in migration 002. **An
unmapped code must be a load-time error, not a silent `other`.**

### Reconciliation audits

`ingest_audit.check_name` values, all keyed to a `snapshot_id`:

| Name | Grain | Coverage |
|---|---|---|
| `lease_total` | one per lease with a Total row | 4,106 across 25/25 files |
| `charge_code` | one per code in the file-level summary | 133 across 16/25 files |
| `lease_v_units` | one per property, cross-report | 25 (compares current-section leases vs `total_units`) |

Full column definitions in `db/migrations/001_initalize_schema.sql`.

---

## Gold layer

Nine views in `db/migrations/004_gold_views.sql`. The semantic layer the
API, dashboard, and (eventually) agent tools sit on. Plain views, not
materialized — 4k leases / 9k charges is fast enough. All views granted to
the `rri_readonly` role.

### Foundation
- `v_latest_snapshot` — resolves the current snapshot per `(property, report_type)`. Every other view joins through this.

### Drill-down
- `v_lease_detail` — one row per current-section lease with joined property / unit / resident and a derived `base_rent_actual` (sum of `category = 'base_rent'` charges). Grain: 4,013 rows.

### Property metrics
- `v_occupancy_by_property` — carries `occupancy_source` (`availability_report` where `states_reconcile AND total_units > 0`, `rent_roll_derived` otherwise). Denominator source matches numerator source — mixing would produce nonsense divisions.
- `v_loss_to_lease` — market vs effective base rent. Residential + affordable only; commercial has no `market_rent`, land/mgmt have no leases.
- `v_delinquency_by_property` — rollup of leases with `balance > 0`. No aging buckets (source data doesn't carry them).
- `v_charge_mix_by_property` — long form (one row per `property × category`). `pct_of_property_gross` uses `ABS()` in the denominator so concessions show as share of gross, not net.

### Time-based
- `v_expirations_by_month` — long form (`property × month`). Month-to-month leases (NULL `lease_expiration`) excluded and can be surfaced as a separate KPI.

### Rollups
- `v_portfolio_summary_by_type` — one row per `property_type`. Ratios weighted within type — never blended across types. Occupancy denominator is `SUM(rentable_units)` from `v_occupancy_by_property`, which keeps per-property source consistency.
- `v_data_quality_summary` — long form `metric_name / value`. Powers the dashboard data-quality panel that surfaces `ingest_audit` failures and `unclassified_units`.

### Design rules enforced in the views

- Base rent resolves via `charge_code.category = 'base_rent'`, never a literal `WHERE charge_code = 'RENT'` (would zero five commercial properties).
- Never blend across property types — every rollup groups by `property_type`, and cross-type portfolio ratios are not exposed.
- Non-revenue units (`model + down + admin`) excluded from every occupancy denominator.
- `occupancy_source` is carried through `v_occupancy_by_property` and inherited by every downstream view that uses it.
- Snapshot-aware end-to-end: loading next month's files won't affect today's views.

---

## API layer

FastAPI, sync, sitting on `psycopg_pool`. Full endpoint catalogue and
envelope spec in `docs/api.md`. Highlights:

- **Two connection pools.** `readonly_conn()` binds to `rri_readonly`
  (SELECT only, 5s statement timeout at the role level). `privileged_conn()`
  is reserved for writes to `query_audit`; no query endpoint touches it.
  Separation makes it impossible to accidentally read through a role that
  can also write.
- **Response envelope.** `{data, sources, row_count, query_time_ms, warnings}`.
  `sources` lists exactly the snapshots that contributed — up to 50 for
  portfolio endpoints, typically 2 for property-scoped ones. `run_readonly_sql`
  returns `sources: null` plus a warning explaining why.
- **PII masking** is applied at serialization time (`api/pii.py`), not in
  the DB. `MASK_PII=true` rewrites `display_name` to `Resident #<id>`;
  storage stays unmasked.
- **Escape hatch guard.** `POST /run-readonly-sql` runs a sqlglot AST
  validation (SELECT/CTE only, no forbidden functions, single statement,
  row-cap wrap) before executing. Every attempt — allowed or blocked —
  writes a row to `query_audit`.
