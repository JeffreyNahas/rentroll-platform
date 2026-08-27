// The printed Q/A log docked directly above the command line. Same ruled,
// monospace vocabulary as the rest of the sheet — no chat bubbles, no
// avatars, no typing effect. An answer arrives the way a printed slip does:
// all at once, with its sources and notes attached.
//
// Citations and warnings reuse the marks the rest of the dashboard already
// draws (SourcesMark, SheetNotes) rather than inventing a second citation
// language for the agent alone.

import type { AgentAskResponse } from "@/lib/types";
import { SourcesMark } from "./Marks";
import { SheetNotes } from "./Revisions";

export type TranscriptEntry = {
  question: string;
  response?: AgentAskResponse;
  error?: string;
  pending?: boolean;
  // The live tool-call label while pending ("Looking up occupancy…",
  // "Double-checking the numbers…") — falls back to a generic line until
  // the first progress event arrives.
  statusLine?: string;
};

export function AgentTranscript({
  entries,
  height,
}: {
  entries: TranscriptEntry[];
  height: number;
}) {
  if (entries.length === 0) return null;

  return (
    <div
      className="border-rule-strong bg-field overflow-y-auto border-b"
      style={{ height }}
    >
      <ol className="divide-rule divide-y">
        {entries.map((entry, i) => (
          <li key={i} className="px-4 py-3.5 md:px-6">
            <p className="text-ink font-mono text-[0.8125rem]">
              <span className="letter text-ink-3 mr-2.5">Q</span>
              {entry.question}
            </p>

            {entry.pending && (
              <p className="text-ink-3 mt-2 flex items-center gap-1.5 text-[0.8125rem]">
                <span className="bg-amber inline-block size-1.5 shrink-0 animate-pulse rounded-full" />
                {entry.statusLine ?? "Asking…"}
              </p>
            )}

            {entry.error && (
              <p className="text-redline mt-2 text-[0.8125rem]">
                {entry.error}
              </p>
            )}

            {entry.response && (
              <div className="mt-2">
                <p className="text-ink-2 text-[0.8125rem] leading-relaxed whitespace-pre-wrap">
                  <span className="letter text-ink-3 mr-2.5">A</span>
                  {entry.response.answer}
                </p>

                {entry.response.warnings.length > 0 && (
                  <div className="mt-2.5">
                    <SheetNotes warnings={entry.response.warnings} />
                  </div>
                )}

                <div className="mt-2.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
                  <SourcesMark sources={entry.response.sources} />
                  {entry.response.tool_calls.length > 0 && (
                    <span className="letter text-ink-3">
                      via{" "}
                      {entry.response.tool_calls.map((t) => t.tool).join(", ")}
                    </span>
                  )}
                </div>
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
