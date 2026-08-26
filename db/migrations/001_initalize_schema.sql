-- ═══════════════════════════════════════════════════════════════════════════
-- Rent Roll Intelligence — initial schema
--
-- Grain note: the source files are point-in-time REPORTS, not master data.
-- Every fact row therefore hangs off a report_snapshot, which makes re-loads
-- idempotent and lets a future month of files land alongside this one.
--
-- Layering:  raw_row  -> typed entities  -> views 
-- ═══════════════════════════════════════════════════════════════════════════


-- DIMENSIONS

-- property_type drives everything downstream: which charge codes mean rent,
-- how occupancy is computed, and how metrics are segmented. Blending a
-- 3-unit retail strip with a 775-unit apartment complex is meaningless.
CREATE TABLE property (
    property_id     SERIAL PRIMARY KEY,
    property_code   TEXT NOT NULL UNIQUE,          -- '115r', '134land', 'altapm'
    property_name   TEXT NOT NULL,
    property_type   TEXT NOT NULL
        CHECK (property_type IN ('residential','affordable','commercial',
                                 'land','other'))
);

CREATE TABLE unit_type (
    unit_type_id    SERIAL PRIMARY KEY,
    property_id     INT  NOT NULL REFERENCES property,
    code            TEXT NOT NULL,                 -- '115mxA05'
    UNIQUE (property_id, code)
);

CREATE TABLE unit (
    unit_id         SERIAL PRIMARY KEY,
    property_id     INT  NOT NULL REFERENCES property,
    unit_number     TEXT NOT NULL,                 -- 'A103'
    unit_type_id    INT  REFERENCES unit_type,
    square_feet     INT  CHECK (square_feet IS NULL OR square_feet >= 0),
    UNIQUE (property_id, unit_number)
);

CREATE TABLE resident (
    resident_id     SERIAL PRIMARY KEY,
    property_id     INT  NOT NULL REFERENCES property,
    resident_code   TEXT NOT NULL,                 -- Yardi tenant code 't0019683'
    display_name    TEXT,                          -- masked when MASK_PII=true
    UNIQUE (property_id, resident_code)
);

-- Category, not the literal code, defines what a charge MEANS. Commercial
-- properties carry no 'RENT' code at all, so any query matching on the
-- literal string silently returns zero rent for five properties.
CREATE TABLE charge_code (
    charge_code     TEXT PRIMARY KEY,
    description     TEXT,
    category        TEXT NOT NULL
        CHECK (category IN ('base_rent','subsidy','concession','amenity',
                            'utility','fee','recovery'))
);


-- PROVENANCE

