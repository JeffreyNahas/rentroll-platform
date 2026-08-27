"""The Anthropic tool-use loop: send messages + tool schemas, dispatch
whatever tool_use blocks come back via `agent/tools.py`, feed the results
back, repeat until the model returns a final text answer.

No raw text-to-SQL (CLAUDE.md design rule #2): the model only ever sees
the named tools in `agent.tools.TOOL_SPECS` plus the guarded escape hatch.
"""

from __future__ import annotations

import json
import os
import time

import anthropic
from dotenv import load_dotenv

from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOL_SPECS, call_tool

load_dotenv()

MAX_TOOL_ROUNDS = 6
TOOL_BUDGET_MESSAGE = (
    "I wasn't able to finish gathering data for that question within the "
    "tool budget. Try narrowing it -- one property or one metric at a time."
)

_client: anthropic.Anthropic | None = None


def _client_instance() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _model() -> str:
    return os.environ.get("AGENT_MODEL", "claude-haiku-4-5")


def run_conversation(
    messages: list[dict],
) -> tuple[str, list[dict], list[dict]]:
    """Drive `messages` to a final text answer, appending the assistant/
    tool exchange to `messages` along the way. Callers that don't want
    that exchange kept (e.g. a grounding retry starting a cleaner
    conversation) should pass a copy.

    Returns (answer_text, tool_results, tool_call_trace) -- both lists
    scoped to this call only.
    """
    tool_results: list[dict] = []
    trace: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = _client_instance().messages.create(
            model=_model(),
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_SPECS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            answer = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return answer, tool_results, trace

        messages.append({"role": "assistant", "content": response.content})

        tool_outputs = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            started = time.perf_counter()
            result = call_tool(block.name, block.input)
            latency_ms = int((time.perf_counter() - started) * 1000)
            tool_results.append(result)
            trace.append(
                {
                    "tool": block.name,
                    "input": block.input,
                    "latency_ms": latency_ms,
                }
            )
            tool_outputs.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                }
            )
        messages.append({"role": "user", "content": tool_outputs})

    return TOOL_BUDGET_MESSAGE, tool_results, trace
