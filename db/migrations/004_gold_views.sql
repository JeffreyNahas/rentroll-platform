-- ═══════════════════════════════════════════════════════════════════════════
-- Gold-layer views.
--
-- These are the semantic layer the API, the dashboard, and (eventually) the
-- agent's tools sit on. Views are declared in dependency order and follow
-- five rules that are load-bearing across the whole submission:
--
--   1. Base rent resolves via charge_code.category = 'base_rent', never a
--      literal string match. Five commercial properties have no 'RENT' code
--      at all -- a naive filter silently zeroes them.
--   2. Metrics never blend across property_type. Averaging a 3-unit retail
--      strip with a 775-unit apartment complex produces a meaningless
--      number.
--   3. Non-revenue units (model / down / admin) are excluded from every
--      occupancy denominator.
--   4. v_occupancy_by_property carries an occupancy_source column --
--      'availability_report' where the availability states reconcile,
--      'rent_roll_derived' where they don't (three commercial properties
--      whose states are incomplete, plus 153c where availability reports
--      0 units for 7 rent-roll leases).
--   5. Everything is snapshot-aware: v_latest_snapshot picks the current
--      snapshot per (property, report_type), and every downstream view
--      filters through it. Loading next month's files becomes a no-op for
--      today's dashboard.
--
-- Plain views, not materialized. 4,106 leases / 9,177 charges is fast
-- enough. Promote individual views to matviews only if the API layer proves
-- one is slow.
-- ═══════════════════════════════════════════════════════════════════════════


-- ─── FOUNDATION ────────────────────────────────────────────────────────────

-- The current snapshot per (property, report_type). Every downstream view
-- joins through this so a future snapshot appears alongside without
-- double-counting today.
CREATE OR REPLACE VIEW v_latest_snapshot AS
SELECT DISTINCT ON (property_id, report_type)
    snapshot_id,
    property_id,
    report_type,
    as_of_date
FROM report_snapshot
ORDER BY property_id, report_type, as_of_date DESC;

COMMENT ON VIEW v_latest_snapshot IS
  'Current snapshot per (property, report_type). Foundation for all gold views.';


-- ─── DRILL-DOWN ────────────────────────────────────────────────────────────

-- One row per current-section lease at the latest snapshot, joined with
-- property / unit / resident dimensions and a derived base_rent_actual
-- (sum of category = 'base_rent' charges). This is the row-level table the
-- dashboard shows on drill-down, and the shape a `search_units` or
-- `lease_detail` agent tool returns.
--
-- PII: display_name is exposed as-is; masking is a response-time concern
-- (FastAPI applies MASK_PII before returning to the client), not a schema
-- concern.
CREATE OR REPLACE VIEW v_lease_detail AS
WITH base_rent AS (
    SELECT lc.lease_id, SUM(lc.amount) AS base_rent_actual
    FROM lease_charge lc
    JOIN charge_code cc ON cc.charge_code = lc.charge_code
    WHERE cc.category = 'base_rent'
    GROUP BY lc.lease_id
)
SELECT
    l.lease_id,
    l.snapshot_id,
    l.source_row,
    ls.as_of_date,
    p.property_id,
    p.property_code,
    p.property_name,
    p.property_type,
    u.unit_id,
    u.unit_number,
    u.square_feet,
    ut.code           AS unit_type_code,
    r.resident_id,
    r.resident_code,
    r.display_name,
    l.section,
    l.lease_status,
    l.is_vacant,
    l.market_rent,
    l.resident_deposit,
    l.other_deposit,
    l.balance,
    l.move_in_date,
    l.lease_expiration,
    l.move_out_date,
    l.reported_total,
    COALESCE(br.base_rent_actual, 0)::numeric(12,2) AS base_rent_actual
FROM lease l
JOIN v_latest_snapshot ls
     ON  ls.snapshot_id = l.snapshot_id
     AND ls.report_type = 'rent_roll'
JOIN unit u        ON u.unit_id = l.unit_id
JOIN property p    ON p.property_id = u.property_id
LEFT JOIN unit_type ut ON ut.unit_type_id = u.unit_type_id
LEFT JOIN resident r   ON r.resident_id   = l.resident_id
LEFT JOIN base_rent br ON br.lease_id     = l.lease_id
WHERE l.section = 'current';

