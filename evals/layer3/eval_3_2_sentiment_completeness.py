"""
eval_3_2_sentiment_completeness.py
------------------------------------
Eval 3.2 — Sentiment Completeness

Layer:   3
EVAL_TAG = "coverage"
Type:    Programmatic
Source:  Analysis.sentiment_trend + Review table

WHAT WE CHECK:
  1. Every app in the project has at least one sentiment trend entry
  2. Every month that has reviews with text has a sentiment trend entry

PASS CRITERIA: 100% coverage (threshold = 1.0)
"""

from collections import defaultdict
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "3.2"
EVAL_NAME = "Sentiment Completeness"
LAYER     = 3


def run(app_analyses: list[dict], analyses: list[dict], reviews: list = None) -> dict:
    result = EvalResult(
        eval_id   = EVAL_ID,
        name      = EVAL_NAME,
        layer     = LAYER,
        threshold = THRESHOLDS[EVAL_ID],
    )

    if not analyses:
        result.error = "No Analysis records found."
        return result.to_dict()

    if not reviews:
        result.error = "No Review records found."
        return result.to_dict()

    # Build lookup: app_id → app_name
    name_by_app = {a["app_id"]: a["app_name"] for a in app_analyses}

    # Build lookup: app_id → set of months with text reviews
    months_with_text: dict[str, set] = defaultdict(set)
    for review in reviews:
        if review.text and review.text.strip() and review.date:
            month_key = review.date.strftime("%Y-%m")
            months_with_text[review.app_id].add(month_key)

    for analysis in analyses:
        sentiment_trend = analysis.get("sentiment_trend", {})
        project_name    = analysis.get("project_name", "?")

        # Check 1 — every app has sentiment data
        for app_id, app_name in name_by_app.items():
            has_data = app_id in sentiment_trend or app_name in sentiment_trend
            passed   = has_data

            if passed:
                result.passed += 1
            else:
                result.failed += 1

            result.details.append({
                "item_id": f"{project_name} / {app_name}",
                "passed":  passed,
                "note": (
                    "OK — sentiment data present"
                    if passed else
                    f"FAIL — no sentiment trend data for {app_name}"
                ),
            })

        # Check 2 — every month with text reviews has a trend entry
        for app_key, monthly_trend in sentiment_trend.items():
            if not isinstance(monthly_trend, dict):
                continue

            # Match app_key to app_id
            app_id = None
            for aid, aname in name_by_app.items():
                if aid == app_key or aname == app_key:
                    app_id = aid
                    break

            if app_id is None:
                continue

            expected_months = months_with_text.get(app_id, set())

            for month in expected_months:
                has_entry = month in monthly_trend
                passed    = has_entry

                if passed:
                    result.passed += 1
                else:
                    result.failed += 1

                result.details.append({
                    "item_id": f"{app_key} / {month}",
                    "passed":  passed,
                    "note": (
                        "OK — sentiment entry present"
                        if passed else
                        f"FAIL — month {month} has reviews but no sentiment entry"
                    ),
                })

    result.finalise()
    return result.to_dict()