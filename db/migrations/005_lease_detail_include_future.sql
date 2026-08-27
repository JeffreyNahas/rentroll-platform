-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 005: expose future applicants through v_lease_detail.
--
-- Migration 004 hardcoded `WHERE l.section = 'current'` inside the view, so
-- future applicants (93 portfolio-wide) were unreachable through the API.
-- The presentation layer needs to serve them via ?section=future without
-- adding a second view for the same shape.
--
-- Safety: every downstream view (v_loss_to_lease, v_delinquency_by_property,
-- v_expirations_by_month, v_portfolio_summary_by_type) filters on
-- `lease_status IN ('current', 'notice')` which already excludes 'future'.
-- Removing the section filter here is a strict superset of what those views
-- see today; they cannot regress.
--
-- CREATE OR REPLACE VIEW works because the column list is unchanged --
-- only the WHERE clause is removed.
-- ═══════════════════════════════════════════════════════════════════════════

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
LEFT JOIN base_rent br ON br.lease_id     = l.lease_id;
-- No section filter: callers filter via l.section (or l.lease_status)
-- according to what they want to see. Future applicants land as
-- section = 'future', lease_status = 'future'.

COMMENT ON VIEW v_lease_detail IS
  'One row per lease at the latest rent-roll snapshot -- current section '
  '(current/notice/vacant) plus future applicants. Callers must filter '
  'by l.section or l.lease_status as appropriate.';

GRANT SELECT ON v_lease_detail TO rri_readonly;
