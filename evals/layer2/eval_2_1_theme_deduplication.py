"""
eval_2_1_theme_deduplication.py
--------------------------------
Eval 2.1 — Theme Deduplication

Layer:   2
EVAL_TAG = "quality"
Type:    Programmatic with fuzzy matching
Source:  AppAnalysis.pain_points, loves, feature_requests

WHAT WE CHECK:
No two themes in the same unified list should be suspiciously similar.
If "App Crashes" and "Crashing Issues" both appear in the top 20
pain points that is a deduplication failure.

PASS CRITERIA: 90% of theme pairs are below 80% similarity (threshold = 0.90)
"""

from itertools import combinations
from thefuzz import fuzz
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID          = "2.1"
EVAL_NAME        = "Theme Deduplication"
LAYER            = 2
SIMILARITY_LIMIT = 80
CATEGORIES       = ("pain_points", "loves", "feature_requests")


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
        app_name = app["app_name"]

        for category in CATEGORIES:
            items = app.get(category, [])
            if not isinstance(items, list) or len(items) < 2:
                result.skipped += 1
                result.details.append({
                    "item_id": f"{app_name} / {category}",
                    "passed":  True,
                    "note":    "Skipped — fewer than 2 themes",
                })
                continue

            themes = [
                item.get("theme", "")
                for item in items
                if isinstance(item, dict) and item.get("theme")
            ]

            for theme_a, theme_b in combinations(themes, 2):
                similarity = fuzz.ratio(
                    theme_a.lower().strip(),
                    theme_b.lower().strip()
                )
                passed = similarity < SIMILARITY_LIMIT

                if passed:
                    result.passed += 1
                else:
                    result.failed += 1

                if similarity >= 70:
                    result.details.append({
                        "item_id":    f"{app_name} / {category}",
                        "passed":     passed,
                        "theme_a":    theme_a,
                        "theme_b":    theme_b,
                        "similarity": similarity,
                        "note": (
                            f"FAIL — '{theme_a}' and '{theme_b}' "
                            f"are {similarity}% similar"
                            if not passed else
                            f"WARN — '{theme_a}' and '{theme_b}' "
                            f"are {similarity}% similar but below threshold"
                        ),
                    })

    result.finalise()
    return result.to_dict()