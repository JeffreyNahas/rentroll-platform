// Charts, drawn rather than imported.
//
// These replaced Tremor. A stock chart library inside a committed world is a
// lapse — its rounded cards, its default blue and its own type scale drag a
// second design system onto the sheet. Every mark here is CSS or SVG, every
// hover is CSS, and none of it ships client JavaScript.
//
// Palette discipline (see globals.css for the validator run): six series inks
// that pass CVD separation on this surface, in fixed order, never cycled.
// Ochre sits below 3:1 against the sheet, so anything using it carries direct
// labels and a table view.

import { count, money, pct } from "@/lib/format";
import { GlyphTypeKey } from "./Glyph";

/* ==========================================================================
   Occupancy by property type
   --------------------------------------------------------------------------
   One measure across five types, so it is a single series: no legend, no
   second color. The notice line rides as a reference tick on the same bar
   instead of becoming a second bar — "occupied" and "occupied including
   notice" are the same quantity at two thresholds, and two bars would imply
   they are separate things.

   There is deliberately no portfolio-wide bar. Averaging a 775-unit complex
   with a 3-unit retail strip is the exact number this product refuses to
   produce, and its absence is the point.
   ========================================================================== */

export function OccupancyByType({
  rows,
}: {
  rows: {
    type: string;
    occupied: number;
    rentable: number;
    withNotice: number;
    properties: number;
  }[];
}) {
  return (
    <div className="space-y-3.5">
      {rows.map((r) => {
        const p = r.rentable > 0 ? r.occupied / r.rentable : 0;
        const pn = r.rentable > 0 ? r.withNotice / r.rentable : 0;
        return (
          <div
            key={r.type}
            className="grid grid-cols-[7.5rem_1fr] items-center gap-3"
          >
            <div className="min-w-0">
              <div className="letter text-ink truncate">{r.type}</div>
              <div className="text-ink-3 mt-0.5 font-mono text-[0.6875rem]">
                {r.properties} {r.properties === 1 ? "property" : "properties"}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <span className="tip relative block h-7 flex-1" tabIndex={0}>
                <span className="bg-rule/35 absolute inset-0 block" />
                {/* notice threshold — a reference tick, not a second series */}
                <span
                  className="bg-ink-2 absolute top-0 bottom-0 z-10 block w-px"
                  style={{ left: `${pn * 100}%` }}
                  aria-hidden="true"
                />
                <span
                  className="mark absolute inset-y-0 left-0 block bg-green-700"
                  style={{ width: `${p * 100}%` }}
                />
                <span className="tip-body">
                  {count(r.occupied)} of {count(r.rentable)} rentable ·{" "}
                  {count(r.withNotice - r.occupied)} on notice
                </span>
              </span>
              <span className="fig text-ink w-14 shrink-0 text-right font-mono text-[0.8125rem] font-medium">
                {pct(p)}
              </span>
            </div>
          </div>
        );
      })}

      <p className="text-ink-3 border-rule mt-1 border-t pt-3 text-[0.75rem] leading-relaxed">
        The hairline on each bar marks occupancy including units on notice.
      </p>
    </div>
  );
}

/* ==========================================================================
   Lease expirations — next 12 months, segmented by property type
   --------------------------------------------------------------------------
   Segmented rather than one green series, because "when does the portfolio
   turn over" and "which kind of property is turning over" are the same
   question here: a commercial renewal and a 300-unit residential renewal are
   different work, and a single-hue column hides that.

   Type identity stays keyed by hatch — the legend swatch is the same drawn
   pattern used everywhere else, tinted in its series ink. Texture leads; the
   ink is the second channel that makes segments separable at column width.

   Stack order validated all-pairs on the shipped surface:
     node scripts/validate_palette.js "#1F5FA9,#00938A,#D2601A" \
       --mode light --surface "#f4f2e9" --pairs all
   → all pass; worst all-pairs CVD ΔE 14.0, normal-vision ΔE 17.5, all >=3:1.
   ========================================================================== */

const TYPE_INK: Record<string, string> = {
  residential: "var(--color-s1)",
  affordable: "var(--color-s3)",
  commercial: "var(--color-s2)",
  land: "var(--color-s5)",
  other: "var(--color-s-other)",
};

export function typeInk(t: string): string {
  return TYPE_INK[t] ?? "var(--color-s-other)";
}

