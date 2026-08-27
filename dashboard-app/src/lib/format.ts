// Response numbers come back as float64 (see docs/journal.md — decimal-to-
// float boundary conversion). These formatters are the render-time contract.

export function money(
  v: number | null | undefined,
  maxFractionDigits = 0
): string {
  if (v == null) return "—";
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: maxFractionDigits,
    minimumFractionDigits: 0,
  });
}

export function moneyCents(v: number | null | undefined): string {
  return money(v, 2);
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function count(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString("en-US");
}

export function monthLabel(iso: string): string {
  // "2026-03-01" → "Mar 2026"
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00Z" : ""));
  return d.toLocaleDateString("en-US", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function dateLabel(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00Z" : ""));
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

// Property type is keyed by hatch, not by hue — see components/sheet/Glyph.tsx.
// Freeing type from color is what keeps the six validated series inks
// available to the data instead of being spent on five badges.
