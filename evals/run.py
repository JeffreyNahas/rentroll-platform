"""The eval runner. `python -m evals.run` (also `make eval`).

For each golden question: call `agent.run.answer()` directly (no HTTP --
that's the whole reason `agent.run.answer()` was kept import-only and
FastAPI-free), score tool trajectory (exact set match) and semantic
accuracy (`evals/judge.py`), write `evals/report.md` + `evals/report.json`.

Needs `make api` running -- the agent's tools call the API over HTTP even
though this runner doesn't.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass

from agent.run import answer
from evals.golden_set import GOLDEN_QUESTIONS, GoldenQuestion
from evals.judge import judge_answer

REPORT_DIR = os.path.dirname(__file__)


@dataclass
class EvalResult:
    id: str
    question: str
    expected_tools: list[str]
    actual_tools: list[str]
    trajectory_pass: bool
    answer: str
    expected_facts: str
    semantic_pass: bool
    semantic_reason: str


def run_one(q: GoldenQuestion) -> EvalResult:
    response = answer(q.question)
    actual_tools = frozenset(tc["tool"] for tc in response.tool_calls)
    trajectory_pass = actual_tools == q.expected_tools
    semantic_pass, reason = judge_answer(q.question, q.expected_facts, response.answer)
    return EvalResult(
        id=q.id,
        question=q.question,
        expected_tools=sorted(q.expected_tools),
        actual_tools=sorted(actual_tools),
        trajectory_pass=trajectory_pass,
        answer=response.answer,
        expected_facts=q.expected_facts,
        semantic_pass=semantic_pass,
        semantic_reason=reason,
    )


def run_all() -> list[EvalResult]:
    results = []
    for i, q in enumerate(GOLDEN_QUESTIONS, 1):
        print(f"[{i}/{len(GOLDEN_QUESTIONS)}] {q.id} ... ", end="", flush=True)
        result = run_one(q)
        traj = "PASS" if result.trajectory_pass else "FAIL"
        sem = "PASS" if result.semantic_pass else "FAIL"
        print(f"trajectory={traj} semantic={sem}")
        results.append(result)
    return results


def write_reports(results: list[EvalResult]) -> None:
    n = len(results)
    n_traj = sum(r.trajectory_pass for r in results)
    n_sem = sum(r.semantic_pass for r in results)
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    agent_model = os.environ.get("AGENT_MODEL", "claude-haiku-4-5")
    judge_model = os.environ.get("EVAL_JUDGE_MODEL", agent_model)

    json_path = os.path.join(REPORT_DIR, "report.json")
    with open(json_path, "w") as f:
        json.dump(
            {
                "generated_at": generated_at,
                "agent_model": agent_model,
                "judge_model": judge_model,
                "summary": {
                    "trajectory_passed": n_traj,
                    "semantic_passed": n_sem,
                    "total": n,
                },
                "results": [asdict(r) for r in results],
            },
            f,
            indent=2,
        )

    lines = [
        "# Evals Report",
        "",
        f"Generated: {generated_at}",
        f"Agent model: `{agent_model}` · Judge model: `{judge_model}`",
        "",
        "## Summary",
        "",
        f"- Tool trajectory: {n_traj}/{n} passed",
        f"- Semantic accuracy: {n_sem}/{n} passed",
        "",
        (
            "**Note:** the agent is non-deterministic (default temperature) -- "
            "this is a single-sample snapshot, not a statistically stable "
            "score. Re-running can change individual results; a question "
            "failing once doesn't necessarily mean it fails consistently. "
            "Multi-sample scoring (N repeats per question, reported as a "
            "pass rate) is a natural next step, not built here."
        ),
        "",
        "## Per-question results",
        "",
        "| ID | Trajectory | Semantic | Notes |",
        "|---|---|---|---|",
    ]
    for r in results:
        traj_mark = "✅" if r.trajectory_pass else "❌"
        sem_mark = "✅" if r.semantic_pass else "❌"
        note = ""
        if not r.trajectory_pass:
            note = f"expected `{{{', '.join(r.expected_tools)}}}`, got `{{{', '.join(r.actual_tools)}}}`"
        lines.append(f"| {r.id} | {traj_mark} | {sem_mark} | {note} |")

    lines += ["", "## Details", ""]
    for r in results:
        lines += [
            f"### {r.id}",
            "",
            f"**Question:** {r.question}",
            "",
            (
                f"**Expected tools:** `{{{', '.join(r.expected_tools)}}}` · "
                f"**Actual tools:** `{{{', '.join(r.actual_tools)}}}`"
            ),
            "",
            f"**Answer:** {r.answer}",
            "",
            f"**Judge reason:** {r.semantic_reason}",
            "",
        ]

    md_path = os.path.join(REPORT_DIR, "report.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nWrote {md_path} and {json_path}")
    print(f"Tool trajectory: {n_traj}/{n} passed")
    print(f"Semantic accuracy: {n_sem}/{n} passed")


def main() -> int:
    results = run_all()
    write_reports(results)
    n = len(results)
    n_traj = sum(r.trajectory_pass for r in results)
    n_sem = sum(r.semantic_pass for r in results)
    return 0 if (n_traj == n and n_sem == n) else 1


if __name__ == "__main__":
    sys.exit(main())
