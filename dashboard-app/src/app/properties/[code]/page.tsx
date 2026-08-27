// Sheet n — one property in depth.
//
// The same sheet grammar as the portfolio view at a deeper zoom: title block,
// registers, the same marks, the same scale. Drilling in reveals detail; it
// does not hand you a differently-designed page.
//
// Next 16: `params` and `searchParams` are Promises and must be awaited.

import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { count, dateLabel, money, pct } from "@/lib/format";
import { TitleBlock, Field } from "@/components/sheet/TitleBlock";
import { Register } from "@/components/sheet/Register";
import { SheetNotes } from "@/components/sheet/Revisions";
import { SourceMark, SourcesMark, TypeKey } from "@/components/sheet/Marks";
import { ChargeMixBar } from "@/components/sheet/Charts";
import { LeasesTable } from "@/components/LeasesTable";

type PageProps = {
  params: Promise<{ code: string }>;
  searchParams: Promise<{ section?: string; offset?: string }>;
};

export default async function PropertyDetailPage({
  params,
  searchParams,
}: PageProps) {
  const { code } = await params;
  const sp = await searchParams;
  const section: "current" | "future" =
    sp.section === "future" ? "future" : "current";
  const offset = Math.max(Number.parseInt(sp.offset ?? "0", 10) || 0, 0);

  const [detailRes, leasesRes] = await Promise.all([
    api.propertyDetail(code),
    api.propertyLeases(code, section, 100, offset),
  ]).catch((err) => {
    if (String(err).includes("404")) notFound();
    throw err;
  });

  const detail = detailRes.data[0];
  const occ = detail.occupancy;
  const ltl = detail.loss_to_lease;
  const del = detail.delinquency;

  const chargeRows = detail.charge_mix.map((c) => ({
    category: c.category,
    amount: c.sum_amount,
    share: c.pct_of_property_gross,
  }));

  const allWarnings = [...detailRes.warnings, ...leasesRes.warnings].filter(
    (w, i, arr) => arr.findIndex((x) => x.code === w.code) === i
  );

  return (
    <div className="space-y-8">
      <Link
        href="/"
        className="letter text-ink-3 inline-flex items-center gap-2 transition-colors hover:text-green-700"
      >
        <svg
          viewBox="0 0 16 16"
          width="12"
          height="12"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.4}
          strokeLinecap="round"
          aria-hidden="true"
        >
          <path d="M10 2.5 L4.5 8 L10 13.5" />
        </svg>
        Sheet index
      </Link>

      <div>
        <div className="mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-2">
          <h1 className="letter-lg text-[1.4rem] tracking-[0.02em]">
            {occ.property_name}
          </h1>
          <span className="text-ink-3 font-mono text-[0.9375rem]">
            {occ.property_code}
          </span>
          <TypeKey type={occ.property_type} />
          <SourceMark source={occ.occupancy_source} />
        </div>

        <TitleBlock cols="lg:grid-cols-6">
          <Field
            label="Snapshot"
            value={dateLabel(occ.as_of_date)}
            note="Single frozen snapshot."
          />
          <Field
            label="Occupied"
            value={`${count(occ.occupied_units)} / ${count(occ.rentable_units)}`}
            note={
              occ.pct_occupied != null
                ? `${pct(occ.pct_occupied)} of rentable`
                : undefined
            }
          />
          <Field
            label="On notice"
            value={count(occ.notice_units)}
            note="Still occupied; counted separately."
          />
          <Field label="Vacant" value={count(occ.vacant_units)} />
          <Field
            label="Unclassified"
            value={count(occ.unclassified_units)}
            tone={occ.unclassified_units > 0 ? "redline" : "ink"}
            note={
              occ.unclassified_units > 0
                ? "Counted by the report, never stated."
                : "All units classified."
            }
          />
          <Field
            label="Occupancy source"
            value={
              occ.occupancy_source === "availability_report"
                ? "Reported"
                : "Derived"
            }
            tone={
              occ.occupancy_source === "availability_report" ? "ink" : "amber"
            }
            note={
              occ.occupancy_source === "availability_report"
                ? "Both exports reconcile."
                : "Exports disagree; rent roll used."
            }
          />
        </TitleBlock>
      </div>

      {allWarnings.length > 0 && <SheetNotes warnings={allWarnings} />}

      <div className="grid gap-12 lg:grid-cols-2 lg:gap-10">
        {/* ---- Loss to lease ------------------------------------------- */}
        <Register
          title="Loss to lease"
          note={
            ltl
              ? `Market rent against actual base rent across ${count(ltl.units_in_scope)} active leases.`
              : undefined
          }
          aside={<SourcesMark sources={detailRes.sources} />}
        >
          {ltl ? (
            <div className="space-y-5">
              <div className="border-rule divide-rule flex divide-x border">
                <div className="flex-1 px-3.5 py-3">
                  <div className="letter">Market</div>
                  <div className="fig text-ink mt-1.5 font-mono text-[1.0625rem]">
                    {money(ltl.market_rent_total)}
                  </div>
                </div>
                <div className="flex-1 px-3.5 py-3">
                  <div className="letter">Effective</div>
                  <div className="fig text-ink mt-1.5 font-mono text-[1.0625rem]">
                    {money(ltl.effective_rent_total)}
                  </div>
                </div>
                <div className="flex-1 px-3.5 py-3">
                  <div className="letter">Delta</div>
                  <div
                    className={`fig mt-1.5 font-mono text-[1.0625rem] ${
                      ltl.loss_to_lease >= 0 ? "text-ink" : "text-redline"
                    }`}
                  >
                    {money(ltl.loss_to_lease)}
                  </div>
                  <div className="text-ink-3 mt-1 font-mono text-[0.6875rem]">
                    {pct(ltl.pct_loss_to_lease)}
                  </div>
                </div>
              </div>

              {ltl.loss_to_lease < 0 && (
                <p className="text-ink-2 text-[0.8125rem] leading-relaxed">
                  Negative: actual rent <em>exceeds</em> market. On this
                  property Yardi&rsquo;s Market Rent field is behaving as a
                  floor rather than an asking rent — a real signal about the
                  source data, not an error in the calculation.
                </p>
              )}
            </div>
          ) : (
            /* Out of scope gets a structural treatment, not a grey dash. The
               hatched field states that the value was never applicable, which
               is a different claim from "we could not compute it". */
            <div className="border-rule border">
              <div className="hatched border-rule h-14 border-b" />
              <div className="px-3.5 py-3">
                <div className="letter text-ink-2">
                  Not applicable · {occ.property_type}
                </div>
                <p className="text-ink-3 mt-2 text-[0.8125rem] leading-relaxed">
                  By design, not by data loss. Commercial leases carry a market
                  rent of zero in the source export, and land and management
                  records carry no leases at all — so there is no market
                  baseline to measure against.
                </p>
              </div>
            </div>
          )}
        </Register>

        {/* ---- Delinquency --------------------------------------------- */}
        <Register
          title="Delinquency"
          note={del ? "Outstanding balances across active leases." : undefined}
          aside={<SourcesMark sources={detailRes.sources} />}
        >
          {del ? (
            <div className="border-rule divide-rule flex divide-x border">
              <div className="flex-1 px-3.5 py-3">
                <div className="letter">Delinquent</div>
                <div className="fig text-ink mt-1.5 font-mono text-[1.0625rem]">
                  {count(del.n_delinquent_leases)} /{" "}
                  {count(del.n_active_leases)}
                </div>
                <div className="text-ink-3 mt-1 font-mono text-[0.6875rem]">
                  {pct(del.pct_leases_delinquent)}
                </div>
              </div>
              <div className="flex-1 px-3.5 py-3">
                <div className="letter">Owed</div>
                <div
                  className={`fig mt-1.5 font-mono text-[1.0625rem] ${
                    del.total_balance_owed > 0 ? "text-redline" : "text-ink"
                  }`}
                >
                  {money(del.total_balance_owed)}
                </div>
                {del.max_balance != null && del.max_balance > 0 && (
                  <div className="text-ink-3 mt-1 font-mono text-[0.6875rem]">
                    max {money(del.max_balance)}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="border-rule border">
              <div className="hatched border-rule h-14 border-b" />
              <div className="px-3.5 py-3">
                <div className="letter text-ink-2">No active leases</div>
                <p className="text-ink-3 mt-2 text-[0.8125rem] leading-relaxed">
                  Nothing to be delinquent on.
                </p>
              </div>
            </div>
          )}
        </Register>
      </div>

      {/* ---- Charge mix ------------------------------------------------ */}
      <Register
        title="Charge mix"
        note="Share of gross billed charges by category. Base rent is resolved through charge_code.category, never a literal RENT match — commercial base rent is RENTRETL or RNTPROF."
        aside={<SourcesMark sources={detailRes.sources} />}
      >
        <ChargeMixBar rows={chargeRows} />
      </Register>

      {/* ---- Leases ---------------------------------------------------- */}
      <Register
        title="Leases"
        aside={<SourcesMark sources={leasesRes.sources} />}
      >
        <LeasesTable
          rows={leasesRes.data}
          section={leasesRes.pagination.section}
          pagination={leasesRes.pagination}
          code={code}
        />
      </Register>
    </div>
  );
}
