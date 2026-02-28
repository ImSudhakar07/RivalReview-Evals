"""
eval_1_2_theme_specificity.py
------------------------------
Eval 1.2 — Theme Specificity

Layer:   1
EVAL_TAG = "quality"
Type:    Programmatic
Source:  AppAnalysis.monthly_batches

WHAT WE CHECK:
Every theme across all categories must be at least 2 words.
Single-word themes like "bad" or "slow" are too vague to be actionable.

PASS CRITERIA: 90% or more of themes are 2+ words (threshold = 0.90)
"""

from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "1.2"
EVAL_NAME = "Theme Specificity"
LAYER     = 1

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

            for category in CATEGORIES:
                items = batch.get(category, [])
                if not isinstance(items, list):
                    continue

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    theme = item.get("theme", "")

                    if not isinstance(theme, str) or not theme.strip():
                        result.failed += 1
                        result.details.append({
                            "item_id": f"{app['app_name']} / {month_key} / {category}",
                            "passed":  False,
                            "note":    f"Theme is empty or not a string: {theme!r}",
                        })
                        continue

                    word_count = len(theme.strip().split())
                    passed     = word_count >= 2

                    if passed:
                        result.passed += 1
                    else:
                        result.failed += 1

                    result.details.append({
                        "item_id":    f"{app['app_name']} / {month_key} / {category}",
                        "passed":     passed,
                        "theme":      theme,
                        "word_count": word_count,
                        "note":       f"{'OK' if passed else 'FAIL'} — {word_count} word(s): {theme!r}",
                    })

    result.finalise()
    return result.to_dict()