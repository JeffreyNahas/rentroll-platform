// The title block.
//
// On a real drawing sheet this is the ruled grid in the corner that says what
// the sheet is, what it was drawn from, when, and at which revision. Nothing
// on the sheet is trustworthy without it.
//
// It is also what replaces the KPI card strip. The portfolio's totals are
// title-block fields — labelled cells in a ruled grid — not five floating
// tiles with big numbers, so a figure and its provenance arrive together
// instead of the figure arriving alone and the provenance living in a
// footnote nobody reads.

import type { ReactNode } from "react";

// A grid rather than a wrapping flex row: with flex, the last field on a
// short row sat alone against a long empty gap. A grid keeps every field the
// same width and every row full, which is what makes it read as ruled paper
// rather than as boxes that happened to line up.
export function TitleBlock({
  cols,
  children,
}: {
  cols: string;
  children: ReactNode;
}) {
  return (
    <div className="border-rule-strong bg-field/60 overflow-hidden border">
      {/* Each cell rules its own right and bottom edge; the grid runs 1px
          past its container so the outermost rules clip against the frame
          instead of doubling it. A partial last row stays correct. */}
      <div className={`-mr-px -mb-px grid grid-cols-2 sm:grid-cols-3 ${cols}`}>
        {children}
      </div>
    </div>
  );
}

export function Field({
  label,
  value,
  note,
  tone = "ink",
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  tone?: "ink" | "redline" | "amber" | "green";
}) {
  const toneClass = {
    ink: "text-ink",
    redline: "text-redline",
    amber: "text-amber",
    green: "text-green-700",
  }[tone];

  return (
    <div className="border-rule flex min-w-0 flex-col gap-1.5 border-r border-b px-3.5 py-2.5">
      <span className="letter">{label}</span>
      <span
        className={`fig font-mono text-[0.9375rem] leading-none font-medium ${toneClass}`}
      >
        {value}
      </span>
      {note && (
        <span className="text-ink-3 text-[0.6875rem] leading-snug">{note}</span>
      )}
    </div>
  );
}
