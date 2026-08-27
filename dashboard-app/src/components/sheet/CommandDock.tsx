"use client";

// The command line, pinned to the sheet's bottom edge.
//
// A drafting application has always had a command line along the bottom of
// the sheet, so the conversation surface gets a home that belongs to this
// world rather than a chat bubble bolted onto the side. Answers print into
// AgentTranscript, docked directly above the input, in the same ruled/
// monospace vocabulary as the rest of the sheet.
//
// Client component because it owns live request state (in-flight, history,
// the transcript) — the only place in the dashboard that isn't a plain
// server-rendered read, because a question is the one thing here that
// can't be known ahead of a request.

import { useState } from "react";
import { askAgent } from "@/lib/api";
import type { AgentMessage } from "@/lib/types";
import { AgentTranscript, type TranscriptEntry } from "./AgentTranscript";
import { GlyphEnter } from "./Glyph";

export function CommandDock() {
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);

  async function ask(question: string) {
    const history: AgentMessage[] = entries.flatMap((e) =>
      e.response
        ? [
            { role: "user" as const, content: e.question },
            { role: "assistant" as const, content: e.response.answer },
          ]
        : []
    );

    setPending(true);
    setEntries((prev) => [...prev, { question, pending: true }]);

    try {
      const response = await askAgent(question, history);
      setEntries((prev) =>
        prev.map((e, i) => (i === prev.length - 1 ? { question, response } : e))
      );
    } catch (err) {
      setEntries((prev) =>
        prev.map((e, i) =>
          i === prev.length - 1
            ? {
                question,
                error:
                  err instanceof Error
                    ? err.message
                    : "The agent couldn't be reached.",
              }
            : e
        )
      );
    } finally {
      setPending(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const question = value.trim();
    if (!question || pending) return;
    setValue("");
    void ask(question);
  }

  return (
    <div data-dock className="sticky bottom-0 z-20">
      <AgentTranscript entries={entries} />

      <form
        onSubmit={onSubmit}
        className="border-rule-strong bg-field-sunk border-t"
      >
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5 md:px-6">
          <span className="text-green-700" aria-hidden="true">
            <svg
              viewBox="0 0 16 16"
              width="13"
              height="13"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.6}
              strokeLinecap="square"
            >
              <path d="M2.5 3 L7 8 L2.5 13" />
              <path d="M8.5 13 L13.5 13" />
            </svg>
          </span>

          <label htmlFor="ask" className="sr-only">
            Ask the portfolio a question
          </label>
          <input
            id="ask"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={pending}
            placeholder="Ask the portfolio — “which properties are on a derived occupancy source, and why?”"
            className="text-ink placeholder:text-ink-3 min-w-0 flex-1 border-0 bg-transparent font-mono text-[0.8125rem] outline-none disabled:cursor-not-allowed"
          />

          {pending ? (
            <span className="letter text-amber flex items-center gap-1.5 whitespace-nowrap">
              <span className="bg-amber inline-block size-1.5 rounded-full" />
              Asking…
            </span>
          ) : (
            <button
              type="submit"
              disabled={!value.trim()}
              className="letter text-ink-3 inline-flex items-center gap-1.5 whitespace-nowrap transition-colors hover:text-green-700 disabled:pointer-events-none disabled:opacity-40"
            >
              Ask
              <GlyphEnter />
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