COMMENT ON VIEW v_lease_detail IS
  'One row per current-section lease at the latest rent-roll snapshot. '
  'Excludes future applicants. Includes base_rent_actual derived via '
  'charge_code.category.';


-- ─── OCCUPANCY ─────────────────────────────────────────────────────────────

-- The headline occupancy number per property, with source attribution.
--
-- The source choice: prefer the availability report where its five states
-- reconcile (residential and most affordable properties). Fall back to the
-- rent roll for the three commercial properties whose availability states
-- are incomplete, and for 153c where availability reports 0 units for a
-- property whose rent roll contains 7 leases.
--
-- When falling back to the rent roll, rentable_units also comes from the
-- rent roll (occupied + notice + vacant) so the denominator matches the
-- numerator. Mixing sources would introduce nonsense divisions.
CREATE OR REPLACE VIEW v_occupancy_by_property AS
WITH avail AS (
    SELECT
        pa.property_id,
        pa.total_units,
        (pa.model_units + pa.down_units + pa.admin_units) AS non_revenue_units,
        pa.unclassified_units,
        pa.states_reconcile,
        pa.occupied_no_notice                              AS av_occupied,
        (pa.notice_rented + pa.notice_unrented)            AS av_notice,
        (pa.vacant_rented + pa.vacant_unrented)            AS av_vacant
    FROM property_availability pa
    JOIN v_latest_snapshot ls
         ON  ls.snapshot_id = pa.snapshot_id
         AND ls.report_type = 'unit_availability'
),
rr AS (
    SELECT
        p.property_id,
        SUM(CASE WHEN l.lease_status = 'current' THEN 1 ELSE 0 END) AS rr_occupied,
        SUM(CASE WHEN l.lease_status = 'notice'  THEN 1 ELSE 0 END) AS rr_notice,
        SUM(CASE WHEN l.lease_status = 'vacant'  THEN 1 ELSE 0 END) AS rr_vacant
    FROM lease l
    JOIN v_latest_snapshot ls
         ON  ls.snapshot_id = l.snapshot_id
         AND ls.report_type = 'rent_roll'
    JOIN unit u     ON u.unit_id = l.unit_id
    JOIN property p ON p.property_id = u.property_id
    WHERE l.section = 'current'
    GROUP BY p.property_id
),
combined AS (
    SELECT
        p.property_id,
        p.property_code,
        p.property_name,
        p.property_type,
        ls.as_of_date,
        COALESCE(a.total_units, 0)         AS total_units,
        COALESCE(a.non_revenue_units, 0)   AS non_revenue_units,
        COALESCE(a.unclassified_units, 0)  AS unclassified_units,
        COALESCE(a.states_reconcile, TRUE) AS states_reconcile,
        COALESCE(a.av_occupied, 0)  AS av_occupied,
        COALESCE(a.av_notice, 0)    AS av_notice,
        COALESCE(a.av_vacant, 0)    AS av_vacant,
        COALESCE(rr.rr_occupied, 0) AS rr_occupied,
        COALESCE(rr.rr_notice, 0)   AS rr_notice,
        COALESCE(rr.rr_vacant, 0)   AS rr_vacant,
        -- Availability wins where its states reconcile AND it actually
        -- counts units. The second clause catches 153c: total_units=0 while
        -- rent roll contains 7 leases -- availability is silent, not
        -- authoritative.
        CASE
            WHEN COALESCE(a.states_reconcile, FALSE)
             AND COALESCE(a.total_units, 0) > 0
                 THEN 'availability_report'
            ELSE      'rent_roll_derived'
        END AS occupancy_source
    FROM property p
    LEFT JOIN v_latest_snapshot ls
         ON  ls.property_id = p.property_id
         AND ls.report_type = 'rent_roll'
    LEFT JOIN avail a  ON a.property_id = p.property_id
    LEFT JOIN rr       ON rr.property_id = p.property_id
),
selected AS (
    SELECT
        property_id, property_code, property_name, property_type, as_of_date,
        occupancy_source,
        total_units, non_revenue_units, unclassified_units,
        CASE occupancy_source
            WHEN 'availability_report' THEN av_occupied
            ELSE                            rr_occupied
        END AS occupied_units,
        CASE occupancy_source
            WHEN 'availability_report' THEN av_notice
            ELSE                            rr_notice
        END AS notice_units,
        CASE occupancy_source
            WHEN 'availability_report' THEN av_vacant
            ELSE                            rr_vacant
        END AS vacant_units,
        -- Denominator source matches numerator source.
        CASE occupancy_source
            WHEN 'availability_report'
                 THEN (total_units - non_revenue_units - unclassified_units)
            ELSE      (rr_occupied + rr_notice + rr_vacant)
        END AS rentable_units
    FROM combined
)
SELECT
    property_id, property_code, property_name, property_type, as_of_date,
    occupancy_source,
    total_units, non_revenue_units, unclassified_units, rentable_units,
    occupied_units, notice_units, vacant_units,
    CASE WHEN rentable_units > 0
         THEN ROUND(occupied_units::numeric / rentable_units::numeric, 4)
         ELSE NULL
    END AS pct_occupied,
    CASE WHEN rentable_units > 0
         THEN ROUND((occupied_units + notice_units)::numeric
                    / rentable_units::numeric, 4)
         ELSE NULL
    END AS pct_occupied_with_notice
