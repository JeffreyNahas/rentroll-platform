import type { Metadata } from "next";
import Link from "next/link";
import { Archivo_Narrow, Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { CommandDock } from "@/components/sheet/CommandDock";

// Drafting lettering — condensed caps for title-block fields and column
// heads. Prose stays in the workhorse sans; every figure is mono and tabular,
// because these are measurements that must align in columns.
const archivoNarrow = Archivo_Narrow({
  variable: "--font-archivo-narrow",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Rent Roll Intelligence",
  description:
    "A reconciled, source-cited view of 25 mixed-use properties from 50 Yardi Voyager exports.",
};

const DIRECTION_CONTRACT = `
THESIS: Every panel is a drawing sheet, and no figure appears without a title
block naming its source, its snapshot and its revision state. It refuses the
arrangement this category always ships: KPI tiles floating as rounded white
cards on a grey ground, where a number arrives with no apparatus around it.

OWN-WORLD: Engineering-pad stock (#F4F2E9) under a printed pale-green grid.
Structure from ruled register and void — no card, no card border, no shadow.
Drafting lettering in condensed caps; graphite tabular figures; green is
ground and structure and carries no status; redline is reserved for the
deviation system; six validator-passed inks carry the data.

STORY: The reviewer reads provenance before totals, sees the property types
kept apart rather than averaged, and finds the three source contradictions
redlined in the margin instead of buried at the bottom.

FIRST VIEWPORT: A full-width title block carrying snapshot, source count,
revision state and the portfolio totals as ruled fields; beneath it the
25-property schedule, each row's size drawn to one shared scale; deviations
redlined in the right margin; the ask dock is a command line pinned to the
sheet's bottom edge.

FORM: The Engineering Sheet — candidate 5 of 7, seed key c0872ef5.

FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md, and every shipping raster carrying its
provenance
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${archivoNarrow.variable} ${geistSans.variable} ${geistMono.variable} bg-sheet min-h-screen`}
        // Browser extensions (Grammarly, etc.) inject attributes like
        // data-gr-ext-installed onto <body> before React hydrates. Scoped
        // to this element only -- real hydration bugs in children still warn.
        suppressHydrationWarning
      >
        {/* The direction contract, emitted into the built markup so it can be
            audited after the production build. */}
        <div
          hidden
          aria-hidden="true"
          dangerouslySetInnerHTML={{ __html: `<!--${DIRECTION_CONTRACT}-->` }}
        />

        <div className="mx-auto flex min-h-screen max-w-[1680px] flex-col p-3 md:p-5">
          {/* The sheet: a drawn frame with everything inside it. */}
          <div className="border-rule-strong pad-grid flex flex-1 flex-col border">
            {/* Top edge of the frame — identification, the way a drawing
                sheet names itself along its border. */}
            <div className="border-rule flex items-center justify-between gap-4 border-b px-4 py-2 md:px-6">
              <Link
                href="/"
                className="letter-lg text-ink text-[0.9375rem] transition-colors hover:text-green-700"
              >
                Rent&nbsp;Roll&nbsp;Intelligence
              </Link>
              <div className="letter flex items-center gap-3 md:gap-5">
                <span className="hidden sm:inline">
                  Yardi Voyager · 50 exports
                </span>
                <span className="bg-rule hidden h-3 w-px sm:inline-block" />
                <Link href="/" className="hover:text-ink transition-colors">
                  Sheet index
                </Link>
              </div>
            </div>

            <main className="flex-1 px-4 py-6 md:px-6 md:py-8">{children}</main>

            <CommandDock />
          </div>
        </div>
      </body>
    </html>
  );
}
