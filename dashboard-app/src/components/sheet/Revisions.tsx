// The revision margin.
//
// A drawing sheet keeps its deviations in a numbered table in the margin,
// where a reader meets them before they meet the drawing — not hidden at the
// bottom. Rule #6 says surface data problems rather than hide them; this is
// that rule as a piece of the sheet's anatomy instead of a panel appended to
// the end of the page.
//
// Each entry carries the note the API wrote, verbatim. The API is where the
// explanation belongs; the dashboard's job is to make sure it is read.

import type { ApiWarning, DataQualityFailure } from "@/lib/types";
import { GlyphDeviation, GlyphNote } from "./Glyph";

const CHECK_LABEL: Record<string, string> = {
  charge_code: "Charge summary",
  lease_v_units: "Cross-report",
  unclassified_units: "Unclassified",
};

export function RevisionMargin({
  failures,
}: {
  failures: DataQualityFailure[];
}) {
  return (
    <aside className="border-rule-strong bg-field/70 border">
      <div className="border-rule-strong text-redline flex items-center gap-2 border-b px-3.5 py-2.5">
        <GlyphDeviation />
        <span className="letter text-current">
          Deviations · {failures.length}
        </span>
      </div>

      {failures.length === 0 ? (
        <p className="text-ink-3 px-3.5 py-4 text-[0.8125rem] leading-relaxed">
          Every audit passed and no units are unclassified. Nothing to redline.
        </p>
      ) : (
        <ol className="divide-rule divide-y">
          {failures.map((f, i) => (
            <li key={`${f.check_name}-${f.property_code}-${f.subject}`}>
              <div className="flex gap-2.5 px-3.5 py-3">
                <span className="text-redline mt-px shrink-0">
                  <GlyphDeviation n={i + 1} />
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-ink font-mono text-[0.8125rem] font-medium">
                      {f.property_code}
                    </span>
                    <span className="letter">
                      {CHECK_LABEL[f.check_name] ?? f.check_name}
                    </span>
                    {f.delta != null && f.delta !== 0 && (
                      // Spelled out rather than "Δ": a delta symbol sitting
                      // beside the revision triangles read as a second mark
                      // in the same family and meant something different.
                      <span className="text-redline fig font-mono text-[0.75rem]">
                        off by{" "}
                        {f.delta.toLocaleString("en-US", {
                          maximumFractionDigits: 2,
                        })}
                      </span>
                    )}
                  </div>
                  <p className="text-ink-3 mt-1.5 text-[0.75rem] leading-relaxed">
                    {f.note}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}

/* --- Sheet notes ---------------------------------------------------------
   API envelope warnings. On a drawing these are the general notes: things
   true of the whole sheet that the drawing itself cannot show. */

export function SheetNotes({ warnings }: { warnings: ApiWarning[] }) {
  if (warnings.length === 0) return null;
  return (
    <div className="border-rule bg-amber-wash/50 border px-3.5 py-3">
      <div className="text-amber flex items-center gap-2">
        <GlyphNote />
        <span className="letter text-current">Notes · {warnings.length}</span>
      </div>
      <ul className="mt-2 space-y-1.5">
        {warnings.map((w, i) => (
          // `code` alone isn't guaranteed unique here: the agent can emit
          // two warnings with the same code but different messages (e.g.
          // occupancy_source_fallback from two differently-filtered
          // occupancy calls in one turn) — see agent/run.py's dedup,
          // which keys on (code, message), not code alone.
          <li
            key={`${w.code}-${i}`}
            className="text-ink-2 text-[0.8125rem] leading-relaxed"
          >
            <span className="text-ink-3 font-mono text-[0.6875rem]">
              {w.code}
            </span>{" "}
            — {w.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
