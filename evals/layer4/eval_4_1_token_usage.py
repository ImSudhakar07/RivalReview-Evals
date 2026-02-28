"""
eval_4_1_token_usage.py
------------------------
Eval 4.1 — Token Usage Per Agent

Layer:   4
EVAL_TAG = "cost"
Type:    Programmatic
Source:  AgentMetrics table

WHAT WE CHECK:
Each agent call should be within expected token range.
Unusually high token usage indicates prompt bloat or runaway context.
Unusually low usage indicates the agent may have short-circuited.

Expected ranges per agent (empirically set):
  monthly_batch_agent:   1000 - 8000 tokens per call
  app_synthesis_agent:   2000 - 12000 tokens per call
  cross_app_agent:       1000 - 8000 tokens per call

PASS CRITERIA: 90% of calls within expected range (threshold = 0.90)
"""

from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "4.1"
EVAL_NAME = "Token Usage Per Agent"
LAYER     = 4

# Expected total token ranges per agent
TOKEN_RANGES = {
    "monthly_batch_agent":  (1000, 8000),
    "app_synthesis_agent":  (2000, 12000),
    "cross_app_agent":      (1000, 8000),
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
        agent_name   = metric.agent_name
        total_tokens = metric.total_tokens
        item_id      = f"{agent_name} / {metric.called_at.strftime('%Y-%m-%d %H:%M') if metric.called_at else '?'}"

        if agent_name not in TOKEN_RANGES:
            result.skipped += 1
            continue

        min_tokens, max_tokens = TOKEN_RANGES[agent_name]
        passed = min_tokens <= total_tokens <= max_tokens

        if passed:
            result.passed += 1
        else:
            result.failed += 1

        result.details.append({
            "item_id":      item_id,
            "passed":       passed,
            "agent":        agent_name,
            "total_tokens": total_tokens,
            "note": (
                f"OK — {total_tokens} tokens within [{min_tokens}–{max_tokens}]"
                if passed else
                f"FAIL — {total_tokens} tokens outside [{min_tokens}–{max_tokens}]"
            ),
        })

    result.finalise()
    return result.to_dict()