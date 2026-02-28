"""
eval_3_1_sentiment_math.py
---------------------------
Eval 3.1 — Sentiment Trend Math

Layer:   3
EVAL_TAG = "reliability"
Type:    Programmatic
Source:  Analysis.sentiment_trend + Review table

WHAT WE CHECK:
The sentiment_trend is stored as:
  { "App Name": [ {"month": "YYYY-MM", "positive": float, "negative": float, "total_reviews": int} ] }

We recalculate the combined positive % independently:
  rating_positive = (4-5 star reviews / total non-neutral reviews) x 100
  grok_positive   = monthly_batch.sentiment.positive_percent
  combined        = (rating_positive x 0.6) + (grok_positive x 0.4)

Then compare against stored positive value within tolerance.

TOLERANCE: 2.0 percentage points (agent uses rounding)
PASS CRITERIA: 100% match within tolerance (threshold = 1.0)
"""

from collections import defaultdict
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "3.1"
EVAL_NAME = "Sentiment Trend Math"
LAYER     = 3
TOLERANCE = 2.0  # percentage points — agent rounds to 1dp


def _rating_sentiment_by_month(reviews: list, app_id: str) -> dict[str, dict]:
    """
    Calculate rating-based positive and negative % per month for one app.
    Returns dict keyed by YYYY-MM.
    """
    monthly: dict = defaultdict(lambda: {"total": 0, "positive": 0, "negative": 0})

    for review in reviews:
        if review.app_id != app_id:
            continue
        if not review.date or not review.rating:
            continue

        key = review.date.strftime("%Y-%m")
        monthly[key]["total"] += 1

        if review.rating >= 4:
            monthly[key]["positive"] += 1
        elif review.rating <= 2:
            monthly[key]["negative"] += 1

    result = {}
    for month, counts in monthly.items():
        total = counts["total"]
        if total > 0:
            result[month] = {
                "positive": round(counts["positive"] / total * 100, 1),
                "negative": round(counts["negative"] / total * 100, 1),
            }

    return result


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

    # Build lookup: app_name → app_id and app_name → monthly_batches
    name_to_id      = {a["app_name"]: a["app_id"] for a in app_analyses}
    name_to_batches = {a["app_name"]: a["monthly_batches"] for a in app_analyses}

    for analysis in analyses:
        sentiment_trend = analysis.get("sentiment_trend", {})

        if not sentiment_trend:
            result.error = "sentiment_trend is empty."
            return result.to_dict()

        # Structure: { "App Name": [ {month, positive, negative, total_reviews} ] }
        for app_name, monthly_list in sentiment_trend.items():
            if not isinstance(monthly_list, list):
                continue

            app_id = name_to_id.get(app_name)
            if not app_id:
                result.skipped += 1
                result.details.append({
                    "item_id": f"{app_name}",
                    "passed":  False,
                    "note":    f"Could not match app name '{app_name}' to any app",
                })
                continue

            rating_by_month = _rating_sentiment_by_month(reviews, app_id)
            monthly_batches = name_to_batches.get(app_name, {})

            for entry in monthly_list:
                if not isinstance(entry, dict):
                    continue

                month           = entry.get("month")
                stored_positive = entry.get("positive")

                if not month or stored_positive is None:
                    result.skipped += 1
                    continue

                # Get rating-based sentiment
                rating_data   = rating_by_month.get(month, {})
                rating_pos    = rating_data.get("positive", 0.0)

                # Get Grok sentiment from monthly batches
                batch         = monthly_batches.get(month, {})
                grok_pos      = 0.0
                if isinstance(batch, dict):
                    sentiment = batch.get("sentiment", {})
                    if isinstance(sentiment, dict):
                        grok_pos = float(sentiment.get("positive_percent", 0) or 0)

                # Recalculate combined
                total_reviews = entry.get("total_reviews", 0)
                if total_reviews > 0 and grok_pos > 0:
                    expected = round((rating_pos * 0.6) + (grok_pos * 0.4), 1)
                elif total_reviews > 0:
                    expected = round(rating_pos, 1)
                elif grok_pos > 0:
                    expected = round(grok_pos, 1)
                else:
                    expected = 0.0

                diff   = abs(float(stored_positive) - expected)
                passed = diff <= TOLERANCE

                if passed:
                    result.passed += 1
                else:
                    result.failed += 1

                result.details.append({
                    "item_id":         f"{app_name} / {month}",
                    "passed":          passed,
                    "stored_positive": stored_positive,
                    "expected":        expected,
                    "diff":            round(diff, 2),
                    "note": (
                        f"OK — diff {diff:.1f}pp within ±{TOLERANCE}pp"
                        if passed else
                        f"FAIL — stored={stored_positive}%, "
                        f"expected={expected}%, diff={diff:.1f}pp"
                    ),
                })

    result.finalise()
    return result.to_dict()