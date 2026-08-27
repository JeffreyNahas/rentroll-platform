# dashboard-app

The dashboard for **Rent Roll Intelligence** — a reconciled, source-cited
view of 25 mixed-use properties from 50 Yardi Voyager exports, plus a
tool-use agent chat docked to the sheet's bottom edge.

Part of the [rentroll-platform](../) repo; see the root `CLAUDE.md` and
`STATUS.md` for the project as a whole. This directory is just the
Next.js frontend — it talks to the FastAPI backend in `../api/` and,
through it, the agent in `../agent/`.

## Tech stack

- **Next.js 16** (App Router) + **React 19** + **TypeScript**
- **Tailwind CSS v4** — no component library; every chart and mark is
  hand-drawn CSS/SVG (see `DESIGN.md` at the repo root for why)
- Server components fetching from the API on render (`revalidate: 60`);
  `LeasesTable` and `CommandDock` are the only client components

## Running

Needs the API running first:

```bash
make api        # from the repo root, one terminal — :8000
make dashboard  # another terminal — :3000
```

Or directly:

```bash
npm install
npm run dev
```

`.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## Project structure

```
dashboard-app/src/
  app/
    layout.tsx        # sheet frame, direction contract, command dock
    globals.css        # tokens, sheet primitives, validator record
    page.tsx           # portfolio sheet
    properties/[code]/page.tsx
  components/
    LeasesTable.tsx     # client — section toggle + pagination
    sheet/
      Glyph.tsx         # the drawn legend: one 16-unit box, one 1.25 stroke
      Marks.tsx         # SourceMark, TypeKey, SourcesMark
      TitleBlock.tsx    # ruled field grid
      Register.tsx      # section divider + ScaleBar
      Revisions.tsx     # RevisionMargin, SheetNotes
      Charts.tsx        # occupancy, expirations, charge mix
      CommandDock.tsx    # client — the agent's chat input
      AgentTranscript.tsx # printed Q/A log, docked above the command line
  lib/                  # api.ts, types.ts, format.ts
```

Full spec: `docs/dashboard.md` (pages, component vocabulary) and
`DESIGN.md` (visual system, tokens) at the repo root.

## Scripts

- `npm run dev` — dev server (Turbopack)
- `npm run build` — production build
- `npm run start` — production server
- `npm run lint` — ESLint
- `npm run format` / `npm run format:check` — Prettier
