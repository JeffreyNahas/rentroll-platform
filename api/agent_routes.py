"""POST /agent/ask -- the dashboard's command dock, and (later) the evals
entrypoint over HTTP. Thin: all the real work (tool-use loop, grounding
check) lives in `agent/`; this module only shapes the request/response.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from agent.run import answer as agent_answer

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
