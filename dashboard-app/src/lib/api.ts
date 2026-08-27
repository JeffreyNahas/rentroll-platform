// Server-side fetch layer. FastAPI is trusted, sub-10ms per call, single
// user — no SWR / React Query. Every page fetches its own data. Response
// cached for 60s so a demo F5 doesn't re-hit the DB every time.

import type {
  AgentMessage,
  AgentStreamEvent,
  ApiResponse,
  DataQualityFailure,
  ExpirationRow,
  LeasesResponse,
  OccupancyRow,
  PortfolioSummaryRow,
  PropertyDetail,
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
};

// Called client-side from CommandDock — a live agent turn, not a cached
// page fetch, so it bypasses apiGet's revalidate wrapper. Streams
// progress (`tool_start`/`tool_done`/`status`/`error`) via `onEvent` as
// the agent works, terminating in exactly one `done` event carrying the
// full answer. No EventSource here — it can't send a POST body, so this
// parses Server-Sent Events by hand off `fetch`'s streaming body reader.
export async function askAgentStream(
  question: string,
  history: AgentMessage[],
  onEvent: (event: AgentStreamEvent) => void
): Promise<void> {
  const res = await fetch(`${API_URL}/agent/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  if (!res.ok || !res.body) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `API /agent/ask/stream → ${res.status} ${res.statusText}: ${body}`
    );
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });

    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      const rawEvent = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const dataLine = rawEvent
        .split("\n")
        .find((line) => line.startsWith("data: "));
      if (dataLine) {
        onEvent(
          JSON.parse(dataLine.slice("data: ".length)) as AgentStreamEvent
        );
      }
      sep = buffer.indexOf("\n\n");
    }
  }
}
