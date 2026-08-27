// The drawing legend.
//
// Every meaning in this system is carried by a drawn mark first and a color
// second. That is not decoration: occupancy source, reconciliation state and
// property type are load-bearing distinctions, and the old dashboard carried
// them on green-vs-amber alone, which fails for a colorblind reader and for
// anyone printing the page. Here the mark says it and the color confirms it.
//
// One stroke weight (1.25) and one 16-unit box throughout, so the marks read
// as one family the way a plat legend does.

type GlyphProps = { className?: string; title?: string };

const BOX = "0 0 16 16";

function Svg({
  children,
  className,
  title,
}: GlyphProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox={BOX}
      width="13"
      height="13"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      strokeLinecap="square"
      className={`shrink-0 ${className ?? ""}`}
      role={title ? "img" : "presentation"}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {children}
    </svg>
  );
}

/* --- Occupancy source -----------------------------------------------------
   Verified: the two Yardi exports agree, so the box is closed and ticked.
   Derived:  they disagree and we fell back to the rent roll, so the box is
             open and hatched — visibly an inference, not a reading. */

export function GlyphVerified(p: GlyphProps) {
  return (
    <Svg {...p}>
      <rect x="1.5" y="1.5" width="13" height="13" />
      <path d="M4.5 8.4 L7 10.9 L11.5 5.2" strokeWidth={1.6} />
    </Svg>
  );
}

export function GlyphDerived(p: GlyphProps) {
  return (
    <Svg {...p}>
      <rect x="1.5" y="1.5" width="13" height="13" strokeDasharray="2.5 1.9" />
      <path d="M2 11 L11 2 M6 14 L14 6" strokeWidth={1} />
    </Svg>
  );
}

/* --- Deviation ------------------------------------------------------------
   The revision triangle from a drawing sheet. On a real sheet it flags a spot
   where the drawing changed and points at the revision table; here it flags a
   spot where the source data contradicts itself and points at the margin. */

export function GlyphDeviation({ n, ...p }: GlyphProps & { n?: number }) {
  return (
    <svg
      viewBox={BOX}
      width="15"
      height="15"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      strokeLinejoin="round"
      className={`shrink-0 ${p.className ?? ""}`}
      role={p.title ? "img" : "presentation"}
      aria-label={p.title}
      aria-hidden={p.title ? undefined : true}
    >
      <path d="M8 1.6 L15 14.2 L1 14.2 Z" />
      {n != null && (
        <text
          x="8"
          y="12.1"
          textAnchor="middle"
          fontSize="7.4"
          fontWeight="700"
          fill="currentColor"
          stroke="none"
          fontFamily="var(--font-mono)"
        >
          {n}
        </text>
      )}
    </svg>
  );
}

/* --- Note / annotation flag ---------------------------------------------- */

export function GlyphNote(p: GlyphProps) {
  return (
    <Svg {...p}>
      <path d="M3.2 14.5 L3.2 1.8 L12.8 1.8 L12.8 9 L3.2 9" />
    </Svg>
  );
}

/* --- Sheet / source ------------------------------------------------------- */

export function GlyphSheet(p: GlyphProps) {
  return (
    <Svg {...p}>
      <path d="M2.5 1.5 L13.5 1.5 L13.5 14.5 L2.5 14.5 Z" />
      <path d="M2.5 11.2 L13.5 11.2 M9.3 11.2 L9.3 14.5" strokeWidth={1} />
    </Svg>
  );
}

/* --- Property-type key ----------------------------------------------------
   Land use keyed by hatch, the way a Sanborn map or a recorded plat keys it.
   This is what lets property type stop competing with the chart palette for
   hue: type is a texture, so the six validated series colors stay free for
   the data. */

export type TypePattern = "solid" | "ruled" | "diagonal" | "stipple" | "open";

const PATTERN_BY_TYPE: Record<string, TypePattern> = {
  residential: "solid",
  affordable: "ruled",
  commercial: "diagonal",
  land: "stipple",
  other: "open",
};

export function typePattern(t: string): TypePattern {
  return PATTERN_BY_TYPE[t] ?? "open";
}

export function GlyphTypeKey({
  type,
  className,
}: {
  type: string;
  className?: string;
}) {
  const p = typePattern(type);
  const id = `tk-${p}`;
  return (
    <svg
      viewBox={BOX}
      width="13"
      height="13"
      className={`shrink-0 ${className ?? ""}`}
      aria-hidden="true"
    >
      <defs>
        {p === "ruled" && (
          <pattern
            id={id}
            width="16"
            height="3.2"
            patternUnits="userSpaceOnUse"
          >
            <line
              x1="0"
              y1="1.6"
              x2="16"
              y2="1.6"
              stroke="currentColor"
              strokeWidth="1.15"
            />
          </pattern>
        )}
        {p === "diagonal" && (
          <pattern
            id={id}
            width="4"
            height="4"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <line
              x1="0"
              y1="0"
              x2="0"
              y2="4"
              stroke="currentColor"
              strokeWidth="1.5"
            />
          </pattern>
        )}
        {p === "stipple" && (
          <pattern id={id} width="4" height="4" patternUnits="userSpaceOnUse">
            <circle cx="1.6" cy="1.6" r="0.85" fill="currentColor" />
          </pattern>
        )}
      </defs>
      <rect
        x="1.5"
        y="1.5"
        width="13"
        height="13"
        fill={
          p === "solid" ? "currentColor" : p === "open" ? "none" : `url(#${id})`
        }
        stroke="currentColor"
        strokeWidth="1.25"
      />
    </svg>
  );
}

/* --- Lease state ----------------------------------------------------------
   The same drawn family as the rest of the legend: how full the mark is
   tracks how occupied the unit is, so the sequence reads as a scale rather
   than as four unrelated colors. */

export function GlyphState({
  state,
  ...p
}: GlyphProps & { state: "current" | "notice" | "vacant" | "future" }) {
  if (state === "future") {
    return (
      <Svg {...p}>
        <path d="M8 1.8 L14.2 8 L8 14.2 L1.8 8 Z" strokeLinejoin="round" />
      </Svg>
    );
  }
  return (
    <Svg {...p}>
      <circle cx="8" cy="8" r="6.2" />
      {state === "current" && (
        <circle cx="8" cy="8" r="6.2" fill="currentColor" />
      )}
      {state === "notice" && (
        <path
          d="M8 1.8 A6.2 6.2 0 0 1 8 14.2 Z"
          fill="currentColor"
          stroke="none"
        />
      )}
    </Svg>
  );
}

/* --- Chevron (drill-in) --------------------------------------------------- */

export function GlyphIn(p: GlyphProps) {
  return (
    <Svg {...p}>
      <path d="M5.5 2.5 L11 8 L5.5 13.5" strokeLinecap="round" />
    </Svg>
  );
}

/* --- Enter (command dock submit) ------------------------------------------
   A drawn return-key mark rather than the Unicode ⏎ glyph -- everything the
   command dock draws stays in this family, the same as every other icon on
   the sheet. */

export function GlyphEnter(p: GlyphProps) {
  return (
    <Svg {...p}>
      <path d="M4.5 5 L11.5 5 L11.5 9.5 L6.5 9.5" />
      <path d="M9 7 L6.5 9.5 L9 12" />
    </Svg>
  );
}
