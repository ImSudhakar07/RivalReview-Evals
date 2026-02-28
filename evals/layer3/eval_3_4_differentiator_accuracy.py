"""
eval_3_4_differentiator_accuracy.py
-------------------------------------
Eval 3.4 — Differentiator Accuracy

Layer:   3
EVAL_TAG = "quality"
Type:    Programmatic with fuzzy matching
Source:  Analysis.differentiators + AppAnalysis.loves

WHAT WE CHECK:
Each differentiator claimed by Layer 3 for an app must be traceable
to that app's loves data using fuzzy matching.

The differentiators are stored as:
  { "App Name": "what this app does uniquely well" }

PASS CRITERIA: 80% of differentiators traceable to loves (threshold = 0.80)
"""

from thefuzz import fuzz
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID         = "3.4"
EVAL_NAME       = "Differentiator Accuracy"
LAYER           = 3
FUZZY_THRESHOLD = 65


def _differentiator_in_loves(differentiator: str, loves: list) -> bool:
    diff_lower = differentiator.lower().strip()
    for item in loves:
        if not isinstance(item, dict):
            continue
        theme = item.get("theme", "").lower().strip()
        if not theme:
            continue
        similarity = fuzz.partial_ratio(diff_lower, theme)
        if similarity >= FUZZY_THRESHOLD:
            return True
    return False


def run(app_analyses: list[dict], analyses: list[dict]) -> dict:
    result = EvalResult(
        eval_id   = EVAL_ID,
        name      = EVAL_NAME,
        layer     = LAYER,
        threshold = THRESHOLDS[EVAL_ID],
    )

    if not analyses:
        result.error = "No Analysis records found."
        return result.to_dict()

    # Build lookup: app_name → loves
    loves_by_name = {a["app_name"]: a.get("loves", []) for a in app_analyses}

    for analysis in analyses:
        project_name  = analysis.get("project_name", "?")
        differentiators = analysis.get("differentiators", {})

        if not differentiators:
            result.skipped += 1
            result.details.append({
                "item_id": f"{project_name}",
                "passed":  False,
                "note":    "No differentiators found in Analysis record",
            })
            continue

        if not isinstance(differentiators, dict):
            result.skipped += 1
            result.details.append({
                "item_id": f"{project_name}",
                "passed":  False,
                "note":    f"differentiators is not a dict: {type(differentiators)}",
            })
            continue

        for app_name, differentiator in differentiators.items():
            loves   = loves_by_name.get(app_name, [])
            item_id = f"{project_name} / {app_name}"

            if not loves:
                result.skipped += 1
                result.details.append({
                    "item_id": item_id,
                    "passed":  False,
                    "note":    f"No loves data found for {app_name}",
                })
                continue

            found  = _differentiator_in_loves(differentiator, loves)
            passed = found

            if passed:
                result.passed += 1
            else:
                result.failed += 1

            result.details.append({
                "item_id":        item_id,
                "passed":         passed,
                "differentiator": differentiator,
                "note": (
                    f"OK — '{differentiator}' supported by loves data"
                    if passed else
                    f"FAIL — '{differentiator}' not found in loves data"
                ),
            })

    result.finalise()
    return result.to_dict()