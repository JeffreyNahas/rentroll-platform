// Marks: the fixed-cell state vocabulary.
//
// Occupancy source, property type and reconciliation state each get a drawn
// mark in a fixed position. Color confirms the reading; it never carries it
// alone. That is why green could be taken back for the ground: nothing here
// needs green to mean "good".

import type { Source } from "@/lib/types";
import { dateLabel } from "@/lib/format";
import { GlyphDerived, GlyphSheet, GlyphTypeKey, GlyphVerified } from "./Glyph";

/* --- Occupancy source ---------------------------------------------------- */

export function SourceMark({
  source,
  compact,
}: {
  source: "availability_report" | "rent_roll_derived";
  compact?: boolean;
}) {
  const verified = source === "availability_report";
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap ${
        verified ? "text-ink-2" : "text-amber"
      }`}
      title={
        verified
          ? "Availability report and rent roll reconcile; occupancy is read from the availability report."
          : "The two exports disagree for this property; occupancy is derived from the rent roll instead."
      }
    >
      {verified ? <GlyphVerified /> : <GlyphDerived />}
      {!compact && (
        <span className="letter text-current">
          {verified ? "Reported" : "Derived"}
        </span>
      )}
    </span>
  );
}

/* --- Property type -------------------------------------------------------
   Keyed by hatch, the way a plat or a Sanborn map keys land use. Texture
   rather than hue, so the validated series colors stay free for the data. */

export function TypeKey({
  type,
  compact,
}: {
  type: string;
  compact?: boolean;
}) {
  return (
    <span
      className="text-ink-2 inline-flex items-center gap-1.5 whitespace-nowrap"
      title={`Property type: ${type}`}
    >
      <GlyphTypeKey type={type} />
      {!compact && <span className="letter text-current">{type}</span>}
    </span>
  );
}

export function TypeLegend({ types }: { types: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
      {types.map((t) => (
        <TypeKey key={t} type={t} />
      ))}
    </div>
  );
}

/* --- Sources -------------------------------------------------------------
   Rule #3: every metric carries its source. This is the mark that does it —
   it sits beside the register heading of anything with a number in it, and
   opens to the exact files. No JS: a <details> element does the whole job. */

export function SourcesMark({ sources }: { sources: Source[] | null }) {
  if (!sources || sources.length === 0) {
    return (
      <span className="letter text-amber inline-flex items-center gap-1.5">
        <GlyphSheet />
        No sources
      </span>
    );
  }

  const asOf = sources[0]?.as_of_date;
  const uniqueProps = new Set(sources.map((s) => s.property_code)).size;

  return (
    <details className="group relative">
      <summary className="letter hover:text-ink flex cursor-pointer list-none items-center gap-1.5 transition-colors marker:content-none">
        <GlyphSheet />
        {sources.length} source{sources.length === 1 ? "" : "s"} · as of{" "}
        {dateLabel(asOf)}
      </summary>
      <div className="border-rule-strong bg-field absolute right-0 z-40 mt-2 max-h-80 w-[26rem] max-w-[85vw] overflow-y-auto border-2 p-3">
        <div className="letter border-rule mb-2 border-b pb-2">
          {sources.length} snapshot{sources.length === 1 ? "" : "s"} ·{" "}
          {uniqueProps} propert{uniqueProps === 1 ? "y" : "ies"}
        </div>
        <ul className="space-y-1">
          {sources.map((s) => (
            <li
              key={s.snapshot_id}
              className="text-ink-3 flex gap-2 font-mono text-[0.6875rem]"
            >
              <span className="text-green-700">{s.property_code}</span>
              <span className="truncate">{s.filename}</span>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}
