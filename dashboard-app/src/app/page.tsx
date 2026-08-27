// Sheet 1 — the portfolio.
//
// Reading order is deliberate and inverts the old page. Provenance and
// revision state arrive in the title block before any total; the schedule
// comes next because "which property should I look at" is the actual first
// question; the deviations sit in the margin alongside everything rather than
// waiting at the bottom of the scroll.

import Link from "next/link";
import { api } from "@/lib/api";
import { count, money, monthLabel, pct } from "@/lib/format";
import { TitleBlock, Field } from "@/components/sheet/TitleBlock";
import { Register, ScaleBar } from "@/components/sheet/Register";
import { RevisionMargin } from "@/components/sheet/Revisions";
import {
  SourceMark,
  SourcesMark,
  TypeKey,
  TypeLegend,
} from "@/components/sheet/Marks";
import { OccupancyByType, ExpirationSchedule } from "@/components/sheet/Charts";
import { GlyphIn } from "@/components/sheet/Glyph";
import { dateLabel } from "@/lib/format";

const TYPE_ORDER = ["residential", "affordable", "commercial", "land", "other"];

export default async function OverviewPage() {
  const [summary, failures, occupancy, expirations] = await Promise.all([
    api.portfolioSummary(),
    api.dataQualityFailures(),
    api.occupancy(),
    api.expirations(),
  ]);

  // Portfolio-wide figures that are safe to sum. There is deliberately no
  // portfolio occupancy percentage anywhere on this sheet: averaging a
  // 775-unit apartment complex with a 3-unit retail strip produces a number
  // that describes nothing (rule #4).
  const totalProperties = summary.data.reduce((a, r) => a + r.n_properties, 0);
  const totalUnits = summary.data.reduce((a, r) => a + r.total_units, 0);
  const totalRentable = summary.data.reduce(
    (a, r) => a + r.total_rentable_units,
    0
  );
  const totalOccupied = summary.data.reduce(
    (a, r) => a + r.total_occupied_units,
    0
  );
  const totalBaseRent = summary.data.reduce((a, r) => a + r.total_base_rent, 0);

  const occByType = TYPE_ORDER.map((t) =>
    summary.data.find((r) => r.property_type === t)
  )
    .filter(
      (r): r is NonNullable<typeof r> => !!r && r.total_rentable_units > 0
    )
    .map((r) => ({
      type: r.property_type,
      occupied: r.total_occupied_units,
      rentable: r.total_rentable_units,
      withNotice: r.total_occupied_units + r.total_notice_units,
      properties: r.n_properties,
    }));

  // Expirations for the next 12 months only; month-to-month leases have no
  // expiration date and are excluded upstream. Grouped by month AND property
  // type, because a commercial renewal and a 300-unit residential renewal are
  // different work and one flat column hides that.
  const now = new Date();
  const cutoff = new Date(now.getFullYear() + 1, now.getMonth(), 1);
  const byMonth = new Map<string, Map<string, number>>();
  for (const row of expirations.data) {
    const d = new Date(row.expiration_month);
    if (d < now || d > cutoff) continue;
    const m = byMonth.get(row.expiration_month) ?? new Map<string, number>();
    m.set(
      row.property_type,
      (m.get(row.property_type) ?? 0) + row.n_leases_expiring
    );
    byMonth.set(row.expiration_month, m);
  }
  const expByMonth = Array.from(byMonth.entries())
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([m, types]) => {
      // Stacked in the fixed type order, never in per-column magnitude order:
      // colour must follow the entity, so a type keeps its band position and
      // its ink in every column.
      const segments = TYPE_ORDER.filter((t) => (types.get(t) ?? 0) > 0).map(
        (t) => ({ type: t, leases: types.get(t)! })
      );
      return {
        month: monthLabel(m),
        total: segments.reduce((a, s) => a + s.leases, 0),
        segments,
      };
    });

  const expiringTypes = TYPE_ORDER.filter((t) =>
    expByMonth.some((r) => r.segments.some((s) => s.type === t))
  );

  const propertyRows = [...occupancy.data].sort(
    (a, b) => b.total_units - a.total_units
  );
  const maxUnits = Math.max(...propertyRows.map((p) => p.total_units), 1);
  const derivedCount = propertyRows.filter(
    (p) => p.occupancy_source === "rent_roll_derived"
  ).length;
  const asOf = summary.sources?.[0]?.as_of_date ?? null;
  const presentTypes = TYPE_ORDER.filter((t) =>
    propertyRows.some((p) => p.property_type === t)
  );

  return (
    <div className="space-y-8">
      {/* ---- Title block: what this sheet is, and what it was drawn from --- */}
      <TitleBlock cols="lg:grid-cols-4 xl:grid-cols-8">
        <Field label="Sheet" value="1 · Portfolio" note="Residents masked." />
        <Field
          label="Snapshot"
          value={asOf ? dateLabel(asOf) : "—"}
          note="One frozen snapshot; no prior period."
        />
        <Field
          label="Sources"
          value={`${summary.sources?.length ?? 0} files`}
        />
        <Field label="Properties" value={count(totalProperties)} />
        <Field label="Units" value={count(totalUnits)} />
        <Field
          label="Occupied"
          value={`${count(totalOccupied)} / ${count(totalRentable)}`}
          note="Counted, not averaged."
        />
        <Field label="Base rent billed" value={money(totalBaseRent)} />
        <Field
          label="Deviations"
          value={count(failures.data.length)}
          tone={failures.data.length > 0 ? "redline" : "ink"}
          note="Redlined in the margin."
        />
      </TitleBlock>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_19rem] xl:gap-10">
        <div className="min-w-0 space-y-12">
          {/* ---- The schedule ------------------------------------------- */}
          <Register
            title="Property schedule"
            note={
              <>
                Twenty-five properties, largest first. Size is drawn to one
                shared scale across every row, so the portfolio&rsquo;s spread —
                from a 775-unit complex to a three-unit retail strip — is
                visible before any figure is read.
              </>
            }
            aside={<SourcesMark sources={occupancy.sources} />}
          >
            <div className="mb-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
              <TypeLegend types={presentTypes} />
              {/* Below lg the schedule drops size, units and the raw
                  occupied/rentable count, keeping code, source and % occupied
                  — the columns rules #3 and #4 depend on. */}
              <span className="letter text-ink-3 lg:hidden">
                Size and unit counts hidden — open a sheet for the full record
              </span>
            </div>

            <div className="-mx-1 overflow-x-auto px-1">
              <table className="schedule w-full lg:min-w-[54rem]">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Property</th>
                    <th className="hidden lg:table-cell">Type</th>
                    <th>Source</th>
                    <th className="hidden w-[9rem] lg:table-cell">Size</th>
                    <th className="hidden text-right lg:table-cell">Units</th>
                    <th className="hidden text-right lg:table-cell">
                      Occ / rentable
                    </th>
                    <th className="text-right">% occ</th>
                    <th className="hidden lg:table-cell" />
                  </tr>
                </thead>
                <tbody>
                  {propertyRows.map((p) => (
                    <tr key={p.property_code} className="group">
                      <td>
                        <Link
                          href={`/properties/${p.property_code}`}
                          className="font-mono text-[0.8125rem] font-medium text-green-700 underline decoration-green-300 underline-offset-[3px] transition-colors hover:text-green-900 hover:decoration-green-700"
                        >
                          {p.property_code}
                        </Link>
                      </td>
                      <td className="text-ink max-w-[7.5rem] truncate sm:max-w-[9rem] lg:max-w-[15rem]">
                        {p.property_name}
                      </td>
                      <td className="hidden lg:table-cell">
                        <TypeKey type={p.property_type} compact />
                      </td>
                      <td>
                        <SourceMark source={p.occupancy_source} compact />
                      </td>
                      <td className="hidden lg:table-cell">
                        <ScaleBar
                          value={p.total_units}
                          max={maxUnits}
                          label={`${count(p.total_units)} units`}
                        />
                      </td>
                      <td className="num hidden lg:table-cell">
                        {count(p.total_units)}
                      </td>
                      <td className="num hidden lg:table-cell">
                        {count(p.occupied_units)} / {count(p.rentable_units)}
                      </td>
                      <td className="num text-ink font-medium">
                        {pct(p.pct_occupied)}
                      </td>
                      <td className="hidden w-6 lg:table-cell">
                        <Link
                          href={`/properties/${p.property_code}`}
                          aria-label={`Open sheet for ${p.property_name}`}
                          className="text-ink-3 inline-flex transition-colors group-hover:text-green-700"
                        >
                          <GlyphIn />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-ink-3 border-rule mt-4 border-t pt-3 text-[0.75rem] leading-relaxed">
              {derivedCount} of {propertyRows.length} properties carry a derived
              occupancy source: the availability report and the rent roll
              disagree, so occupancy is taken from the rent roll. Open any of
              them to read why.
            </p>
          </Register>

          {/* ---- The two views ------------------------------------------ */}
          <div className="grid gap-12 lg:grid-cols-2 lg:gap-10">
            <Register
              title="Occupancy by type"
              note="Segmented, never blended. This is the only place a percentage belongs."
              aside={<SourcesMark sources={summary.sources} />}
            >
              <OccupancyByType rows={occByType} />
            </Register>

            <Register
              title="Expirations · 12 months"
              note="Leases reaching expiration by month. Month-to-month leases carry no expiration date and are excluded upstream."
              aside={<SourcesMark sources={expirations.sources} />}
            >
              <ExpirationSchedule rows={expByMonth} types={expiringTypes} />
            </Register>
          </div>
        </div>

        {/* ---- The margin --------------------------------------------- */}
        <div className="xl:sticky xl:top-5 xl:self-start">
          <RevisionMargin failures={failures.data} />
        </div>
      </div>
    </div>
  );
}