CREATE TABLE source_file (
    source_file_id  SERIAL PRIMARY KEY,
    filename        TEXT NOT NULL,
    file_hash       TEXT NOT NULL UNIQUE,          -- sha256 => idempotent loads
    report_type     TEXT NOT NULL
        CHECK (report_type IN ('rent_roll','unit_availability')),
    n_rows          INT,                           -- distinguishes an empty
                                                   -- file from a failed parse
    parser_version  TEXT NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE report_snapshot (
    snapshot_id     SERIAL PRIMARY KEY,
    source_file_id  INT  NOT NULL REFERENCES source_file,
    property_id     INT  NOT NULL REFERENCES property,
    report_type     TEXT NOT NULL,
    as_of_date      DATE NOT NULL,
    UNIQUE (property_id, report_type, as_of_date)
);

-- Bronze: every source row kept verbatim, so any parse can be replayed
-- without re-reading the spreadsheets.
CREATE TABLE raw_row (
    raw_row_id      BIGSERIAL PRIMARY KEY,
    source_file_id  INT   NOT NULL REFERENCES source_file,
    source_row      INT   NOT NULL,
    payload         JSONB NOT NULL
);


-- FACTS

-- Snapshot-grained, not SCD2: the exports carry no lease identifier, so
-- threading one lease across snapshots would require fuzzy matching on
-- (unit, resident, move-in) that cannot be validated.
CREATE TABLE lease (
    lease_id            SERIAL PRIMARY KEY,
    snapshot_id         INT  NOT NULL REFERENCES report_snapshot,
    unit_id             INT  NOT NULL REFERENCES unit,
    resident_id         INT  REFERENCES resident,        -- NULL when vacant
    -- 'future' rows are signed but not moved in; counting them as occupied
    -- would inflate occupancy by 93 units portfolio-wide.
    section             TEXT NOT NULL CHECK (section IN ('current','future')),
    lease_status        TEXT NOT NULL
        CHECK (lease_status IN ('current','notice','vacant','future')),
    is_vacant           BOOLEAN NOT NULL,
    market_rent         NUMERIC(12,2),
    resident_deposit    NUMERIC(12,2),
    other_deposit       NUMERIC(12,2),
    balance             NUMERIC(12,2),
    move_in_date        DATE,
    lease_expiration    DATE,
    move_out_date       DATE,
    reported_total      NUMERIC(12,2),   -- the block's own Total row: the
                                         -- primary reconciliation target
    source_row          INT  NOT NULL,
    UNIQUE (snapshot_id, unit_id, source_row)
);

-- No unique constraint on (lease_id, charge_code): a lease legitimately
-- carries the same code more than once (two parking spaces, two pet fees).
CREATE TABLE lease_charge (
    lease_charge_id SERIAL PRIMARY KEY,
    lease_id        INT  NOT NULL REFERENCES lease ON DELETE CASCADE,
    charge_code     TEXT NOT NULL REFERENCES charge_code,
    amount          NUMERIC(12,2) NOT NULL,   -- concessions stored negative
    source_row      INT  NOT NULL
);

-- One row per property, not per unit: the availability report is a
-- property-level rollup used as an independent control total.
CREATE TABLE property_availability (
    availability_id     SERIAL PRIMARY KEY,
    snapshot_id         INT  NOT NULL REFERENCES report_snapshot,
    property_id         INT  NOT NULL REFERENCES property,
    avg_square_feet     INT,
    avg_rent            NUMERIC(12,2),
    total_units         INT NOT NULL,
    occupied_no_notice  INT,
    vacant_rented       INT,
    vacant_unrented     INT,
    notice_rented       INT,
    notice_unrented     INT,
    available           INT,
    model_units         INT,
    down_units          INT,
    admin_units         INT,
    pct_occupied            NUMERIC(6,2),
    pct_occupied_nonrev     NUMERIC(6,2),
    pct_leased              NUMERIC(6,2),
    pct_trend               NUMERIC(6,2),
    -- Units the report counts but never classifies. Three commercial
    -- properties report units with no occupancy states. Stored, never
    -- redistributed across the states and never hidden.
    unclassified_units  INT NOT NULL DEFAULT 0,
    states_reconcile    BOOLEAN NOT NULL,
    source_row          INT NOT NULL,
    UNIQUE (snapshot_id)
);


-- AUDIT

CREATE TABLE ingest_error (
    ingest_error_id SERIAL PRIMARY KEY,
    source_file_id  INT  REFERENCES source_file,
    source_row      INT,
    severity        TEXT CHECK (severity IN ('warn','error')),
    stage           TEXT CHECK (stage IN ('parse','validate','load')),
    message         TEXT NOT NULL,
    raw             JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Two-tier reconciliation results. check_name is one of:
--   'lease_total'   per-lease block total   (25/25 files, ~4,106 checks)
--   'charge_code'   file-level summary      (16/25 files)
--   'lease_v_units' current leases == units (cross-report, per property)
CREATE TABLE ingest_audit (
    ingest_audit_id SERIAL PRIMARY KEY,
    snapshot_id     INT  REFERENCES report_snapshot,
    check_name      TEXT NOT NULL,
    subject         TEXT,                     -- unit number or charge code
    expected        NUMERIC(14,2),
    actual          NUMERIC(14,2),
    delta           NUMERIC(14,2),
    passed          BOOLEAN NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every question the agent asks of the database, allowed or blocked.
CREATE TABLE query_audit (
    query_audit_id  SERIAL PRIMARY KEY,
    question        TEXT,
    tool_name       TEXT,
    generated_sql   TEXT,
    row_count       INT,
    latency_ms      INT,
    blocked         BOOLEAN NOT NULL DEFAULT false,
    block_reason    TEXT,
    asked_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- INDEXES

CREATE INDEX idx_lease_snapshot       ON lease (snapshot_id);
CREATE INDEX idx_lease_unit           ON lease (unit_id);
CREATE INDEX idx_lease_expiration     ON lease (lease_expiration)
    WHERE lease_expiration IS NOT NULL;
CREATE INDEX idx_lease_section        ON lease (section, is_vacant);
CREATE INDEX idx_charge_lease         ON lease_charge (lease_id, charge_code);
CREATE INDEX idx_snapshot_property    ON report_snapshot (property_id, as_of_date DESC);
CREATE INDEX idx_raw_row_file         ON raw_row (source_file_id, source_row);
CREATE INDEX idx_audit_snapshot       ON ingest_audit (snapshot_id, passed);