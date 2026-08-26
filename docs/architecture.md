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
