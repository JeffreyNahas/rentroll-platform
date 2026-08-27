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
// the transcript, the transcript's resized height) — the only place in the
// dashboard that isn't a plain server-rendered read, because a question is
// the one thing here that can't be known ahead of a request.

import { useRef, useState, useSyncExternalStore } from "react";
import { askAgentStream } from "@/lib/api";
import type { AgentMessage } from "@/lib/types";
import { AgentTranscript, type TranscriptEntry } from "./AgentTranscript";
import { GlyphEnter } from "./Glyph";

const DEFAULT_HEIGHT = 320; // matches the old fixed max-h-80
const MIN_HEIGHT = 120;
const HEIGHT_STORAGE_KEY = "rri-command-dock-height";

function clampHeight(px: number): number {
  const max = typeof window === "undefined" ? px : window.innerHeight * 0.7;
  return Math.min(Math.max(px, MIN_HEIGHT), max);
}

// A viewer's last chosen height, read via useSyncExternalStore rather than
// useState+useEffect so the server snapshot (DEFAULT_HEIGHT, matching SSR)
// and the client snapshot never fight — no hydration mismatch, and no
// setState-in-effect render either. localStorage doesn't fire a same-tab
// 'storage' event, and this value only needs to be read once per mount
// (drags are tracked separately), so the subscription is a no-op.
function subscribeNoop() {
  return () => {};
}

function readStoredHeight(): number {
  try {
    const stored = window.localStorage.getItem(HEIGHT_STORAGE_KEY);
    const parsed = stored ? Number(stored) : NaN;
    return Number.isFinite(parsed) ? parsed : DEFAULT_HEIGHT;
  } catch {
    return DEFAULT_HEIGHT;
  }
}

function readServerHeight(): number {
  return DEFAULT_HEIGHT;
}

export function CommandDock() {
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);

  const storedHeight = useSyncExternalStore(
    subscribeNoop,
    readStoredHeight,
    readServerHeight
  );
  // Overrides the stored height once the viewer drags the handle this
  // session; null defers to whatever was persisted from a previous visit.
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  const height = clampHeight(dragHeight ?? storedHeight);
  const dragState = useRef<{ startY: number; startHeight: number } | null>(
    null
  );

  function onHandlePointerDown(e: React.PointerEvent) {
    dragState.current = { startY: e.clientY, startHeight: height };

    function onMove(ev: PointerEvent) {
      if (!dragState.current) return;
      // Dragging the handle up grows the transcript, so height moves
      // opposite to pointer delta.
      const delta = dragState.current.startY - ev.clientY;
      setDragHeight(clampHeight(dragState.current.startHeight + delta));
    }

    function onUp() {
      dragState.current = null;
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      setDragHeight((h) => {
        if (h != null) {
          try {
            window.localStorage.setItem(HEIGHT_STORAGE_KEY, String(h));
          } catch {
            // best effort only
          }
        }
        return h;
      });
    }

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

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
    setEntries((prev) => [
      ...prev,
      { question, pending: true, statusLine: "Asking…" },
    ]);

    function updateLast(patch: Partial<TranscriptEntry>) {
      setEntries((prev) =>
        prev.map((e, i) => (i === prev.length - 1 ? { ...e, ...patch } : e))
      );
    }

    let errored = false;

    try {
      await askAgentStream(question, history, (event) => {
        switch (event.type) {
          case "tool_start":
            updateLast({ statusLine: `${event.label}…` });
            break;
          case "status":
            updateLast({ statusLine: event.message });
            break;
          case "error":
            errored = true;
            updateLast({ error: event.message, pending: false });
            break;
          case "done":
            if (!errored) {
              updateLast({
                pending: false,
                statusLine: undefined,
                response: {
                  answer: event.answer,
                  sources: event.sources,
                  warnings: event.warnings,
                  tool_calls: event.tool_calls,
                },
              });
            }
            break;
        }
      });
    } catch (err) {
      updateLast({
        pending: false,
        error:
          err instanceof Error ? err.message : "The agent couldn't be reached.",
      });
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
      {entries.length > 0 && (
        <div
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize the conversation panel"
          onPointerDown={onHandlePointerDown}
          className="border-rule bg-field-sunk group flex h-2.5 cursor-ns-resize touch-none items-center justify-center border-t hover:bg-green-50"
        >
          <span className="bg-rule block h-[2px] w-8 transition-colors group-hover:bg-green-700" />
        </div>
      )}

      <AgentTranscript entries={entries} height={height} />

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
