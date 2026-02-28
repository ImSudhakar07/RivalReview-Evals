"""
eval_2_3_ranking_correctness.py
--------------------------------
Eval 2.3 — Ranking Correctness

Layer:   2
EVAL_TAG = "reliability"
Type:    Programmatic
Source:  AppAnalysis.pain_points, loves, feature_requests

WHAT WE CHECK:
Unified top-20 lists must be sorted by volume descending.
item[i].volume >= item[i+1].volume for all i.

PASS CRITERIA: 100% sorted correctly (threshold = 1.0)
"""

from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID    = "2.3"
EVAL_NAME  = "Ranking Correctness"
LAYER      = 2
CATEGORIES = ("pain_points", "loves", "feature_requests")


def _check_sorted(items: list) -> list[str]:
    """
    Returns a list of failure descriptions.
    Empty list means correctly sorted.
    """
    failures = []
    for i in range(len(items) - 1):
        v_curr = items[i].get("volume", 0)
        v_next = items[i + 1].get("volume", 0)
        if v_curr < v_next:
            failures.append(
                f"Position {i} (vol={v_curr}) < position {i+1} (vol={v_next})"
            )
    return failures


def run(app_analyses: list[dict], analyses: list[dict]) -> dict:
    result = EvalResult(
        eval_id   = EVAL_ID,
        name      = EVAL_NAME,
        layer     = LAYER,
        threshold = THRESHOLDS[EVAL_ID],
    )

    if not app_analyses:
        result.error = "No AppAnalysis records found."
        return result.to_dict()

    for app in app_analyses:
        for category in CATEGORIES:
            items = app.get(category, [])

            if not isinstance(items, list) or len(items) < 2:
                result.skipped += 1
                result.details.append({
                    "item_id": f"{app['app_name']} / {category}",
                    "passed":  True,
                    "note":    f"Skipped — only {len(items)} item(s), cannot check sort order",
                })
                continue

            failures = _check_sorted(items)
            passed   = len(failures) == 0

            if passed:
                result.passed += 1
            else:
                result.failed += 1

            result.details.append({
                "item_id": f"{app['app_name']} / {category}",
                "passed":  passed,
                "note": (
                    f"Correctly sorted ({len(items)} items)"
                    if passed else
                    f"Sort errors: {'; '.join(failures)}"
                ),
            })

    result.finalise()
    return result.to_dict()