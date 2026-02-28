"""
eval_1_5_volume_plausibility.py
--------------------------------
Eval 1.5 — Volume Plausibility

Layer:   1
EVAL_TAG = "reliability"
Type:    Programmatic
Source:  AppAnalysis.monthly_batches

WHAT WE CHECK:
No single theme's volume should exceed the total review_count for that month.
A theme cannot affect more reviews than actually exist.

PASS CRITERIA: 100% pass the upper bound check (threshold = 1.0)
"""

from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID    = "1.5"
EVAL_NAME  = "Volume Plausibility"
LAYER      = 1
CATEGORIES = ("pain_points", "loves", "feature_requests")


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
        monthly_batches = app.get("monthly_batches", {})

        for month_key, batch in monthly_batches.items():
            if not isinstance(batch, dict):
                continue

            review_count = batch.get("review_count")
            if not isinstance(review_count, (int, float)) or review_count <= 0:
                result.skipped += 1
                result.details.append({
                    "item_id": f"{app['app_name']} / {month_key}",
                    "passed":  False,
                    "note":    f"review_count missing or invalid: {review_count!r}",
                })
                continue

            for category in CATEGORIES:
                items = batch.get(category, [])
                if not isinstance(items, list):
                    continue

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    theme  = item.get("theme", "?")
                    volume = item.get("volume")

                    if not isinstance(volume, (int, float)):
                        result.skipped += 1
                        result.details.append({
                            "item_id": f"{app['app_name']} / {month_key} / {theme}",
                            "passed":  False,
                            "note":    f"volume is not a number: {volume!r}",
                        })
                        continue

                    passed = volume <= review_count

                    if passed:
                        result.passed += 1
                    else:
                        result.failed += 1

                    result.details.append({
                        "item_id":      f"{app['app_name']} / {month_key} / {theme}",
                        "passed":       passed,
                        "note": (
                            f"OK — volume {volume} ≤ review_count {review_count}"
                            if passed else
                            f"FAIL — volume {volume} exceeds review_count {review_count}"
                        ),
                    })

    result.finalise()
    return result.to_dict()