FROM selected;

COMMENT ON VIEW v_occupancy_by_property IS
  'Occupancy per property with occupancy_source. Availability wins where '
  'states_reconcile AND total_units>0; rent roll fills the gap otherwise.';


-- ─── LOSS TO LEASE ────────────────────────────────────────────────────────

-- Market vs actual base rent per property. Residential + affordable only:
-- commercial market_rent is 0 in the source, land/management have no
-- leases. Loss-to-lease on regulated affordable housing has a slightly
-- different meaning (regulatory caps, not market forces) but the math is
-- valid; the dashboard can split them visually.
CREATE OR REPLACE VIEW v_loss_to_lease AS
SELECT
    property_id, property_code, property_name, property_type, as_of_date,
    COUNT(*)             AS units_in_scope,
    SUM(market_rent)     AS market_rent_total,
    SUM(base_rent_actual) AS effective_rent_total,
    SUM(market_rent - base_rent_actual) AS loss_to_lease,
    CASE WHEN SUM(market_rent) > 0
         THEN ROUND(SUM(market_rent - base_rent_actual)::numeric
                    / SUM(market_rent)::numeric, 4)
         ELSE NULL
    END AS pct_loss_to_lease
FROM v_lease_detail
WHERE property_type IN ('residential', 'affordable')
  AND lease_status IN ('current', 'notice')
  AND market_rent > 0
GROUP BY property_id, property_code, property_name, property_type, as_of_date;

COMMENT ON VIEW v_loss_to_lease IS
  'Market vs effective base rent per property (residential + affordable).';


-- ─── DELINQUENCY ──────────────────────────────────────────────────────────

-- One row per property with active leases. Balance > 0 means owed money.
-- The source data has no aging buckets, so we cannot age balances.
CREATE OR REPLACE VIEW v_delinquency_by_property AS
SELECT
    property_id, property_code, property_name, property_type, as_of_date,
    COUNT(*)                                AS n_active_leases,
    COUNT(*) FILTER (WHERE balance > 0)     AS n_delinquent_leases,
    COALESCE(SUM(balance) FILTER (WHERE balance > 0), 0) AS total_balance_owed,
    ROUND(
        COUNT(*) FILTER (WHERE balance > 0)::numeric / COUNT(*)::numeric,
        4
    ) AS pct_leases_delinquent,
    COALESCE(MAX(balance) FILTER (WHERE balance > 0), 0) AS max_balance,
    CASE WHEN COUNT(*) FILTER (WHERE balance > 0) > 0
         THEN ROUND(
                (SUM(balance) FILTER (WHERE balance > 0))::numeric
                / COUNT(*) FILTER (WHERE balance > 0)::numeric,
                2)
         ELSE 0
    END AS avg_delinquent_balance
FROM v_lease_detail
WHERE lease_status IN ('current', 'notice')
GROUP BY property_id, property_code, property_name, property_type, as_of_date;

COMMENT ON VIEW v_delinquency_by_property IS
  'Delinquency rollup per property (current + notice leases only). '
  'No aging buckets: the source data does not carry them.';


-- ─── CHARGE MIX ────────────────────────────────────────────────────────────