export function ExpirationSchedule({
  rows,
  types,
}: {
  rows: {
    month: string;
    total: number;
    segments: { type: string; leases: number }[];
  }[];
  types: string[];
}) {
  const max = Math.max(...rows.map((r) => r.total), 1);

  if (rows.length === 0) {
    return (
      <p className="text-ink-3 text-[0.8125rem]">
        No leases expire in the next twelve months.
      </p>
    );
  }

  // "Mar 2027" → month on the tick, year only where it changes. Repeating the
  // year under all twelve columns pushed the axis 230px past a phone viewport
  // and told the reader nothing they could not already see.
  const parsedMonths = rows.map((r) => {
    const [mon, year] = r.month.split(/\s+/);
    return { mon, year };
  });
  const ticks = parsedMonths.map((p, i) => ({
    mon: p.mon,
    year: i === 0 || p.year !== parsedMonths[i - 1].year ? p.year : null,
  }));

  return (
    <div>
      {/* Two or more series always carry a legend; identity is never
          color-alone. */}
      <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2">
        {types.map((t) => (
          <span key={t} className="inline-flex items-center gap-1.5">
            <span style={{ color: typeInk(t) }}>
              <GlyphTypeKey type={t} />
            </span>
            <span className="letter">{t}</span>
          </span>
        ))}
      </div>

      <div className="-mx-1 overflow-x-auto px-1">
        <div className="min-w-[21rem]">
          <div className="flex h-52 items-end gap-1.5">
            {rows.map((r) => (
              <div
                key={r.month}
                className="flex h-full flex-1 flex-col items-center justify-end gap-1.5"
              >
                <span className="fig text-ink-2 font-mono text-[0.6875rem]">
                  {r.total}
                </span>
                <div
                  className="flex w-full flex-col justify-end gap-px"
                  style={{ height: `${(r.total / max) * 100}%` }}
                >
                  {r.segments.map((sg, i) => (
                    <span
                      key={sg.type}
                      className="tip flex w-full justify-center"
                      style={{
                        height: `${(sg.leases / r.total) * 100}%`,
                        // A legend that declares a key you cannot see is a
                        // legend that lies. Commercial is 1-2px of a 208px
                        // column at true proportion; a 3px floor costs about
                        // one percentage point of accuracy and buys the third
                        // key its existence. Exact counts stay in the tooltip.
                        minHeight: sg.leases > 0 ? "3px" : undefined,
                      }}
                      tabIndex={0}
                    >
                      <span
                        className={`block w-full ${i === 0 ? "mark-v" : ""}`}
                        style={{ background: typeInk(sg.type) }}
                      />
                      <span className="tip-body">
                        {r.month} · {sg.type} · {count(sg.leases)} leases
                      </span>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="border-rule-strong mt-2 flex gap-1.5 border-t pt-2">
            {ticks.map((t, i) => (
              <div key={rows[i].month} className="min-w-0 flex-1 text-center">
                <div className="letter text-[0.5625rem] tracking-[0.03em]">
                  {t.mon}
                </div>
                {t.year && (
                  <div className="text-ink-3 mt-0.5 font-mono text-[0.625rem]">
                    {t.year}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ==========================================================================
   Charge mix
   --------------------------------------------------------------------------
   Part-to-whole across eight categories where base rent is ~90% of the total.
   That is the case a donut handles worst: seven near-identical slivers around
   one dominant arc, none of them readable. A horizontal stacked bar keeps the
   proportion honest and lets the seven minor categories be compared against
   each other, which is the only interesting question here.
   Base rent takes graphite rather than a series ink — it is the baseline the
   others are read against, and giving 90% of the bar a saturated hue would
   drown the part that carries the information.
   ========================================================================== */

const CATEGORY_INK: Record<string, string> = {
  base_rent: "var(--color-s-anchor)",
  utility: "var(--color-s1)",
  fee: "var(--color-s2)",
  amenity: "var(--color-s3)",
  recovery: "var(--color-s4)",
  subsidy: "var(--color-s5)",
  concession: "var(--color-s6)",
  other: "var(--color-s-other)",
};

export function categoryInk(c: string): string {
  return CATEGORY_INK[c] ?? "var(--color-s-other)";
}

export function ChargeMixBar({
  rows,
}: {
  rows: { category: string; amount: number; share: number | null }[];
}) {
  const total = rows.reduce((a, r) => a + Math.abs(r.amount), 0);
  if (total === 0) {
    return (
      <p className="text-ink-3 text-[0.8125rem]">
        No charges recorded for this property.
      </p>
    );
  }

  const sorted = [...rows].sort(
    (a, b) => Math.abs(b.amount) - Math.abs(a.amount)
  );

  // One category means one full-width slab, which reads as a redaction bar
  // and says nothing the "100.0%" row below does not. The bar earns its place
  // only where there is a proportion to see.
  const showBar = sorted.length > 1;

  return (
    <div>
      {/* 2px surface gaps between adjacent fills keep the segments legible
          where two inks meet. */}
      <div className={`flex h-9 w-full gap-0.5 ${showBar ? "" : "hidden"}`}>
        {sorted.map((r) => {
          const share = Math.abs(r.amount) / total;
          return (
            <span
              key={r.category}
              className="tip relative block min-w-[2px]"
              style={{
                width: `${share * 100}%`,
                background: categoryInk(r.category),
              }}
              tabIndex={0}
            >
              <span className="tip-body">
                {r.category.replace(/_/g, " ")} · {money(r.amount)} ·{" "}
                {pct(share)}
              </span>
            </span>
          );
        })}
      </div>

      {/* The table view. Not an afterthought: ochre sits below 3:1 on this
          surface, and the validator's relief rule makes a readable table
          mandatory rather than optional. */}
      <table className={`schedule ${showBar ? "mt-5" : ""}`}>
        <thead>
          <tr>
            <th>Category</th>
            <th className="text-right">Amount</th>
            <th className="text-right">Share</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.category}>
              <td>
                <span className="flex items-center gap-2">
                  <span
                    className="inline-block size-2.5 shrink-0"
                    style={{ background: categoryInk(r.category) }}
                    aria-hidden="true"
                  />
                  <span className="text-ink">
                    {r.category.replace(/_/g, " ")}
                  </span>
                </span>
              </td>
              <td className="num">{money(r.amount)}</td>
              <td className="num text-ink-3">
                {pct(Math.abs(r.amount) / total)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="text-ink-3 mt-3 text-[0.75rem] leading-relaxed">
        Shares are of gross billed charges, so credits (concessions, subsidy
        offsets) count by magnitude rather than netting against rent.
      </p>
    </div>
  );
}
