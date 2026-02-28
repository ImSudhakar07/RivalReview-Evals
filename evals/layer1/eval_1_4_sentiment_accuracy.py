"""
eval_1_4_sentiment_accuracy.py
--------------------------------
Eval 1.4 — Sentiment Accuracy

Layer:   1
EVAL_TAG = "reliability"
Type:    Programmatic — compares Grok sentiment against rating-based ground truth
Source:  AppAnalysis.monthly_batches + Review table (raw ratings)

WHAT WE CHECK:
For each month, we calculate rating-based positive % from raw star ratings:
  4-5 stars = positive
  1-2 stars = negative
  3 stars   = neutral (excluded)

We compare this against Grok's positive_percent from monthly_batches.
If they differ by more than 15 percentage points, that month fails.

PASS CRITERIA: 80% or more of months within tolerance (threshold = 0.80)
"""

from collections import defaultdict
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "1.4"
EVAL_NAME = "Sentiment Accuracy"
LAYER     = 1
TOLERANCE = 15.0  # percentage points


def _rating_sentiment_by_month(reviews: list) -> dict[str, dict]:
    """
    Group raw reviews by app_id and month, calculate rating-based sentiment.
    Returns dict keyed by app_id → month → positive_percent
    """
    # Structure: { app_id: { "YYYY-MM": { "positive": int, "total": int } } }
    monthly: dict = defaultdict(lambda: defaultdict(lambda: {"positive": 0, "total": 0}))

    for review in reviews:
        if not review.date or not review.rating:
            continue
        # Skip neutral ratings
        if review.rating == 3:
            continue

        month_key = review.date.strftime("%Y-%m")
        monthly[review.app_id][month_key]["total"] += 1

        if review.rating >= 4:
            monthly[review.app_id][month_key]["positive"] += 1

    # Convert to positive percentages
    result = {}
    for app_id, months in monthly.items():
        result[app_id] = {}
        for month, counts in months.items():
            if counts["total"] > 0:
                result[app_id][month] = round(
                    counts["positive"] / counts["total"] * 100, 2
                )

    return result


def run(app_analyses: list[dict], analyses: list[dict], reviews: list = None) -> dict:
    result = EvalResult(
        eval_id   = EVAL_ID,
        name      = EVAL_NAME,
        layer     = LAYER,
        threshold = THRESHOLDS[EVAL_ID],
    )

    if not app_analyses:
        result.error = "No AppAnalysis records found."
        return result.to_dict()

    if not reviews:
        result.error = "No Review records found. Cannot calculate rating-based sentiment."
        return result.to_dict()

    # Calculate rating-based sentiment from raw reviews
    rating_sentiment = _rating_sentiment_by_month(reviews)

    for app in app_analyses:
        app_id          = app["app_id"]
        app_name        = app["app_name"]
        monthly_batches = app.get("monthly_batches", {})
        app_ratings     = rating_sentiment.get(app_id, {})

        for month_key, batch in monthly_batches.items():
            if not isinstance(batch, dict):
                continue

            # Get Grok's sentiment for this month
            sentiment = batch.get("sentiment", {})
            if not isinstance(sentiment, dict):
                result.skipped += 1
                result.details.append({
                    "item_id": f"{app_name} / {month_key}",
                    "passed":  False,
                    "note":    "No sentiment data in batch",
                })
                continue

            grok_positive = sentiment.get("positive_percent")
            if grok_positive is None:
                result.skipped += 1
                result.details.append({
                    "item_id": f"{app_name} / {month_key}",
                    "passed":  False,
                    "note":    "positive_percent missing from sentiment",
                })
                continue

            # Get rating-based sentiment for this month
            rating_positive = app_ratings.get(month_key)
            if rating_positive is None:
                result.skipped += 1
                result.details.append({
                    "item_id": f"{app_name} / {month_key}",
                    "passed":  False,
                    "note":    "No raw reviews found for this month",
                })
                continue

            # Compare
            diff   = abs(float(grok_positive) - rating_positive)
            passed = diff <= TOLERANCE

            if passed:
                result.passed += 1
            else:
                result.failed += 1

            result.details.append({
                "item_id":        f"{app_name} / {month_key}",
                "passed":         passed,
                "grok_positive":  grok_positive,
                "rating_positive": rating_positive,
                "diff":           round(diff, 2),
                "note": (
                    f"OK — Grok {grok_positive}% vs ratings {rating_positive}% "
                    f"(diff {diff:.1f}pp)"
                    if passed else
                    f"FAIL — Grok {grok_positive}% vs ratings {rating_positive}% "
                    f"(diff {diff:.1f}pp exceeds {TOLERANCE}pp tolerance)"
                ),
            })

    result.finalise()
    return result.to_dict()