---
name: Rent Roll Intelligence
description: A reconciled, source-cited portfolio dashboard drawn as an engineering sheet — ISO/DIN title blocks on green-grid computation-pad stock.
colors:
  sheet: "#e9e7dc"
  field: "#f4f2e9"
  field-sunk: "#eeecdf"
  grid: "#d5ddc7"
  grid-major: "#c3cfb2"
  rule: "#b9bfac"
  rule-strong: "#6e7a66"
  ink: "#1b211c"
  ink-2: "#4a5449"
  ink-3: "#5f6a5a"
  ink-faint: "#8a9184"
  green-900: "#22301f"
  green-700: "#35543a"
  green-500: "#4c7a4e"
  green-300: "#9dba95"
  green-100: "#dce5d3"
  green-50: "#eaf0e2"
  redline: "#b0442e"
  redline-deep: "#8a3423"
  redline-wash: "#f6e6e1"
  amber: "#955714"
  amber-wash: "#f6ecdd"
  series-dimension-blue: "#1f5fa9"
  series-survey-orange: "#d2601a"
  series-teal: "#00938a"
  series-ochre: "#c99000"
  series-plum: "#7b4b9e"
  series-drafting-green: "#4c7a22"
  series-graphite: "#3a4038"
  series-other: "#8a9184"
typography:
  lettering:
    fontFamily: "Archivo Narrow, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "0.11em"
  lettering-lg:
    fontFamily: "Archivo Narrow, sans-serif"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "0.055em"
  body:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
  figures:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontFeatureSettings: "tabular-nums"
spacing:
  field-padding: "0.625rem 0.875rem"
  register-gap: "0.5rem 0.875rem"
  cell-padding: "0.4375rem 0.625rem"
components:
  title-block-field:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    padding: "{spacing.field-padding}"
  register-heading:
    textColor: "{colors.ink}"
    typography: "{typography.lettering-lg}"
  schedule-row-hover:
    backgroundColor: "{colors.green-50}"
  tooltip:
    backgroundColor: "{colors.green-900}"
    textColor: "{colors.green-50}"
    rounded: "2px"
  section-toggle-active:
    backgroundColor: "{colors.green-700}"
    textColor: "{colors.green-50}"
---

# Design System: Rent Roll Intelligence

This governs `dashboard-app/` (Next.js 16, React 19, Tailwind v4) — the
canonical dashboard. `web/` (Next 14 + Tremor) is superseded and unstyled by
this document; it is not maintained and carries no design authority.

## Overview

**Creative North Star: "The Engineering Sheet"**

