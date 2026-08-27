-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 006: portfolio-wide grand totals.
--
-- Motivation: the agent had no legitimate way to answer "how many units in
-- total" -- v_portfolio_summary_by_type is deliberately grouped by
-- property_type (rule #4: never blend metrics across types) with no
-- portfolio-wide row, so the model was reduced to summing five per-type
-- numbers itself. That's design rule #1's "never let the LLM compute a
-- number" violated in the most literal way, and the numeric grounding
-- check correctly failed the answer closed.
--
-- This view does in SQL exactly what the model was attempting to do by
-- hand: sum the per-type additive counts into one row. That's still safe
-- under rule #4 -- summing counts is not the same as averaging a ratio
-- across incommensurable property types, which is what the rule actually
-- forbids. No percentage/ratio column is exposed here on purpose: a
-- portfolio-wide occupancy % would be exactly that meaningless blended
-- number, and the dashboard's title block already refuses to show one
-- ("Counted, not averaged").
--
-- total_units vs total_rentable_units, both exposed deliberately: they are
-- not the same number and collapsing them into one would hide a real data
-- problem. total_units sums each property's raw availability-report count
-- (0 for 153c, whose availability report doesn't reconcile against its 7
-- rent-roll leases -- see docs/data_quality.md). total_rentable_units sums
-- the reconciled, source-matched figure v_occupancy_by_property already
-- computes per property (rule: denominator source matches numerator
-- source), which is 7 for 153c, not 0. Presenting only one of these would
-- either overstate revenue-producing capacity or silently undercount a
-- known-good property by 7 units.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_portfolio_totals AS
SELECT
    SUM(n_properties)          AS n_properties,
    SUM(total_units)           AS total_units,
    SUM(non_revenue_units)     AS non_revenue_units,
    SUM(unclassified_units)    AS unclassified_units,
    SUM(total_rentable_units)  AS total_rentable_units,
    SUM(total_occupied_units)  AS total_occupied_units,
    SUM(total_notice_units)    AS total_notice_units,
    SUM(total_vacant_units)    AS total_vacant_units,
    SUM(n_leases_current)      AS n_leases_current,
    SUM(n_leases_notice)       AS n_leases_notice,
    SUM(n_leases_vacant)       AS n_leases_vacant,
    SUM(total_market_rent)     AS total_market_rent,
    SUM(total_base_rent)       AS total_base_rent
FROM v_portfolio_summary_by_type;

COMMENT ON VIEW v_portfolio_totals IS
  'Portfolio-wide grand totals -- straight sums of v_portfolio_summary_by_type''s '
  'per-type additive counts, never a blended ratio (no occupancy % here; see rule #4). '
  'total_units (raw availability-report sum) and total_rentable_units (source-reconciled '
  'sum) routinely differ -- the net of many per-property effects, largest single '
  'contributor being the 153c gap documented in docs/data_quality.md.';

GRANT SELECT ON v_portfolio_totals TO rri_readonly;
