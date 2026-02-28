"""
eval_2_6_excerpt_traceability.py
---------------------------------
Eval 2.6 — Excerpt Traceability

Layer:   2
EVAL_TAG = "coverage"
Type:    Programmatic with fuzzy matching
Source:  AppAnalysis.pain_points + Review table (raw review text)

WHAT WE CHECK:
Two checks per excerpt:
  1. Length — must be 150 characters or fewer
  2. Traceability — must appear near-verbatim in raw reviews
     for the same app (fuzzy match >= 75%)

We search only reviews belonging to the same app to keep it fast.

PASS CRITERIA: 85% of excerpts traceable to source reviews (threshold = 0.85)
"""

from thefuzz import fuzz
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID          = "2.6"
EVAL_NAME        = "Excerpt Traceability"
LAYER            = 2
MAX_LENGTH       = 150
FUZZY_THRESHOLD  = 75
CATEGORIES       = ("pain_points", "loves", "feature_requests")


def _find_in_reviews(excerpt: str, reviews: list) -> bool:
    """Check if excerpt appears near-verbatim in any review text."""
    excerpt_clean = excerpt.lower().strip()
    for review in reviews:
        if not review.text:
            continue
        similarity = fuzz.partial_ratio(
            excerpt_clean,
            review.text.lower().strip()
        )
        if similarity >= FUZZY_THRESHOLD:
            return True
    return False


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
        result.error = "No Review records found."
        return result.to_dict()

    # Group reviews by app_id for fast lookup
    reviews_by_app: dict[str, list] = {}
    for review in reviews:
        reviews_by_app.setdefault(review.app_id, []).append(review)

    for app in app_analyses:
        app_id   = app["app_id"]
        app_name = app["app_name"]
        app_reviews = reviews_by_app.get(app_id, [])

        for category in CATEGORIES:
            items = app.get(category, [])
            if not isinstance(items, list):
                continue

            for item in items[:5]:  # top 5 themes only
                if not isinstance(item, dict):
                    continue

                theme    = item.get("theme", "?")
                excerpts = item.get("excerpts", [])

                if not isinstance(excerpts, list):
                    continue

                for excerpt in excerpts:
                    if not isinstance(excerpt, str) or not excerpt.strip():
                        continue

                    item_id = f"{app_name} / {category} / {theme}"
                    failures = []

                    # Length check
                    if len(excerpt) > MAX_LENGTH:
                        failures.append(
                            f"Too long ({len(excerpt)} chars, max {MAX_LENGTH})"
                        )

                    # Traceability check
                    found = _find_in_reviews(excerpt, app_reviews)
                    if not found:
                        failures.append("Not found in raw reviews")

                    passed = len(failures) == 0

                    if passed:
                        result.passed += 1
                    else:
                        result.failed += 1

                    result.details.append({
                        "item_id": item_id,
                        "passed":  passed,
                        "excerpt": excerpt[:80] + "..." if len(excerpt) > 80 else excerpt,
                        "note": (
                            "OK — traceable and within length"
                            if passed else
                            f"FAIL — {' | '.join(failures)}"
                        ),
                    })

    result.finalise()
    return result.to_dict()