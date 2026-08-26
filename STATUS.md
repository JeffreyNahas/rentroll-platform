# Status

Snapshot of "where we are." Read this at the start of a work session.

For upcoming work, see `TODO.md`.
For a log of past decisions and mistakes, see `docs/journal.md`.

---

## Shipped

| Component | Notes |
|---|---|
| `docker-compose.yml` | Postgres 16 + Adminer, healthchecked |
| `Makefile` | `up down reset migrate load discover parse eval test lint` |
| `db/migrations/001_*` | Full schema DDL |
| `db/migrations/002_*` | 32 charge codes with categories |
| `db/migrations/003_*` | `rri_readonly` role, SELECT-only, 5s timeout |
| `ingest/migrate.py` | Migration runner |
| `ingest/normalize.py` | `to_money` (parens negatives), `to_date` (Excel serials), `property_type` |
| `ingest/models.py` | Pydantic records with date-order and vacancy validators |
| `ingest/parsers/` | Both parsers. 4,106 / 4,106 per-lease reconciliations exact, 0 warnings |
| `scripts/discover.py` | Structure validation across all 50 files. `make discover` |
| `scripts/batch_parse.py` | Parser + reconciliation batch test. `make parse` |
| `ingest/loader.py` + `cli.py` | `make load`. Idempotent by file hash |
| `db/migrations/004_gold_views.sql` | 9 gold views: `v_latest_snapshot`, `v_lease_detail`, `v_occupancy_by_property` (with `occupancy_source`), `v_loss_to_lease`, `v_delinquency_by_property`, `v_charge_mix_by_property`, `v_expirations_by_month`, `v_portfolio_summary_by_type`, `v_data_quality_summary`. All granted to `rri_readonly` |
| `api/` | FastAPI tool backend. `make api` on `:8000`. 12 endpoints — one per gold view + `/properties/{code}/leases` (paginated, PII-masked) + guarded `POST /run-readonly-sql`. Two connection pools, response envelope with `sources`, sqlglot AST guard, `query_audit` logging. Full spec in `docs/api.md`. |

## Loaded database state

After `make load` (as of the last work session):

| Table | Rows |
|---|---|
| `property` | 25 |
| `unit` | 4,013 |
| `unit_type` | 448 |
| `resident` | 3,923 |
| `lease` | 4,106 |
| `lease_charge` | 9,177 |
| `property_availability` | 25 |
| `source_file` / `report_snapshot` | 50 / 50 |
| `raw_row` (bronze) | 19,525 |
| `ingest_audit` | 4,264 (4,261 pass, 3 fail) |
| `ingest_error` | 0 |

The 3 audit failures are the known file-level source oddities documented in
`docs/data_quality.md`: 462a `SUBSIDY`, 462a `SEC8CRD`, 153c
`lease_v_units`. No parser bugs remain.

## Verified against gold views

- 115r: 288 occupied of 300 rentable, `occupancy_source = availability_report`.
  Base rent $754,322 (matches `docs/data_quality.md` line 191 to the cent).
- 153c: `occupancy_source = rent_roll_derived`, 1 occupied of 7 rentable
  (availability said 0 units; rent roll had 7).
- Portfolio: 12 residential / 6 affordable / 5 commercial / 1 land / 1 other.
- Commercial rentable_units (49) exceeds commercial total_units (42) by 7 —
  reflects the 153c source disagreement, not a view bug.
- `v_data_quality_summary` surfaces the 3 known audit failures.
- **Noteworthy:** 115r `loss_to_lease` is −$22,830 (−3.12%) — actuals *exceed*
  market. Yardi's Market Rent field appears to behave as a floor here, not
  an asking rent. Real business signal, not a bug.

## Verified against the API

- `GET /health` → `PostgreSQL 16.15`, 50 snapshots loaded, `mask_pii=true`.
- `GET /portfolio/summary` → 5 rows, matches gold view (12 res @ 92.13%, 6
  aff @ 93.68%, 5 comm @ 53.06%). Cites 50 sources.
- `GET /occupancy?property_code=115r` → `occupancy_source=availability_report`,
  270 occupied of 300 rentable. Cites 2 sources (115r rent roll + availability).
- `GET /properties/115r/leases?limit=3` → 300 total, PII correctly masked
  (`Resident #1`, `Resident #2`).
- `GET /portfolio/data-quality` → the 3 known audit failures visible.
- `POST /run-readonly-sql` — all guard paths exercised:
  valid SELECT → executed; `INSERT` → blocked ("only SELECT allowed");
  `pg_read_file('/etc/passwd')` → blocked ("forbidden function");
  `SELECT 1; DROP TABLE property;` → blocked ("multiple statements");
  `WITH … SELECT` → executed. All 5 attempts written to `query_audit`.

## Immediate next step

**Presentation layer.** Next.js + TS dashboard preferred (hits the JD
stack, patches a stated gap); Streamlit is the time-boxed fallback. Tiles
from `/portfolio/summary`, a property picker driving
`/properties/{code}` + `/properties/{code}/leases`, expirations chart from
`/expirations`, and a data-quality panel from `/portfolio/data-quality`
that surfaces the 3 known audit failures.
