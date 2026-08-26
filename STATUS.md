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

## Immediate next step

**Gold views** — start with `occupancy_by_property`. Segmented by property
type, non-revenue units excluded from the denominator, `occupancy_source`
carried through per row (`availability_report` where `states_reconcile`,
`rent_roll_derived` where it doesn't). Full list in `TODO.md`.
