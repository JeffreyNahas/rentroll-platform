"""Public entrypoint: `answer(question, history)`. Used by
`api/agent_routes.py` (the dashboard's command dock) and, later, the
evals harness -- kept import-only, no FastAPI/HTTP dependency here.

Orchestrates the tool-use loop (`agent/client.py`) and the numeric
grounding check (`agent/grounding.py`): one retry with a corrective
instruction, then fail closed per CLAUDE.md design rule #1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent import grounding
from agent.client import TOOL_BUDGET_MESSAGE, run_conversation

UNVERIFIABLE_MESSAGE = "I can't verify that figure from the data."
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


def answer(question: str, history: list[dict[str, str]] | None = None) -> AgentResponse:
    messages: list[dict] = list(history or [])
    messages.append({"role": "user", "content": question})

    text, tool_results, trace = run_conversation(list(messages))

    retries = 0
    while text not in _TERMINAL_ANSWERS and retries < MAX_GROUNDING_RETRIES:
        ungrounded = grounding.find_ungrounded(text, tool_results)
        if not ungrounded:
            break
        correction = (
            "The figure(s) "
            + ", ".join(f"{v:g}" for v in ungrounded)
            + " in your last answer do not appear in any tool result. "
            "Restate your answer using only figures actually returned "
            "by a tool call, or say you cannot verify them."
        )
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": correction})
        text, more_results, more_trace = run_conversation(list(messages))
        tool_results = tool_results + more_results
        trace = trace + more_trace
        retries += 1

    if text not in _TERMINAL_ANSWERS and grounding.find_ungrounded(text, tool_results):
        text = UNVERIFIABLE_MESSAGE

    sources, warnings = _collect_sources_and_warnings(tool_results)
    return AgentResponse(
        answer=text, sources=sources, warnings=warnings, tool_calls=trace
    )
