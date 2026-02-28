"""
eval_4_3_latency.py
--------------------
Eval 4.3 — Latency Per Agent

Layer:   4
EVAL_TAG = "latency"
Type:    Programmatic
Source:  AgentMetrics table

WHAT WE CHECK:
Each agent call should complete within expected time limits.
Calls that exceed the limit indicate timeout risk or API slowness.

Expected max latency per agent:
  monthly_batch_agent:  120 seconds
  app_synthesis_agent:  180 seconds
  cross_app_agent:      120 seconds

PASS CRITERIA: 90% of calls within time limit (threshold = 0.90)
"""

from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "4.3"
EVAL_NAME = "Latency Per Agent"
LAYER     = 4

# Maximum acceptable latency per agent in seconds
MAX_LATENCY = {
    "monthly_batch_agent": 120,
    "app_synthesis_agent": 180,
    "cross_app_agent":     120,
}


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

    for metric in metrics:
        agent_name       = metric.agent_name
        duration_seconds = metric.duration_seconds or 0.0
        item_id          = f"{agent_name} / {metric.called_at.strftime('%Y-%m-%d %H:%M') if metric.called_at else '?'}"

        if agent_name not in MAX_LATENCY:
            result.skipped += 1
            continue

        max_secs = MAX_LATENCY[agent_name]
        passed   = duration_seconds <= max_secs

        if passed:
            result.passed += 1
        else:
            result.failed += 1

        result.details.append({
            "item_id":  item_id,
            "passed":   passed,
            "agent":    agent_name,
            "duration": duration_seconds,
            "note": (
                f"OK — {duration_seconds:.1f}s within {max_secs}s limit"
                if passed else
                f"FAIL — {duration_seconds:.1f}s exceeds {max_secs}s limit"
            ),
        })

    result.finalise()
    return result.to_dict()