The dashboard is drawn as an ISO/DIN engineering drawing sheet on green-grid
computation-pad stock. Every panel is a sheet, and no sheet exists without a
title block naming its source, its snapshot, and its revision state — that
is not a metaphor bolted onto the UI after the fact, it is the literal
structure the product's own rules produce: rule #3 ("every metric carries
its source") becomes a title block; rule #6 ("surface data problems") becomes
a numbered revision margin; rule #4 ("never blend across property types")
becomes one shared scale drawn across a schedule instead of a percentage.
The system was chosen against a user-pinned constraint — green and off-white
as the ground, a wider palette for charts — and built out from a set of
real drafting artifacts (title blocks, redline revision marks, hatched
"not-applicable" fields, plat-map land-use keys) rather than invented
UI chrome. Full derivation and the seed key (`c0872ef5`, form "candidate 5
of 7") are recorded in the direction contract embedded as an HTML comment
at the top of `<body>` in `app/layout.tsx`.

The visitor mode is Operate: a reviewer or analyst reading a portfolio,
never a persuasion surface. Density and legibility outrank ornament
everywhere. The system is committed to one appearance — a lit paper pad
under room light — and has no dark mode; that is a stated invariant, not
an unfinished feature.

**Key Characteristics:**
- No card, no card border, no drop shadow anywhere. Structure comes from
  ruled dividers and empty space.
- Meaning is carried by a drawn mark first, color second — never color
  alone.
- Green is the ground and the structural color. It carries no status
  meaning.
- Redline is reserved for the deviation/revision system and never doubles
  as a chart series.
- Every chart is hand-drawn CSS/SVG. No chart library, no client
  JavaScript for any visualization.
- Light-only, deliberately.

## Colors

Off-white engineering-pad stock under a printed pale-green grid, with a
narrow, functionally-partitioned ink system: one scale for structure
(green), one for annotation (redline, amber — each reserved to a single
job), and eight series inks gated by an automated contrast/colorblind
validator rather than picked by eye.

### Primary
- **Structural Green** (`#35543a`, `--color-green-700`): the sheet's one
  functional accent — links, the active leases-section toggle, focus
  rings, the occupancy scale-bar fill. Never used to mean "good" or
  "reconciled"; that job belongs to the drawn marks in Components.

### Secondary
- **Redline** (`#b0442e`, `--color-redline`): reserved exclusively for the
  deviation/revision system — the numbered triangles in the margin, a
  negative loss-to-lease delta, an outstanding balance. **The Reserved Ink
  Rule.** No other element on the sheet may use redline; if it appears,
  the reader should already expect "something here contradicts something
  else" before reading the text next to it.
- **Amber** (`#955714`, `--color-amber`, 5.1:1 on field): the single
  "derived, not reported" signal — a fallback occupancy source, a sheet
  note, the disabled command-dock status. Always paired with a drawn mark
  or a label; never the only carrier of that meaning.

### Tertiary
- **Series Set** (six inks, fixed order, never cycled): `--color-s1`
  Dimension Blue `#1f5fa9`, `--color-s2` Survey Orange `#d2601a`,
  `--color-s3` Teal `#00938a`, `--color-s4` Ochre `#c99000`, `--color-s5`
  Plum `#7b4b9e`, `--color-s6` Drafting Green `#4c7a22`. Plus two utility
  slots: `--color-s-anchor` Graphite `#3a4038` (the dominant baseline
  category in a stacked chart — charge mix's "base rent" segment) and
  `--color-s-other` `#8a9184` (the fold-to bucket past six series).

### Neutral
- **Field** (`#f4f2e9`, `--color-field`): the drawing area — the surface
  every register, table, and title block sits on.
- **Sheet** (`#e9e7dc`, `--color-sheet`): the board beneath the field;
  page background and the sheet's outer frame.
- **Field Sunk** (`#eeecdf`, `--color-field-sunk`): recessed register,
  currently used only by the command dock's ground.
- **Ink** (`#1b211c`, 14.6:1 on field): primary text and figures.
- **Ink 2** (`#4a5449`, 7.1:1): secondary text — property names, resident
  placeholders, body copy inside cards.
- **Ink 3** (`#5f6a5a`, 5.1:1): labels, captions, table secondary columns.
  This is the lightest ink allowed to carry text.
- **Ink Faint** (`#8a9184`, 2.9:1): **non-text only** — see the Named Rule
  below. Currently unused by any component; declared, not yet spent.
- **Grid** (`#d5ddc7`) / **Grid Major** (`#c3cfb2`): the printed pad grid
  painted into `.pad-grid` — fine lines every 16px, a heavier line every
  80px.
- **Rule** (`#b9bfac`) / **Rule Strong** (`#6e7a66`): hairline and heavy
  dividers — table rows, title-block cells, section registers, the sheet's
  own frame.

### Named Rules
**The Ink Faint Trap.** `--color-ink-faint` measures 2.9:1 on the field —
below the 4.5:1 body-text floor. It exists for non-text decoration only
(a disabled icon, a resting-state fill). A real defect shipped once when
placeholder copy, an axis label, and a hover-affordance icon all rode this
token; all three were moved to `--color-ink-3` (5.1:1). Treat any new
`text-ink-faint` usage as a contrast bug until proven otherwise.

**The One Green Rule.** Green is spent once, on structure. If a future
addition needs a "this reconciled" signal, it must be a drawn mark (see
Components), never a second use of `--color-green-*` as a status fill —
that is the exact ambiguity this system was rebuilt to remove.

## Typography

**Display/Label Font:** Archivo Narrow (with sans-serif fallback)
**Body Font:** Geist (with `ui-sans-serif, system-ui, sans-serif`)
**Figure Font:** Geist Mono (with `ui-monospace, monospace`)

**Character:** A condensed, tracked-open drafting caps face for every label
and heading, set against a plain workhorse sans for prose and a tabular
mono for every number. The pairing exists to make one distinction visible
at a glance: *this is a label* versus *this is a reading*.

### Hierarchy
- **Lettering-lg** (700, ~15px depending on context, line-height 1.05,
  tracking 0.055em, uppercase): sheet title, register headings (`Property
  schedule`, `Charge mix`), property name on the detail sheet. `.letter-lg`.
- **Lettering** (600, 11px, line-height 1.1, tracking 0.11em, uppercase):
  every field label, table column head, legend key, badge text. `.letter`.
- **Body** (Geist, regular weight, ~13px, relaxed line-height): register
  notes, sheet notes, the loss-to-lease explanation paragraph. Measure
  capped at `max-w-[68ch]` in `Register`'s note slot.
- **Figures** (Geist Mono, tabular-nums, 13–17px depending on context):
  every number on the sheet — title-block values, table cells, KPI-style
  figures. `.fig` plus `.num` for right-aligned table cells.

### Named Rules
**The No Prose Numbers Rule.** A number never sets in the body sans. If it
is a reading — a dollar amount, a count, a percentage, a date — it is
Geist Mono with `tabular-nums`, so columns of figures actually align.

## Layout

Single-column content flow inside one drawn sheet frame
(`border` + `.pad-grid`), capped at `max-w-[1680px]`, padded `p-3` /
`md:p-5`. Sections are `Register` blocks — a heading, a rule that runs to
the margin, an optional right-aligned `aside` (almost always a
`SourcesMark`) — separated by generous vertical rhythm (`space-y-8` at
page level, `mt-5` inside a register), never by a boxed container.

**Two-column split at `xl`:** the portfolio page runs the schedule and
charts in a `minmax(0,1fr)` column against a fixed `19rem` revision margin
(`RevisionMargin`, `sticky top-5` at `xl`); below `xl` the margin reflows
under the main content.

**Title blocks are CSS grids, not flex rows.** `TitleBlock` renders
`grid-cols-2` by default, widening via a `cols` prop (`sm:grid-cols-3`,
then a caller-supplied breakpoint — `lg:grid-cols-4 xl:grid-cols-8` on the
portfolio sheet, `lg:grid-cols-6` on the property sheet) so every row
stays full and a short trailing row never leaves one field stranded
against empty space — a real defect this system replaced.

**Data-dense tables collapse columns before they scroll.** The property
schedule drops `Type`, `Size`, `Units`, and `Occ / rentable` below `lg`,
keeping `Code / Property / Source / % occ` — the columns rule #3 (source)
and rule #4 (never-blended occupancy) actually depend on — visible with no
horizontal scroll. Below `lg` cell padding also tightens
(`0.375rem` vs. the default `0.625rem`) to give the property-name column
room. The leases table, which has no such priority column set, scrolls
horizontally instead (`overflow-x-auto`) rather than hiding data.

**The command dock is `position: sticky; bottom: 0`,** pinned to the
sheet's own bottom edge (not the viewport), `z-20`, opaque
`--color-field-sunk` so it reads over scrolling content.

## Elevation & Depth

**Flat, by contract.** There is no `box-shadow` anywhere in the system and
no card surface to cast one. Structure comes entirely from 0.5px/1.5px
hairline rules (`--color-rule` / `--color-rule-strong`) and negative
space. This was violated twice during the build — a tooltip and a sources
popover both briefly carried a `box-shadow` — and corrected both times
once caught; treat any shadow reintroduced here as a regression against
the world's own founding claim, not a style choice.

### Named Rules
**The No-Shadow Rule.** If a component needs to separate from what is
behind it, give it a `border` (typically `border-2` for a floating
popover on the plain field, since a hairline alone reads as a stray rule
rather than a boundary once the element is no longer flush with the
sheet). Never a shadow.

## Shapes

**Square by default; the only intentional curves are functional.**
Borders are hairline rules, not rounded rectangles — the title block, the
schedule, the revision margin, the sources popover are all sharp-cornered.
The exceptions are chart marks: `.mark` rounds a bar's data-end (the side
away from the axis) to `3px`, `.mark-v` the top of a vertical column — a
small, deliberate softening so the bar reads as "drawn," not so the
system reads as rounded-UI. Circular geometry is reserved for the state
glyphs (`GlyphState`'s filled/half-filled/open circle, the diamond for
"future") and is never used for a container.

## Components

Nearly every component here is bespoke to the sheet metaphor; there is no
generic card/button/input library underneath it. Lead components live in
`dashboard-app/src/components/sheet/`.

### Title Block (`TitleBlock` + `Field`)
- **Shape:** a bordered grid (`border-rule-strong`), cells ruled on their
  right and bottom edges only, so the grid's own outer border does the
  rest — no doubled lines at the container edge.
- **A field:** label in Lettering, value in Figures (or Lettering-lg for a
  short text value), an optional caption in Ink 3. Four tone variants for
  the value — `ink` (default), `redline` (a deviation count, a negative
  delta), `amber` (a derived-source value), `green` (unused as of this
  write).
- **Replaces:** the KPI card strip. Portfolio totals are title-block
  fields, not floating tiles, so a figure and its provenance render in
  the same visual unit.

### Register (`Register`)
- **Anatomy:** Lettering-lg heading, a hairline rule running to the
  margin (`.register-rule`), an optional right-aligned `aside`. This is
  the section divider — **it is the card replacement**, and every new
  page section should be a `Register`, never a bordered `<div>`.
- **Note slot:** body-sans prose under the heading, capped at 68 characters
  for readability.

### Schedule (`.schedule` + `.num`)
- **Style:** collapsed-border table, Lettering column heads
  (border-bottom `rule-strong`), 0.5px row rules, `--color-green-50` row
  hover.
- **`.num`:** right-aligned, mono, `tabular-nums` — apply to every numeric
  table cell.

### Glyph legend (`Glyph.tsx`)
The system's signature component: every state on the sheet is a drawn
SVG mark on one shared grammar — a 16-unit viewBox, one stroke weight
(1.25), `strokeLinecap: square`. No Unicode glyph or emoji stands in for
one of these.
- **`GlyphVerified` / `GlyphDerived`:** a closed, ticked box for a
  reconciled occupancy source; an open, dashed, crossed box for a
  derived/fallback one. This pairing is what let green leave the status
  vocabulary — the box shape carries the meaning, color only confirms it.
- **`GlyphDeviation`:** the drafting revision triangle, optionally
  numbered, used in the revision margin.
- **`GlyphTypeKey` / `typePattern`:** property type keyed by fill
  **texture**, not hue — `solid` (residential), `ruled` (affordable),
  `diagonal` (commercial), `stipple` (land), `open` (other). This is what
  frees the six series inks for chart data instead of spending them on
  five type badges.
- **`GlyphState`:** lease status as a filled/half-filled/open circle plus
  a diamond for "future" — reads as one continuous scale of occupancy
  rather than four unrelated colors.
- **`GlyphSheet` / `GlyphNote` / `GlyphIn`:** source-citation, annotation,
  and drill-in affordances, same grammar.

### Named Rules
**The Drawn-Mark-First Rule.** Any new state this system needs to
represent gets a glyph on the same 16-unit/1.25-stroke grammar before it
gets a color. Color is confirmation, never the primary signal — this is
what makes every status legible without color vision and on a printed
page.

### Marks (`Marks.tsx`)
- **`SourceMark`:** pairs `GlyphVerified`/`GlyphDerived` with an
  optional Lettering caption ("Reported" / "Derived"); `title` attribute
  carries the full explanation.
- **`TypeKey` / `TypeLegend`:** the type-hatch glyph plus label; the
  legend is a flat wrapped row, no swatches.
- **`SourcesMark`:** a native `<details>`/`<summary>` disclosure (rule
  #3's enforcement point) — no JS needed to expand. Open state renders a
  bordered (`border-rule-strong`), shadow-free popover,
  `border-2` where it floats free of the sheet.

### Revision Margin & Sheet Notes (`Revisions.tsx`)
- **`RevisionMargin`:** a bordered aside, Redline header, numbered
  `<ol>` of deviations each carrying the API's own `note` text verbatim
  and, when present, a plain-language "off by N" delta (spelled out
  rather than a `Δ` glyph, which read as a second revision-triangle mark
  in the wrong place).
- **`SheetNotes`:** amber-wash background (`bg-amber-wash/50`), for
  envelope warnings — the sheet's general notes.

### Charts (`Charts.tsx`)
All three charts are hand-authored CSS/SVG, zero client JS, zero chart
library.
- **`OccupancyByType`:** single-hue horizontal bars (`--color-green-700`),
  one row per property type, a thin `--color-ink-2` tick marking
  "occupied including notice" as a reference line on the same bar — never
  a second bar, since it is the same quantity at a second threshold.
- **`ExpirationSchedule`:** vertical stacked columns, segmented by
  property type in fixed type order (color follows the entity across
  columns, never magnitude-sorted), each visible segment carrying a
  `minHeight: 3px` floor so a legend key with a real but tiny share (e.g.
  a single commercial lease) still renders as a visible band rather than
  a promise the eye cannot verify.
- **`ChargeMixBar`:** a horizontal stacked bar with a 2px gap between
  fills, `--color-s-anchor` (graphite) reserved for the dominant baseline
  category so a saturated series hue never drowns the minority categories
  that actually carry information. Suppressed entirely below two
  categories (a single-category bar reads as a redaction, and the table
  view already says "100.0%"). Always paired with a full data table below
  it — required, not optional, because the ochre series slot
  (`--color-s4`) sits under the 3:1 contrast floor on this surface.

### Named Rules
**The Donut Refusal.** Charge mix is never a pie/donut. With base rent
routinely ~90%+ of gross charges, a ring produces one dominant arc and
several unreadable slivers — the textbook part-to-whole anti-pattern. Any
future part-to-whole chart on this system defaults to a stacked bar plus
table, not a ring.

### Leases Table (`LeasesTable.tsx`, the one client component)
- **Section toggle:** two-button segmented control, active state
  `--color-green-700` fill on `--color-green-50` text (i.e. inverted —
  active is filled, inactive is the wash), `aria-pressed` on each button.
- **Pagination:** Previous/Next + "Page N of M", Lettering, disabled at
  the natural bounds (`opacity-40`, `pointer-events-none`), `offset`
  round-tripped through the URL query string. Only renders when
  `total > limit`.
- **Row state:** `GlyphState` circle/diamond, never a colored pill.

### Command Dock (`CommandDock.tsx`)
- **Style:** sticky bottom bar, `--color-field-sunk` ground, a chevron
  glyph, a disabled mono input with placeholder copy demonstrating the
  intended query, and an amber "Toolbelt not connected" status with a
  small filled dot.
- **Honesty constraint:** the input must remain genuinely `disabled`
  until the agent toolbelt (see TODO.md) exists. A mocked chat that
  accepts input and answers nothing is worse than a labeled empty state.

## Do's and Don'ts

### Do:
- **Do** give every new status a `Glyph.tsx` mark on the shared
  16-unit/1.25-stroke grammar before assigning it a color.
- **Do** re-run the palette validator against `--color-field` (currently
  `#f4f2e9`) whenever a chart's series set or the field token changes:
  `node scripts/validate_palette.js "<hex,hex,...>" --mode light --surface "#f4f2e9"`
  (path: the `dataviz` skill's `scripts/validate_palette.js`, or wherever
  it is vendored into this repo). A validator receipt that names a
  surface the build does not ship is worse than no receipt — this exact
  mistake happened once (`#F2F1EA` vs. the shipped `#f4f2e9`) and is
  disclosed rather than erased in `globals.css`'s header comment.
- **Do** use `Register` for every new page section. It is the card
  replacement.
- **Do** keep every figure in Geist Mono with `tabular-nums`.
- **Do** use `--color-redline` only inside the deviation/revision system.
- **Do** ship a table view alongside any chart that uses the ochre series
  slot (`--color-s4`, sub-3:1 on this surface) — the validator's relief
  rule, not a preference.

### Don't:
- **Don't** add a card, a card border, or a `box-shadow` anywhere. If
  something needs to visually separate, give it a `border` (2px if it's
  floating free of the sheet).
- **Don't** let `--color-green-*` mean "good," "reconciled," or "success."
  Green is structural only; status lives in `Glyph.tsx`.
- **Don't** use a Unicode glyph or emoji as a status icon. Draw it in
  `Glyph.tsx` on the shared grammar.
- **Don't** use `--color-ink-faint` for text. It is 2.9:1 — below the
  4.5:1 body floor — and reserved for non-text decoration.
- **Don't** build a donut/pie chart on this system. Use a stacked bar
  plus a data table.
- **Don't** add a dark theme. The world is committed to a single lit-pad
  appearance.
- **Don't** hide a load-bearing column (occupancy source, % occupied)
  behind a breakpoint without a visible affordance — the mobile schedule
  states explicitly what is hidden and why, rather than truncating
  silently.
