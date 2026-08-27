// Server-side fetch layer. FastAPI is trusted, sub-10ms per call, single
// user — no SWR / React Query. Every page fetches its own data. Response
// cached for 60s so a demo F5 doesn't re-hit the DB every time.

import type {
  AgentAskResponse,
  AgentMessage,
  ApiResponse,
  ChargeMixRow,
  DataQualityFailure,
  DelinquencyRow,
  ExpirationRow,
  LeasesResponse,
  LossToLeaseRow,
  OccupancyRow,
  PortfolioSummaryRow,
  PropertyDetail,
  PropertyRef,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    next: { revalidate: 60 },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${path} → ${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export const api = {
  portfolioSummary: () =>
    apiGet<ApiResponse<PortfolioSummaryRow>>("/portfolio/summary"),

  dataQualityFailures: () =>
    apiGet<ApiResponse<DataQualityFailure>>("/portfolio/data-quality/failures"),

  properties: () => apiGet<ApiResponse<PropertyRef>>("/properties"),

  propertyDetail: (code: string) =>
    apiGet<ApiResponse<PropertyDetail>>(`/properties/${code}`),

  propertyLeases: (
    code: string,
    section: "current" | "future" = "current",
    limit = 100,
    offset = 0
  ) =>
    apiGet<LeasesResponse>(
      `/properties/${code}/leases?section=${section}&limit=${limit}&offset=${offset}`
    ),

  occupancy: () => apiGet<ApiResponse<OccupancyRow>>("/occupancy"),

  expirations: (from?: string, to?: string) => {
    const qs = new URLSearchParams();
    if (from) qs.set("from", from);
    if (to) qs.set("to", to);
    const suffix = qs.toString() ? `?${qs}` : "";
    return apiGet<ApiResponse<ExpirationRow>>(`/expirations${suffix}`);
  },

  delinquency: () => apiGet<ApiResponse<DelinquencyRow>>("/delinquency"),

  chargeMix: () =>
    apiGet<
      ApiResponse<
        ChargeMixRow & { property_code: string; property_type: string }
      >
    >("/charge-mix"),

  lossToLease: () => apiGet<ApiResponse<LossToLeaseRow>>("/loss-to-lease"),
};

// Called client-side from CommandDock — a live agent turn, not a cached
// page fetch, so it bypasses apiGet's revalidate wrapper.
export async function askAgent(
  question: string,
  history: AgentMessage[] = []
): Promise<AgentAskResponse> {
  const res = await fetch(`${API_URL}/agent/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `API /agent/ask → ${res.status} ${res.statusText}: ${body}`
    );
  }
  return res.json();
}
