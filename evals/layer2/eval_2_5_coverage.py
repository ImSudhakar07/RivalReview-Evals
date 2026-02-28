"""
eval_2_5_coverage.py
---------------------
Eval 2.5 — Coverage

Layer:   2
EVAL_TAG = "coverage"
Type:    Programmatic with fuzzy matching
Source:  AppAnalysis.pain_points + AppAnalysis.monthly_batches

WHAT WE CHECK:
Each of the top 5 unified themes must appear in at least one
monthly batch. This verifies Layer 2 is not hallucinating themes
that never appeared in the original monthly data.

PASS CRITERIA: 95% of top 5 themes traceable to source data (threshold = 0.95)
"""

from thefuzz import fuzz
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID          = "2.5"
EVAL_NAME        = "Coverage"
LAYER            = 2
FUZZY_THRESHOLD  = 50
TOP_N            = 5
CATEGORIES       = ("pain_points", "loves", "feature_requests")


def _theme_in_monthly(theme: str, category: str, monthly_batches: dict) -> bool:
    """Check if a theme appears in any monthly batch using fuzzy matching."""
    for month_key, batch in monthly_batches.items():
        if not isinstance(batch, dict):
            continue
        items = batch.get(category, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            monthly_theme = item.get("theme", "")
            similarity = fuzz.ratio(
                theme.lower().strip(),
                monthly_theme.lower().strip()
            )
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

    if not app_analyses:
        result.error = "No AppAnalysis records found."
        return result.to_dict()

    for app in app_analyses:
        app_name        = app["app_name"]
        monthly_batches = app.get("monthly_batches", {})

        for category in CATEGORIES:
            items = app.get(category, [])
            if not isinstance(items, list):
                continue

            top_items = items[:TOP_N]

            for item in top_items:
                if not isinstance(item, dict):
                    continue

                theme   = item.get("theme", "")
                item_id = f"{app_name} / {category} / {theme}"

                if not theme:
                    result.skipped += 1
                    continue

                found  = _theme_in_monthly(theme, category, monthly_batches)
                passed = found

                if passed:
                    result.passed += 1
                else:
                    result.failed += 1

                result.details.append({
                    "item_id": item_id,
                    "passed":  passed,
                    "theme":   theme,
                    "note": (
                        f"OK — '{theme}' found in monthly data"
                        if passed else
                        f"FAIL — '{theme}' not found in any monthly batch "
                        f"(possible hallucination)"
                    ),
                })

    result.finalise()
    return result.to_dict()