-- One row per (property, category). pct_of_property_gross uses ABS in the
-- denominator so concessions (negative amounts) show up as a share of
-- gross revenue rather than netting against it.
CREATE OR REPLACE VIEW v_charge_mix_by_property AS
WITH by_cat AS (
    SELECT
        p.property_id, p.property_code, p.property_name, p.property_type,
        ls.as_of_date,
        cc.category,
        SUM(lc.amount) AS sum_amount,
        COUNT(*)       AS n_charges
    FROM lease_charge lc
    JOIN lease   l  ON l.lease_id     = lc.lease_id
    JOIN v_latest_snapshot ls
         ON  ls.snapshot_id = l.snapshot_id
         AND ls.report_type = 'rent_roll'
    JOIN unit     u  ON u.unit_id     = l.unit_id
    JOIN property p  ON p.property_id = u.property_id
    JOIN charge_code cc ON cc.charge_code = lc.charge_code
    WHERE l.section = 'current'
    GROUP BY p.property_id, p.property_code, p.property_name, p.property_type,
             ls.as_of_date, cc.category
),
totals AS (
    SELECT property_id, SUM(ABS(sum_amount)) AS gross_total
    FROM by_cat
    GROUP BY property_id
)
SELECT
    bc.property_id, bc.property_code, bc.property_name, bc.property_type,
    bc.as_of_date, bc.category, bc.sum_amount, bc.n_charges,
    CASE WHEN t.gross_total > 0
         THEN ROUND(ABS(bc.sum_amount)::numeric / t.gross_total::numeric, 4)
         ELSE NULL
    END AS pct_of_property_gross
FROM by_cat bc
JOIN totals t ON t.property_id = bc.property_id;

COMMENT ON VIEW v_charge_mix_by_property IS
  'Revenue mix by charge category, per property. ABS() in the denominator '
  'so concessions show as share of gross, not net.';


-- ─── EXPIRATIONS ──────────────────────────────────────────────────────────

-- Long form. Month-to-month leases (no lease_expiration date) are excluded
-- here and can be surfaced as a separate KPI in the dashboard.
CREATE OR REPLACE VIEW v_expirations_by_month AS
SELECT
    property_id, property_code, property_name, property_type, as_of_date,
    DATE_TRUNC('month', lease_expiration)::date AS expiration_month,
    COUNT(*)                              AS n_leases_expiring,
    COALESCE(SUM(market_rent), 0)         AS market_rent_expiring,
    COALESCE(SUM(base_rent_actual), 0)    AS base_rent_expiring
FROM v_lease_detail
WHERE lease_status IN ('current', 'notice')
  AND lease_expiration IS NOT NULL
GROUP BY property_id, property_code, property_name, property_type, as_of_date,
         DATE_TRUNC('month', lease_expiration)::date;

COMMENT ON VIEW v_expirations_by_month IS
  'Long-form lease expiration schedule. One row per (property, month). '
  'Month-to-month leases (NULL lease_expiration) excluded.';


-- ─── PORTFOLIO ROLLUP ─────────────────────────────────────────────────────

-- One row per property_type. Occupancy is weighted by rentable_units within
-- the type -- never blended across types.
CREATE OR REPLACE VIEW v_portfolio_summary_by_type AS
WITH occ AS (
    SELECT
        property_type,
        COUNT(*)                    AS n_properties,
        SUM(total_units)            AS total_units,
        SUM(non_revenue_units)      AS non_revenue_units,
        SUM(unclassified_units)     AS unclassified_units,
        SUM(rentable_units)         AS total_rentable_units,
        SUM(occupied_units)         AS total_occupied_units,
        SUM(notice_units)           AS total_notice_units,
        SUM(vacant_units)           AS total_vacant_units
    FROM v_occupancy_by_property
    GROUP BY property_type
),
leases AS (
    SELECT
        property_type,
        COUNT(*) FILTER (WHERE lease_status = 'current') AS n_leases_current,
        COUNT(*) FILTER (WHERE lease_status = 'notice')  AS n_leases_notice,
        COUNT(*) FILTER (WHERE lease_status = 'vacant')  AS n_leases_vacant,
        COALESCE(SUM(market_rent) FILTER
                 (WHERE lease_status IN ('current','notice')), 0) AS total_market_rent,
        COALESCE(SUM(base_rent_actual) FILTER
                 (WHERE lease_status IN ('current','notice')), 0) AS total_base_rent
    FROM v_lease_detail
    GROUP BY property_type
)
SELECT
    o.property_type,
    o.n_properties,
    o.total_units,
    o.non_revenue_units,
    o.unclassified_units,
    o.total_rentable_units,
    o.total_occupied_units,
    o.total_notice_units,
    o.total_vacant_units,
    COALESCE(l.n_leases_current, 0) AS n_leases_current,
    COALESCE(l.n_leases_notice,  0) AS n_leases_notice,
    COALESCE(l.n_leases_vacant,  0) AS n_leases_vacant,
    COALESCE(l.total_market_rent, 0) AS total_market_rent,
    COALESCE(l.total_base_rent,   0) AS total_base_rent,
    CASE WHEN o.total_rentable_units > 0
         THEN ROUND(o.total_occupied_units::numeric
                    / o.total_rentable_units::numeric, 4)
         ELSE NULL
    END AS pct_occupied
