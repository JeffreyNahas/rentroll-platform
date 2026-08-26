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

## Immediate next step

**FastAPI tool backend.** One endpoint per gold view (`/portfolio/summary`,
`/occupancy`, `/loss-to-lease`, `/expirations`, `/delinquency`, `/charge-mix`,
`/lease-detail`, `/data-quality`), plus a guarded `run_readonly_sql` escape
hatch (sqlglot AST validation, `rri_readonly` role, row cap, 5s timeout,
full query audit log). Every response carries a `sources` block.
