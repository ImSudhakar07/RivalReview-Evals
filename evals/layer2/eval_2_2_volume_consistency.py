"""
eval_2_2_volume_consistency.py
--------------------------------
Eval 2.2 — Volume Consistency

Layer:   2
EVAL_TAG = "reliability"
Type:    Programmatic
Source:  AppAnalysis.pain_points, loves, feature_requests
         + AppAnalysis.monthly_batches (for lower bound check)
         + App.selected_count (for upper bound check)

WHAT WE CHECK:
Two bounds for every unified theme:

Lower bound:
  unified volume >= highest single-month volume for that theme
  (merging months should never produce a lower volume than any single month)

Upper bound:
  unified volume <= app's selected_count
  (can't affect more reviews than were analysed)

PASS CRITERIA: 100% pass both bounds (threshold = 1.0)
"""

from thefuzz import fuzz
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID    = "2.2"
EVAL_NAME  = "Volume Consistency"
LAYER      = 2
CATEGORIES = ("pain_points", "loves", "feature_requests")

# Fuzzy match threshold — how similar theme names must be to count as the same theme
# 80 means 80% similar. This handles "app crashes" vs "App Crashes" vs "crashing issues"
FUZZY_THRESHOLD = 80


def _find_max_monthly_volume(theme: str, category: str, monthly_batches: dict) -> int:
    """
    Search all monthly batches for the highest volume of a matching theme.
    Uses fuzzy matching so "App Crashes" matches "app crashes" and "crashing issues".
    Returns 0 if theme not found in any month.
    """
    max_volume = 0

    for month_key, batch in monthly_batches.items():
        if not isinstance(batch, dict):
            continue

        items = batch.get(category, [])
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            monthly_theme  = item.get("theme", "")
            monthly_volume = item.get("volume", 0)

            # Fuzzy match the theme names
            similarity = fuzz.ratio(
                theme.lower().strip(),
                monthly_theme.lower().strip()
            )

            if similarity >= FUZZY_THRESHOLD:
                max_volume = max(max_volume, monthly_volume)

    return max_volume


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
        selected_count  = app.get("selected_count") or 0
        monthly_batches = app.get("monthly_batches", {})

        for category in CATEGORIES:
            items = app.get(category, [])
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
                        "item_id": f"{app_name} / {category} / {theme}",
                        "passed":  False,
                        "note":    f"volume is not a number: {volume!r}",
                    })
                    continue

                failures = []

                # --- Upper bound check ---
                if selected_count > 0 and volume > selected_count:
                    failures.append(
                        f"volume {volume} exceeds selected_count {selected_count}"
                    )

                # --- Lower bound check ---
                max_monthly = _find_max_monthly_volume(
                    theme, category, monthly_batches
                )
                if max_monthly > 0 and volume < max_monthly:
                    failures.append(
                        f"volume {volume} is less than max monthly volume {max_monthly}"
                    )

                passed = len(failures) == 0

                if passed:
                    result.passed += 1
                else:
                    result.failed += 1

                result.details.append({
                    "item_id":       f"{app_name} / {category} / {theme}",
                    "passed":        passed,
                    "volume":        volume,
                    "selected_count": selected_count,
                    "max_monthly":   max_monthly,
                    "note": (
                        f"OK — volume {volume} within bounds "
                        f"[{max_monthly} — {selected_count}]"
                        if passed else
                        f"FAIL — {' | '.join(failures)}"
                    ),
                })

    result.finalise()
    return result.to_dict()