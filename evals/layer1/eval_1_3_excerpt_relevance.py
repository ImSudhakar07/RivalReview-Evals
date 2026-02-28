"""
eval_1_3_excerpt_relevance.py
------------------------------
Eval 1.3 — Excerpt Relevance

Layer:   1
EVAL_TAG = "quality"
Type:    LLM-as-judge (Grok)
Source:  AppAnalysis.monthly_batches

WHAT WE CHECK:
Excerpts inside each theme must actually support that theme.
We sample 20% of themes across all apps and months, spread across apps
to avoid clustering. Each sampled theme is judged by Grok.

SCORING:
- Each theme gets a 1-5 relevance score from Grok
- Pass criteria: 80% of sampled themes score >= 3.0

SCORE TYPE: ratio (passed / total sampled)
THRESHOLD:  0.80
"""

import random
from evals.base import EvalResult
from services.grok import judge, GrokJudgeError
from config import THRESHOLDS

EVAL_ID     = "1.3"
EVAL_NAME   = "Excerpt Relevance"
LAYER       = 1
SAMPLE_RATE = 0.20   # sample 20% of themes
PASS_SCORE  = 3.0    # minimum Grok score to pass a theme
CATEGORIES  = ("pain_points", "loves", "feature_requests")


def _collect_themes(app_analyses: list[dict]) -> list[dict]:
    """
    Collect all themes with their excerpts across all apps and months.
    Returns a flat list of dicts ready for sampling.
    """
    all_themes = []

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

                    theme    = item.get("theme", "")
                    excerpts = item.get("excerpts", [])

                    # Skip themes with no excerpts — nothing to judge
                    if not theme or not excerpts:
                        continue

                    all_themes.append({
                        "app_name":  app["app_name"],
                        "month":     month_key,
                        "category":  category,
                        "theme":     theme,
                        "excerpts":  excerpts,
                    })

    return all_themes


def _sample_across_apps(all_themes: list[dict], rate: float) -> list[dict]:
    """
    Sample themes evenly across apps so no single app dominates the sample.
    This prevents clustering — if one app has bad excerpts we'll catch it.
    """
    # Group by app
    by_app: dict[str, list] = {}
    for t in all_themes:
        by_app.setdefault(t["app_name"], []).append(t)

    sampled = []
    for app_name, themes in by_app.items():
        # How many to sample from this app
        n = max(1, int(len(themes) * rate))
        sampled.extend(random.sample(themes, min(n, len(themes))))

    return sampled


def run(app_analyses: list[dict], analyses: list[dict]) -> dict:
    result = EvalResult(
        eval_id    = EVAL_ID,
        name       = EVAL_NAME,
        layer      = LAYER,
        threshold  = THRESHOLDS[EVAL_ID],
    )

    if not app_analyses:
        result.error = "No AppAnalysis records found."
        return result.to_dict()

    # Collect and sample themes
    all_themes = _collect_themes(app_analyses)

    if not all_themes:
        result.error = "No themes with excerpts found in monthly_batches."
        return result.to_dict()

    sampled = _sample_across_apps(all_themes, SAMPLE_RATE)

    for item in sampled:
        theme    = item["theme"]
        excerpts = item["excerpts"]
        item_id  = f"{item['app_name']} / {item['month']} / {theme}"

        # Format excerpts for the judge
        excerpts_text = "\n".join(
            f"- {e}" for e in excerpts if isinstance(e, str)
        )

        criteria = (
            f"The theme is: \"{theme}\". "
            f"Do the following excerpts clearly support and relate to this theme? "
            f"Score 5 if all excerpts strongly support the theme. "
            f"Score 3 if some excerpts are relevant but others are vague. "
            f"Score 1 if excerpts do not relate to the theme at all."
        )

        content = f"Theme: {theme}\n\nExcerpts:\n{excerpts_text}"

        try:
            judgment = judge(criteria=criteria, content=content)
            score    = judgment["score"]
            reason   = judgment["reason"]
            passed   = score >= PASS_SCORE

            if passed:
                result.passed += 1
            else:
                result.failed += 1

            result.details.append({
                "item_id": item_id,
                "passed":  passed,
                "score":   score,
                "note":    f"Score {score}/5 — {reason}",
            })

        except GrokJudgeError as e:
            # API not configured yet or network error
            result.skipped += 1
            result.details.append({
                "item_id": item_id,
                "passed":  False,
                "note":    f"Skipped — {e}",
            })

    result.finalise()
    return result.to_dict()