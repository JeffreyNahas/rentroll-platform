"""Semantic-accuracy judge: one Anthropic call per golden question,
comparing the agent's actual answer against `GoldenQuestion.expected_facts`.

Self-contained -- constructs its own client rather than reaching into
`agent/client.py`'s private `_client_instance`, so `evals/` doesn't
depend on `agent/`'s internals, only its public `agent.run.answer()`.

Structured output via a forced tool call (the same tool-use mechanism
`agent/` already uses to talk to the model) rather than asking for JSON
in prose and hoping -- one `response.content[0].input` read, no parsing
of free text.
"""

from __future__ import annotations

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

_VERDICT_TOOL = {
    "name": "record_verdict",
    "description": "Record whether the actual answer semantically satisfies the expected facts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "correct": {
                "type": "boolean",
                "description": (
                    "True if the actual answer conveys the expected facts "
                    "-- tolerant of different wording/formatting, but "
                    "strict about substance: figures, framing, refusals."
                ),
            },
            "reason": {
                "type": "string",
                "description": "One sentence explaining the verdict.",
            },
        },
        "required": ["correct", "reason"],
    },
}

JUDGE_SYSTEM_PROMPT = """\
You are grading one answer from a real-estate portfolio Q&A agent \
against a reference description of what a correct answer must convey. \
Judge substance, not phrasing -- different wording, formatting, or \
ordering is fine. Judge strictly on: are the stated figures right, does \
it frame the answer the way the reference requires (e.g. declining to \
blend metrics, citing an out-of-scope reason, masking a name), and does \
it avoid claiming something the reference says it must not claim. \
Call record_verdict with your judgment."""


def _client_instance() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _model() -> str:
    return os.environ.get(
        "EVAL_JUDGE_MODEL", os.environ.get("AGENT_MODEL", "claude-haiku-4-5")
    )


def judge_answer(
    question: str, expected_facts: str, actual_answer: str
) -> tuple[bool, str]:
    """Returns (correct, reason)."""
    response = _client_instance().messages.create(
        model=_model(),
        max_tokens=256,
        system=JUDGE_SYSTEM_PROMPT,
        tools=[_VERDICT_TOOL],
        tool_choice={"type": "tool", "name": "record_verdict"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Question asked: {question}\n\n"
                    f"Expected facts (reference): {expected_facts}\n\n"
                    f"Actual answer: {actual_answer}"
                ),
            }
        ],
    )
    block = next(b for b in response.content if b.type == "tool_use")
    return bool(block.input["correct"]), str(block.input["reason"])
