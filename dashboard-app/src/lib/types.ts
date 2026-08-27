// Row shapes mirror the columns of the gold views. If the API adds a
// field, TypeScript flags a compile error until the row type is updated.
// Source of truth: db/migrations/004_gold_views.sql and docs/api.md.

export type PropertyType =
  "residential" | "affordable" | "commercial" | "land" | "other";

export type OccupancySource = "availability_report" | "rent_roll_derived";

export type ReportType = "rent_roll" | "unit_availability";

export type Source = {
  snapshot_id: number;
  property_code: string;
  report_type: ReportType;
  filename: string;
  as_of_date: string;
};

export type ApiWarning = {
  code: string;
  message: string;
};

export type ApiResponse<T> = {
  data: T[];
  sources: Source[] | null;
  row_count: number;
  query_time_ms: number;
  warnings: ApiWarning[];
};

export type PortfolioSummaryRow = {
  property_type: PropertyType;
  n_properties: number;
  total_units: number;
  non_revenue_units: number;
  unclassified_units: number;
  total_rentable_units: number;
  total_occupied_units: number;
  total_notice_units: number;
  total_vacant_units: number;
  n_leases_current: number;
  n_leases_notice: number;
  n_leases_vacant: number;
  total_market_rent: number;
  total_base_rent: number;
  pct_occupied: number | null;
};

export type OccupancyRow = {
  property_id: number;
  property_code: string;
  property_name: string;
  property_type: PropertyType;
  as_of_date: string;
  occupancy_source: OccupancySource;
  total_units: number;
  non_revenue_units: number;
  unclassified_units: number;
  rentable_units: number;
  occupied_units: number;
  notice_units: number;
  vacant_units: number;
  pct_occupied: number | null;
  pct_occupied_with_notice: number | null;
};

export type ChargeMixRow = {
  category: string;
  sum_amount: number;
  n_charges: number;
  pct_of_property_gross: number | null;
};

export type DelinquencyRow = {
  property_code: string;
  property_name: string;
  property_type: PropertyType;
  n_active_leases: number;
  n_delinquent_leases: number;
  total_balance_owed: number;
  pct_leases_delinquent: number | null;
  max_balance: number;
  avg_delinquent_balance: number;
};

export type LossToLeaseRow = {
  property_code: string;
  property_name: string;
  property_type: PropertyType;
  units_in_scope: number;
  market_rent_total: number;
  effective_rent_total: number;
  loss_to_lease: number;
  pct_loss_to_lease: number | null;
};

export type ExpirationRow = {
  property_code: string;
  property_name: string;
  property_type: PropertyType;
  expiration_month: string;
  n_leases_expiring: number;
  market_rent_expiring: number;
  base_rent_expiring: number;
};

export type LeaseRow = {
  lease_id: number;
  unit_number: string;
  unit_type_code: string | null;
  square_feet: number | null;
  resident_id: number | null;
  display_name: string | null;
  section: "current" | "future";
  lease_status: "current" | "notice" | "vacant" | "future";
  market_rent: number | null;
  base_rent_actual: number;
  balance: number | null;
  move_in_date: string | null;
  lease_expiration: string | null;
  move_out_date: string | null;
};

export type DataQualityFailure = {
  check_name: "charge_code" | "lease_v_units" | "unclassified_units";
  property_code: string;
  property_name: string;
  property_type: PropertyType;
  subject: string;
  expected: number | null;
  actual: number | null;
  delta: number | null;
  note: string;
};

export type PropertyRef = {
  property_id: number;
  property_code: string;
  property_name: string;
  property_type: PropertyType;
};

// /properties/{code} returns a single row whose `data[0]` bundles four
// sub-objects together. Nulls are legitimate (loss_to_lease is null for
// commercial and land/other).
export type PropertyDetail = {
  occupancy: OccupancyRow;
  charge_mix: ChargeMixRow[];
  delinquency: Omit<
    DelinquencyRow,
    "property_code" | "property_name" | "property_type"
  > | null;
  loss_to_lease: Omit<
    LossToLeaseRow,
    "property_code" | "property_name" | "property_type"
  > | null;
};

// Paginated leases endpoint attaches an extra pagination block.
export type LeasesResponse = ApiResponse<LeaseRow> & {
  pagination: {
    limit: number;
    offset: number;
    total: number;
    section: "current" | "future";
  };
};

// POST /agent/ask. `sources`/`warnings` are the de-duplicated union of
// every tool call's own envelope fields for the turn — the agent doesn't
// invent its own citation shape, it reuses the API's.
export type AgentMessage = {
  role: "user" | "assistant";
  content: string;
};

export type AgentToolCall = {
  tool: string;
  input: Record<string, unknown>;
  latency_ms: number;
};

export type AgentAskResponse = {
  answer: string;
  sources: Source[];
  warnings: ApiWarning[];
  tool_calls: AgentToolCall[];
};