FROM occ o
LEFT JOIN leases l ON l.property_type = o.property_type
ORDER BY o.property_type;

COMMENT ON VIEW v_portfolio_summary_by_type IS
  'Portfolio KPIs grouped by property_type. Ratios never blend across types.';


-- ─── DATA QUALITY ─────────────────────────────────────────────────────────

-- Long-form metric_name / value pairs. The panel that surfaces this on the
-- dashboard is a design rule: unclassified_units, ingest_error, and
-- ingest_audit exist to be displayed.
--
-- value is text so counts and timestamps live in the same column; the
-- dashboard can cast per row.
CREATE OR REPLACE VIEW v_data_quality_summary AS
SELECT 'n_source_files_loaded'      AS metric_name, count(*)::text AS value FROM source_file
UNION ALL SELECT 'n_snapshots',         count(*)::text FROM report_snapshot
UNION ALL SELECT 'n_properties',        count(*)::text FROM property
UNION ALL SELECT 'n_units',             count(*)::text FROM unit
UNION ALL SELECT 'n_residents',         count(*)::text FROM resident
UNION ALL SELECT 'n_leases',            count(*)::text FROM lease
UNION ALL SELECT 'n_charges',           count(*)::text FROM lease_charge
UNION ALL SELECT 'audits_lease_total_pass',
       count(*)::text FROM ingest_audit WHERE check_name = 'lease_total' AND     passed
UNION ALL SELECT 'audits_lease_total_fail',
       count(*)::text FROM ingest_audit WHERE check_name = 'lease_total' AND NOT passed
UNION ALL SELECT 'audits_charge_code_pass',
       count(*)::text FROM ingest_audit WHERE check_name = 'charge_code' AND     passed
UNION ALL SELECT 'audits_charge_code_fail',
       count(*)::text FROM ingest_audit WHERE check_name = 'charge_code' AND NOT passed
UNION ALL SELECT 'audits_lease_v_units_pass',
       count(*)::text FROM ingest_audit WHERE check_name = 'lease_v_units' AND     passed
UNION ALL SELECT 'audits_lease_v_units_fail',
       count(*)::text FROM ingest_audit WHERE check_name = 'lease_v_units' AND NOT passed
UNION ALL SELECT 'n_ingest_errors',     count(*)::text FROM ingest_error
UNION ALL SELECT 'n_unclassified_units',
       COALESCE(SUM(unclassified_units), 0)::text FROM property_availability
UNION ALL SELECT 'last_load_at',
       COALESCE(MAX(ingested_at)::text, '-') FROM source_file;

COMMENT ON VIEW v_data_quality_summary IS
  'Long-form metric_name/value pairs for the dashboard data-quality panel.';


-- ─── GRANTS ────────────────────────────────────────────────────────────────

-- The agent's read-only role needs to see every gold view. Migration 003
-- set default privileges but that only fires for tables created by the
-- same role after that migration; being explicit here is one line per view
-- and makes the security surface auditable.
GRANT SELECT ON v_latest_snapshot           TO rri_readonly;
GRANT SELECT ON v_lease_detail              TO rri_readonly;
GRANT SELECT ON v_occupancy_by_property     TO rri_readonly;
GRANT SELECT ON v_loss_to_lease             TO rri_readonly;
GRANT SELECT ON v_delinquency_by_property   TO rri_readonly;
GRANT SELECT ON v_charge_mix_by_property    TO rri_readonly;
GRANT SELECT ON v_expirations_by_month      TO rri_readonly;
GRANT SELECT ON v_portfolio_summary_by_type TO rri_readonly;
GRANT SELECT ON v_data_quality_summary      TO rri_readonly;
