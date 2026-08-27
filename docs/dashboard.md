# Dashboard

Two pages in `dashboard-app/` — Next.js 16, React 19, TypeScript, Tailwind
v4. Server components fetch from FastAPI on render (`revalidate: 60`); no
client-side data-fetching library.

`make dashboard` runs the dev server on `:3000`. `make api` must be running.

---

## The visual world

The dashboard is designed as an **engineering drawing sheet**. That is not
decoration — it is the design rules in `CLAUDE.md` made structural:

| Drawing device | The rule it carries |
|---|---|
| **Title block** — ruled grid of labelled fields at the top of every sheet | Rule #3. A figure and its provenance arrive together. This is also what replaced the KPI card strip: portfolio totals are title-block fields, not five floating tiles. |
| **Revision margin** — numbered redline triangles down the right side | Rule #6. The three source contradictions and the unclassified-unit rollups are read *before* the data, not hidden in a panel at the bottom. |
| **Hatched field** — a ruled-through panel where a value is out of scope | "By design, not by data loss." Commercial loss-to-lease is not a missing number; it is a number that never existed. A grey dash cannot say that. |
| **Hatch as the property-type key** | Type is keyed by texture (solid / ruled / diagonal / stipple / open) the way a plat or Sanborn map keys land use. This frees hue for the data. |
| **Shared scale bar** across the schedule | Rule #4. A 775-unit complex and a three-unit retail strip are drawn to one scale so they look incommensurable before you read a figure. |
| **Command line** docked to the sheet's bottom edge | Where the agent lands. A drafting application has always had one there. |

The direction contract is an HTML comment emitted at the top of `<body>`
(`DIRECTION_CONTRACT` in `layout.tsx`), greppable in the production build
by its seed key `c0872ef5`.

**Structure comes from ruled register and void — there is no card, no card
border, and no drop shadow anywhere in the system.** If you find yourself
reaching for one, the register (`components/sheet/Register.tsx`) is the
divider you want.

### Ground and ink

Off-white engineering-pad stock under a printed pale-green grid. Green is
ground and structure and **carries no status meaning**; redline is reserved
for the deviation system so it never doubles as a data series.

| Token | Value | Contrast on field |
|---|---|---|
| `--color-field` | `#f4f2e9` | the drawing area |
| `--color-sheet` | `#e9e7dc` | the board beneath |
| `--color-ink` | `#1b211c` | 14.6:1 |
| `--color-ink-2` | `#4a5449` | 7.1:1 |
| `--color-ink-3` | `#5f6a5a` | 5.1:1 |
| `--color-ink-faint` | `#8a9184` | 2.9:1 — **non-text only** |
| `--color-redline` | `#b0442e` | 5.0:1 |
| `--color-amber` | `#955714` | 5.1:1 |

Light only, deliberately: the world is a lit paper pad, and the surface's
real use scene is a narrated screen-share in a bright room.

### Chart palette

Six series inks, fixed order, never cycled. Validated against the shipped
surface — re-run this whenever `--color-field` moves:

```bash
node scripts/validate_palette.js \
  "#1F5FA9,#D2601A,#00938A,#C99000,#7B4B9E,#4C7A22" \
  --mode light --surface "#f4f2e9"
```

All checks pass; worst adjacent CVD ΔE 13.8, normal-vision ΔE 22.1. Ochre
(`--color-s4`) sits at 2.51:1, so any chart using it ships direct labels
**and** a table view — that is the validator's relief rule, not a
preference. Do not add a seventh hue without re-running the validator.

Property type in the expirations chart uses a three-slot subset validated
all-pairs (`#1F5FA9,#00938A,#D2601A`, worst all-pairs CVD ΔE 14.0).

---

## Pages

### `/` — the portfolio sheet

1. **Title block** — sheet, snapshot, source count, properties, units,
   occupied *as a count*, base rent billed, deviations. There is no
   portfolio occupancy percentage here or anywhere else (rule #4); the
   field is labelled "Counted, not averaged."
2. **Property schedule** — 25 rows, largest first, each with its type
   hatch, occupancy-source mark, shared-scale size bar, and % occupied.
   Below `lg` the size, units and occ/rentable columns drop out so code,
   source and % occupied stay visible without a sideways scroll.
3. **Occupancy by type** — one bar per type, single hue, with a hairline
   marking occupancy including notice. The only place a percentage lives.
4. **Expirations · 12 months** — stacked by property type, because a
   commercial renewal and a 300-unit residential renewal are different
   work.
5. **Revision margin** — sticky at `xl`, every deviation with the note the
   API wrote.

### `/properties/[code]` — a property sheet

Same grammar at a deeper zoom: title block (including the occupancy-source
field), loss to lease (or the hatched out-of-scope panel), delinquency,
charge mix, and the leases table with a current/future toggle and
pagination. Residents render as `Resident #N` (rule #8).

---

## Charts are drawn, not imported

Tremor was removed. A stock chart library inside a committed world drags a
second design system onto the sheet — its rounded cards, its default blue,
its own type scale. Every mark in `components/sheet/Charts.tsx` is CSS or
SVG, every hover is CSS, and **none of it ships client JavaScript**. This
also deleted the Tailwind v4 `@source inline()` safelist Tremor needed.

**Charge mix is a stacked bar, not a donut.** Eight categories where base
rent is ~90% of the total is the documented donut anti-pattern — seven
near-identical slivers around one dominant arc. Base rent takes graphite
rather than a series ink, so the ~8% that actually varies gets the colour.
The bar is suppressed entirely below two categories, where a full-width
slab would read as a redaction bar.

---

## File layout

```
dashboard-app/src/
  app/
    layout.tsx        # sheet frame, direction contract, command dock
    globals.css       # tokens, sheet primitives, validator record
    page.tsx          # portfolio sheet
    properties/[code]/page.tsx
  components/
    LeasesTable.tsx   # client — section toggle + pagination
    sheet/
      Glyph.tsx       # the drawn legend: one 16-unit box, one 1.25 stroke
      Marks.tsx       # SourceMark, TypeKey, SourcesMark
      TitleBlock.tsx  # ruled field grid
      Register.tsx    # section divider + ScaleBar
      Revisions.tsx   # RevisionMargin, SheetNotes
      Charts.tsx      # occupancy, expirations, charge mix
      CommandDock.tsx # client — the agent's chat input
      AgentTranscript.tsx # printed Q/A log, docked above the command line
  lib/                # api.ts, types.ts, format.ts
```

`LeasesTable` and `CommandDock` are the only client components. `LeasesTable`
owns the section toggle and pagination but the data still comes from the
server; `CommandDock` owns live request state for `POST /agent/ask` -- the
one place in the dashboard where a question can't be known ahead of a
request, so it can't be a server component.

**Every meaning is carried by a drawn mark first and colour second.** No
Unicode glyph or emoji stands in for an icon. When you add a state, add it
to `Glyph.tsx` on the same 16-unit box at the same stroke weight.

---

## Running

```bash
make api        # one terminal
make dashboard  # another; :3000
```

`dashboard-app/.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## Not built

- Sortable schedule columns, CSV export.
- Dynamic agent-authored charts, pin-to-canvas.

The command dock's chat is live as of `agent/` shipping (see `docs/agent.md`)
-- `CommandDock.tsx` posts to `POST /agent/ask` and `AgentTranscript.tsx`
prints the answer, sources, and warnings above the input, in the same
ruled/monospace vocabulary as the rest of the sheet.
