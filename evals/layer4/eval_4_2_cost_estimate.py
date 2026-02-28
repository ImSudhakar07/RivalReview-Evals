"""
eval_4_2_cost_estimate.py
--------------------------
Eval 4.2 — Cost Per Run

Layer:   4
EVAL_TAG = "cost"
Type:    Programmatic
Source:  AgentMetrics table

WHAT WE CHECK:
Total cost for one full project run should be under $2.00.
Per-agent cost breakdown is shown for visibility.

Pricing used:
  Input:  $0.20 per million tokens
  Output: $0.50 per million tokens

PASS CRITERIA: Total run cost under $2.00 (threshold = 1.0 — binary pass/fail)
"""

from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID       = "4.2"
EVAL_NAME     = "Cost Per Run"
LAYER         = 4
MAX_COST_USD  = 2.00


def run(app_analyses: list[dict], analyses: list[dict], metrics: list = None) -> dict:
    result = EvalResult(
        eval_id   = EVAL_ID,
        name      = EVAL_NAME,
        layer     = LAYER,
        threshold = THRESHOLDS[EVAL_ID],
    )

    if not metrics:
        result.error = "No AgentMetrics records found."
        return result.to_dict()

    # Aggregate cost per agent
    agent_costs: dict[str, float] = {}
    total_cost = 0.0

    for metric in metrics:
        agent_name  = metric.agent_name
        cost        = metric.cost_usd or 0.0
        total_cost += cost
        agent_costs[agent_name] = agent_costs.get(agent_name, 0.0) + cost

    # One entry per agent showing their total cost
    for agent_name, cost in sorted(agent_costs.items()):
        result.details.append({
            "item_id": agent_name,
            "passed":  True,
            "cost":    round(cost, 6),
            "note":    f"${cost:.4f} total for {agent_name}",
        })

    # Overall pass/fail
    total_cost = round(total_cost, 6)
    passed     = total_cost <= MAX_COST_USD

    result.details.append({
        "item_id": "TOTAL",
        "passed":  passed,
        "cost":    total_cost,
        "note": (
            f"OK — total cost ${total_cost:.4f} under ${MAX_COST_USD:.2f} limit"
            if passed else
            f"FAIL — total cost ${total_cost:.4f} exceeds ${MAX_COST_USD:.2f} limit"
        ),
    })

    if passed:
        result.passed += 1
    else:
        result.failed += 1

    result.finalise()
    return result.to_dict()