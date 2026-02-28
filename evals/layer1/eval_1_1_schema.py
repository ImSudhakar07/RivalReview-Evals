"""
eval_1_1_schema.py
------------------
Eval 1.1 — Output Schema Validation

Layer:   1
EVAL_TAG = "reliability"
Type:    Programmatic — no AI judge needed
Source:  AppAnalysis.monthly_batches

WHAT WE CHECK:
Every monthly batch JSON must contain all required keys with correct types.
A single missing or wrong-type key fails that month.

PASS CRITERIA: 100% schema compliance across all months (threshold = 1.0)
"""

from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "1.1"
EVAL_NAME = "Output Schema Validation"
LAYER     = 1

# Keys every monthly batch must have at the top level
REQUIRED_TOP_KEYS = {
    "month", "review_count", "sentiment",
    "pain_points", "loves", "feature_requests"
}

# Keys every item in pain_points / loves / feature_requests must have
REQUIRED_ITEM_KEYS = {"theme", "volume", "excerpts"}

# Keys the sentiment dict must have
REQUIRED_SENTIMENT_KEYS = {"positive_percent", "negative_percent"}


def _check_month(app_name: str, month_key: str, batch: dict) -> dict:
    """
    Validate a single monthly batch dict.
    Returns a detail item describing what passed or failed.
    """
    failures = []

    # 1. Top-level keys
    missing_top = REQUIRED_TOP_KEYS - set(batch.keys())
    if missing_top:
        failures.append(f"Missing keys: {sorted(missing_top)}")

    # 2. Sentiment sub-keys
    sentiment = batch.get("sentiment")
    if isinstance(sentiment, dict):
        missing_sentiment = REQUIRED_SENTIMENT_KEYS - set(sentiment.keys())
        if missing_sentiment:
            failures.append(f"Sentiment missing: {sorted(missing_sentiment)}")
    elif "sentiment" in batch:
        failures.append(f"sentiment is {type(sentiment).__name__}, expected dict")

    # 3. Array categories
    for category in ("pain_points", "loves", "feature_requests"):
        items = batch.get(category)
        if items is None:
            continue  # already caught above
        if not isinstance(items, list):
            failures.append(f"{category} is not a list")
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                failures.append(f"{category}[{i}] is not a dict")
                continue
            missing_item_keys = REQUIRED_ITEM_KEYS - set(item.keys())
            if missing_item_keys:
                failures.append(f"{category}[{i}] missing: {sorted(missing_item_keys)}")

    passed = len(failures) == 0
    return {
        "item_id": f"{app_name} / {month_key}",
        "passed":  passed,
        "note":    "All keys present and valid" if passed else " | ".join(failures),
    }


def run(app_analyses: list[dict], analyses: list[dict]) -> dict:
    """
    Entry point called by the runner.

    Args:
        app_analyses: list of dicts from runner._fetch_rr_data()
        analyses:     not used by this eval but required by runner signature

    Returns:
        EvalResult as a dict
    """
    result = EvalResult(
        eval_id   = EVAL_ID,
        name      = EVAL_NAME,
        layer     = LAYER,
        threshold = THRESHOLDS[EVAL_ID],
    )

    if not app_analyses:
        result.error = "No AppAnalysis records found in the database."
        return result.to_dict()

    for app in app_analyses:
        monthly_batches = app.get("monthly_batches", {})

        if not monthly_batches:
            result.skipped += 1
            result.details.append({
                "item_id": f"{app['app_name']} / (no batches)",
                "passed":  False,
                "note":    "monthly_batches is empty or null",
            })
            continue

        for month_key, batch in monthly_batches.items():
            if not isinstance(batch, dict):
                result.failed += 1
                result.details.append({
                    "item_id": f"{app['app_name']} / {month_key}",
                    "passed":  False,
                    "note":    f"Batch is not a dict — got {type(batch).__name__}",
                })
                continue

            detail = _check_month(app["app_name"], month_key, batch)
            if detail["passed"]:
                result.passed += 1
            else:
                result.failed += 1
            result.details.append(detail)

    result.finalise()
    return result.to_dict()