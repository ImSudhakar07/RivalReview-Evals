"""
eval_4_4_retry_rate.py
-----------------------
Eval 4.4 — Retry Rate

Layer:   4
EVAL_TAG = "reliability"
Type:    Programmatic
Source:  AgentMetrics table

WHAT WE CHECK:
We count how many Grok calls were made per agent per project run.
If an agent made more calls than expected it means retries happened.

Expected calls per project run:
  monthly_batch_agent:  1 call per app per month (N apps x M months)
  app_synthesis_agent:  1 call per app
  cross_app_agent:      1 call total

If actual calls exceed expected by more than 50% retries are happening too often.

PASS CRITERIA: No agent exceeds 150% of expected call count (threshold = 1.0)
"""

from collections import defaultdict
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID            = "4.4"
EVAL_NAME          = "Retry Rate"
LAYER              = 4
MAX_RETRY_RATIO    = 1.5   # 150% of expected = too many retries


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

    # Count calls per agent
    call_counts: dict[str, int] = defaultdict(int)
    for metric in metrics:
        call_counts[metric.agent_name] += 1

    # Calculate expected calls
    num_apps   = len(app_analyses)

    # Count unique months across all apps
    all_months = set()
    for app in app_analyses:
        batches = app.get("monthly_batches", {})
        if isinstance(batches, dict):
            all_months.update(batches.keys())
    num_months = max(len(all_months), 1)

    expected_calls = {
        "monthly_batch_agent": num_apps * num_months,
        "app_synthesis_agent": num_apps,
        "cross_app_agent":     1,
    }

    for agent_name, expected in expected_calls.items():
        actual  = call_counts.get(agent_name, 0)
        ratio   = actual / expected if expected > 0 else 0
        passed  = ratio <= MAX_RETRY_RATIO

        if actual == 0:
            result.skipped += 1
            result.details.append({
                "item_id":  agent_name,
                "passed":   False,
                "expected": expected,
                "actual":   actual,
                "note":     f"No calls found for {agent_name}",
            })
            continue

        if passed:
            result.passed += 1
        else:
            result.failed += 1

        retries = max(0, actual - expected)
        result.details.append({
            "item_id":  agent_name,
            "passed":   passed,
            "expected": expected,
            "actual":   actual,
            "retries":  retries,
            "note": (
                f"OK — {actual} calls, {retries} retries "
                f"({ratio:.0%} of expected)"
                if passed else
                f"FAIL — {actual} calls vs {expected} expected "
                f"({ratio:.0%}) — too many retries"
            ),
        })

    result.finalise()
    return result.to_dict()