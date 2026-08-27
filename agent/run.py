"""Public entrypoints: `answer(question, history)` and
`answer_stream(question, history)`. Used by `api/agent_routes.py` (the
dashboard's command dock, streaming) and, later, the evals harness
(`answer`, plain -- kept import-only, no FastAPI/HTTP dependency here).

Orchestrates the tool-use loop (`agent/client.py`) and the numeric
grounding check (`agent/grounding.py`): one retry with a corrective
instruction, then fail closed per CLAUDE.md design rule #1.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from agent import grounding
from agent.client import TOOL_BUDGET_MESSAGE, run_conversation_stream

UNVERIFIABLE_MESSAGE = "I can't verify that figure from the data."
UNAVAILABLE_MESSAGE = "I ran into a problem answering that -- try again in a moment."
MAX_GROUNDING_RETRIES = 1

# Answers that already are a controlled failure -- never re-check or
# overwrite these with the fail-closed message.
_TERMINAL_ANSWERS = {TOOL_BUDGET_MESSAGE, UNVERIFIABLE_MESSAGE}


@dataclass
class AgentResponse:
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def _collect_sources_and_warnings(
    tool_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_sources: set[tuple[Any, Any]] = set()
    seen_warnings: set[tuple[Any, Any]] = set()

    for result in tool_results:
        for s in result.get("sources") or []:
            key = (s.get("snapshot_id"), s.get("report_type"))
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append(s)
        for w in result.get("warnings") or []:
            key = (w.get("code"), w.get("message"))
            if key not in seen_warnings:
                seen_warnings.add(key)
                warnings.append(w)

    return sources, warnings


def answer_stream(
    question: str, history: list[dict[str, str]] | None = None
) -> Iterator[dict[str, Any]]:
    """Forwards `run_conversation_stream`'s progress events live, adds its
    own `status` event around a grounding retry, and always ends in one
    terminal `done` event -- `{"type": "done", "answer", "sources",
    "warnings", "tool_calls"}` -- even on an exception, so a caller
    reading the stream never has to handle a bare connection drop."""
    try:
        messages: list[dict] = list(history or [])
        messages.append({"role": "user", "content": question})

        text = ""
        tool_results: list[dict] = []
        trace: list[dict] = []
        for event in run_conversation_stream(list(messages)):
            if event["type"] == "final":
                text = event["text"]
                tool_results = event["tool_results"]
                trace = event["trace"]
            else:
                yield event

        retries = 0
        while text not in _TERMINAL_ANSWERS and retries < MAX_GROUNDING_RETRIES:
            ungrounded = grounding.find_ungrounded(text, tool_results)
            if not ungrounded:
                break
            yield {"type": "status", "message": "Double-checking the numbers…"}
            correction = (
                "The figure(s) "
                + ", ".join(f"{v:g}" for v in ungrounded)
                + " in your last answer do not appear in any tool result. "
                "Restate your answer using only figures actually returned "
                "by a tool call, or say you cannot verify them."
            )
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": correction})

            more_results: list[dict] = []
            more_trace: list[dict] = []
            for event in run_conversation_stream(list(messages)):
                if event["type"] == "final":
                    text = event["text"]
                    more_results = event["tool_results"]
                    more_trace = event["trace"]
                else:
                    yield event
            tool_results = tool_results + more_results
            trace = trace + more_trace
            retries += 1

        if text not in _TERMINAL_ANSWERS and grounding.find_ungrounded(text, tool_results):
            text = UNVERIFIABLE_MESSAGE

        sources, warnings = _collect_sources_and_warnings(tool_results)
        yield {
            "type": "done",
            "answer": text,
            "sources": sources,
            "warnings": warnings,
            "tool_calls": trace,
        }
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        yield {
            "type": "done",
            "answer": UNAVAILABLE_MESSAGE,
            "sources": [],
            "warnings": [],
            "tool_calls": [],
        }


def answer(question: str, history: list[dict[str, str]] | None = None) -> AgentResponse:
    """Non-streaming convenience wrapper -- drains `answer_stream` and
    returns its `done` event as an `AgentResponse`. Progress/error events
    are discarded; this is what evals should call."""
    done: dict[str, Any] = {}
    for event in answer_stream(question, history):
        if event["type"] == "done":
            done = event
    return AgentResponse(
        answer=done["answer"],
        sources=done["sources"],
        warnings=done["warnings"],
        tool_calls=done["tool_calls"],
    )
