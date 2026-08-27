"""POST /agent/ask -- the plain-JSON entrypoint (evals, curl, docs
examples) -- and POST /agent/ask/stream -- the dashboard's command dock,
Server-Sent Events. Thin: all the real work (tool-use loop, grounding
check) lives in `agent/`; this module only shapes the request/response.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.run import answer as agent_answer
from agent.run import answer_stream as agent_answer_stream

router = APIRouter()


class AgentMessage(BaseModel):
    role: str
    content: str


class AgentAskRequest(BaseModel):
    question: str
    history: list[AgentMessage] = []


@router.post("/agent/ask", summary="Ask the portfolio a question")
def agent_ask(body: AgentAskRequest) -> dict:
    """Runs the tool-use loop and the numeric grounding check, then
    returns `{answer, sources, warnings, tool_calls}`. `sources` and
    `warnings` are the union of every tool call's own envelope fields for
    this turn -- the agent doesn't invent its own citation logic."""
    history = [{"role": m.role, "content": m.content} for m in body.history]
    result = agent_answer(body.question, history)
    return asdict(result)


@router.post(
    "/agent/ask/stream",
    summary="Ask the portfolio a question, with live tool-call progress",
)
def agent_ask_stream(body: AgentAskRequest) -> StreamingResponse:
    """Server-Sent Events. Each event is one line `data: {...}\\n\\n` with
    a JSON body carrying `type`:

    - `tool_start` / `tool_done` -- a named tool is about to run / just
      finished (`tool`, `label`, and for `tool_done` an `ok` flag).
    - `status` -- a free-text progress note (currently only emitted around
      a grounding retry).
    - `error` -- something went wrong; always followed by a `done` event,
      never a bare dropped connection.
    - `done` -- terminal event, always exactly one per request:
      `{answer, sources, warnings, tool_calls}`, same shape `/agent/ask`
      returns in one shot.
    """
    history = [{"role": m.role, "content": m.content} for m in body.history]

    def event_stream():
        for event in agent_answer_stream(body.question, history):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
