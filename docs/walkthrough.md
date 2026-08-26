# Walkthrough

Read this before the interview. Everything here is about how to present the
work, not how to build it.

---

## The differentiation thesis

Aker's platform page states three engineering principles. Every design
decision in this repo maps to one of them, and that mapping is the pitch.

| Their principle | How this repo implements it |
|---|---|
| **Facts before fluency** | Every number is computed in SQL. The LLM never does arithmetic — it selects tools and narrates results. Enforced by a post-response numeric grounding check. |
| **Evidence before assertion** | Every fact row carries `source_row` and `snapshot_id`; every API and agent response carries citations back to file and row. |
| **Governance before action** | Read-only DB role, SQL AST validation, row caps, 5s statement timeout, full query audit log. |

Plus an **eval harness** — golden question set, tool-trajectory scoring,
exact numeric checks. The interviewer said their team is still figuring out
evals, so this is the highest-leverage thing in the submission.

**Demo one-liner:**
*"I didn't build a dashboard with a chatbot bolted on. I built a governed
semantic layer over the rent roll and gave an agent read-only tools on top
of it — so every number traces to a row in a file you sent me, and I can
prove the agent's accuracy with a regression suite."*

---

## Talking points

1. 50 files profiled before any parser was written — the portfolio turned
   out to be mixed-use with three different rent structures.
2. Only `AMENITY` is shared across all property types; commercial has no
   `RENT` code. A naive query would have silently zeroed five properties.
3. Snapshot grain, and re-running `make load` is a no-op via file hash.
4. The nested charge-row parser — hardest part of the format.
5. Two-tier reconciliation: 4,106 per-lease checks across 25/25 files.
6. 4,006 current leases = 4,006 units, from two independently generated
   reports.
7. Ask the agent something that trips the numeric grounding guard; let it
   fail closed.
8. Open `evals/report.md`: *"this is how I'd know if a prompt change made
   it worse."*

**Close with:**
*"The constraint I set myself was that the LLM never produces a number — it
routes to SQL and narrates. That's why every figure on screen traces to a
row in a file you sent me."*

---

## Cut list, if time runs short

In order: Next.js → Streamlit · drop the `run_readonly_sql` escape hatch ·
drop CI · drop PII masking · eval set 25 → 8 questions.

**Never cut:** reconciliation, provenance columns, the README data-quality
section, or a minimal eval set. Those are the differentiators; everything
else is table stakes.

---

## Version control

Five branches, five PRs, squash-merged so `main` reads as one commit per
stage:

| Branch | Contents |
|---|---|
| `feat/schema-and-infra` | docker-compose, Makefile, migrations, DDL ✅ merged |
| `feat/ingestion` | parsers, models, loader, reconciliation ← current |
| `feat/api-and-dashboard` | gold views, FastAPI, frontend |
| `feat/agent` | toolbelt, SQL guard, citations, grounding check |
| `feat/evals` | golden set, scoring, report |

PR descriptions carry the *why* and the trade-offs — they're artifacts to
open during the walkthrough, not bookkeeping. Tag the submitted state
`v1.0-submission`.
