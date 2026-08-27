// The register: what replaces the card.
//
// Sections are separated by a ruled register and a deep gap, not by a box.
// A heading, a rule that runs to the margin, and whatever the section needs
// to declare about itself (its sources, its scope) riding at the right end of
// that rule — the way a drawing sheet titles a view.

import type { ReactNode } from "react";

export function Register({
  title,
  note,
  aside,
  children,
}: {
  title: string;
  note?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0">
      <div className="register">
        <h2 className="letter-lg text-[0.9375rem] whitespace-nowrap">
          {title}
        </h2>
        <span className="register-rule" />
        {aside && <div className="shrink-0">{aside}</div>}
      </div>
      {note && (
        <p className="text-ink-3 mt-2.5 max-w-[68ch] text-[0.8125rem] leading-relaxed">
          {note}
        </p>
      )}
      <div className="mt-5">{children}</div>
    </section>
  );
}

/* --- Scale bar -----------------------------------------------------------
   One continuous scale across the whole schedule, drawn from a single shared
   maximum. A 775-unit complex and a 3-unit retail strip are meant to look
   incommensurable before you read either number — that is the point of the
   rule against blending them, made visible rather than documented. */

export function ScaleBar({
  value,
  max,
  label,
}: {
  value: number;
  max: number;
  label: string;
}) {
  const w = max > 0 ? Math.max((value / max) * 100, value > 0 ? 1.2 : 0) : 0;
  return (
    <span className="tip flex w-full items-center" tabIndex={0}>
      <span className="bg-rule/40 relative block h-2 w-full">
        <span
          className="mark absolute inset-y-0 left-0 block bg-green-700"
          style={{ width: `${w}%` }}
        />
      </span>
      <span className="tip-body">{label}</span>
    </span>
  );
}
