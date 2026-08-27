"use client";

// Client only because it owns the current/future section toggle. Data still
// arrives from the server as a prop; toggling updates the URL and the page
// re-renders server-side against the new section, so there is still no
// client-side data fetching anywhere in this app.

import { useRouter, useSearchParams } from "next/navigation";
import type { LeaseRow } from "@/lib/types";
import { count, dateLabel, money } from "@/lib/format";
import { GlyphState } from "@/components/sheet/Glyph";

type LeaseState = "current" | "notice" | "vacant" | "future";

// Lease status is a mark in a fixed cell, not a colored pill. The glyph
// carries the state; where a color appears it only confirms it.
const STATUS: Record<LeaseState, { tone: string; title: string }> = {
  current: { tone: "text-ink", title: "Occupied" },
  notice: { tone: "text-amber", title: "On notice — still occupied" },
  vacant: { tone: "text-ink-3", title: "Vacant" },
  future: { tone: "text-green-700", title: "Signed, not moved in" },
};

export function LeasesTable({
  rows,
  section,
  pagination,
  code,
}: {
  rows: LeaseRow[];
  section: "current" | "future";
  pagination: { limit: number; offset: number; total: number };
  code: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  function pick(newSection: "current" | "future") {
    const params = new URLSearchParams(searchParams.toString());
    params.set("section", newSection);
    params.delete("offset");
    router.push(`/properties/${code}?${params.toString()}`);
  }

  function go(offset: number) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("section", section);
    params.set("offset", String(offset));
    router.push(`/properties/${code}?${params.toString()}`);
  }

  const { limit, offset, total } = pagination;
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + limit, total);
  const hasPages = total > limit;

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div
          className="border-rule-strong divide-rule flex divide-x border"
          role="group"
          aria-label="Lease section"
        >
          {(["current", "future"] as const).map((s) => (
            <button
              key={s}
              onClick={() => pick(s)}
              aria-pressed={section === s}
              className={`letter px-3.5 py-2 transition-colors ${
                section === s
                  ? "bg-green-700 text-green-50"
                  : "text-ink-3 hover:text-ink hover:bg-green-50"
              }`}
            >
              {s === "current" ? "Current section" : "Future applicants"}
            </button>
          ))}
        </div>

        <p className="text-ink-3 text-[0.75rem]">
          {count(first)}–{count(last)} of {count(total)}. Resident names are
          masked at the API.
        </p>
      </div>

      {rows.length === 0 ? (
        <p className="text-ink-3 border-rule border-t pt-4 text-[0.8125rem]">
          {section === "future"
            ? "No future applicants on this property."
            : "No leases in the current section."}
        </p>
      ) : (
        <div className="-mx-1 overflow-x-auto px-1">
          <table className="schedule min-w-[58rem]">
            <thead>
              <tr>
                <th>Unit</th>
                <th>Plan</th>
                <th>Resident</th>
                <th>State</th>
                <th className="text-right">Market</th>
                <th className="text-right">Base rent</th>
                <th className="text-right">Balance</th>
                <th>Move-in</th>
                <th>Expires</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const state = (
                  r.lease_status in STATUS ? r.lease_status : "vacant"
                ) as LeaseState;
                const st = STATUS[state];
                const owing = r.balance != null && r.balance > 0;
                return (
                  <tr key={r.lease_id}>
                    <td className="text-ink font-mono text-[0.8125rem]">
                      {r.unit_number}
                    </td>
                    <td className="text-ink-3 font-mono text-[0.6875rem]">
                      {r.unit_type_code ?? "—"}
                    </td>
                    <td className="text-ink-2">{r.display_name ?? "—"}</td>
                    <td>
                      <span
                        className={`inline-flex items-center gap-1.5 whitespace-nowrap ${st.tone}`}
                        title={st.title}
                      >
                        <GlyphState state={state} />
                        <span className="letter text-current">
                          {r.lease_status}
                        </span>
                      </span>
                    </td>
                    <td className="num text-ink-3">
                      {money(r.market_rent, 0)}
                    </td>
                    <td className="num text-ink">
                      {money(r.base_rent_actual, 0)}
                    </td>
                    <td
                      className={`num ${owing ? "text-redline" : "text-ink-3"}`}
                    >
                      {money(r.balance, 0)}
                    </td>
                    <td className="num text-ink-3">
                      {dateLabel(r.move_in_date)}
                    </td>
                    <td className="num text-ink-3">
                      {dateLabel(r.lease_expiration)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* A table that says "100 of 300" and offers no way to the other 200 is
          a truncation, not a page. The API already takes limit/offset. */}
      {hasPages && (
        <nav
          className="border-rule mt-4 flex items-center justify-between border-t pt-3"
          aria-label="Lease pages"
        >
          <button
            onClick={() => go(Math.max(offset - limit, 0))}
            disabled={offset === 0}
            className="letter border-rule-strong text-ink-3 hover:text-ink border px-3 py-1.5 transition-colors hover:bg-green-50 disabled:pointer-events-none disabled:opacity-40"
          >
            Previous
          </button>
          <span className="letter">
            Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}
          </span>
          <button
            onClick={() => go(offset + limit)}
            disabled={last >= total}
            className="letter border-rule-strong text-ink-3 hover:text-ink border px-3 py-1.5 transition-colors hover:bg-green-50 disabled:pointer-events-none disabled:opacity-40"
          >
            Next
          </button>
        </nav>
      )}
    </>
  );
}
