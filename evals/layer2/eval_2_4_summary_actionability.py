"""
eval_2_4_summary_actionability.py
-----------------------------------
Eval 2.4 — Summary Actionability

Layer:   2
EVAL_TAG = "quality"
Type:    Mixed — programmatic checks + LLM-as-judge
Source:  AppAnalysis.summary_text

WHAT WE CHECK:
Three programmatic checks:
  1. Summary is at least 100 characters
  2. Contains at least one action verb
  3. Contains at least one specific theme name from pain_points

One LLM judge check:
  4. Is the summary genuinely actionable and specific?

PASS CRITERIA: 80% of app summaries pass all checks (threshold = 0.80)
"""

import re
from services.grok import judge, GrokJudgeError
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "2.4"
EVAL_NAME = "Summary Actionability"
LAYER     = 2

ACTION_VERBS = [
    "fix", "prioritise", "prioritize", "invest", "address",
    "build", "improve", "resolve", "reduce", "increase",
    "focus", "implement", "develop", "optimise", "optimize"
]


def _programmatic_checks(summary: str, pain_points: list) -> list[str]:
    """Returns list of failure reasons. Empty = all passed."""
    failures = []

    if len(summary) < 100:
        failures.append(f"Summary too short ({len(summary)} chars, minimum 100)")

    summary_lower = summary.lower()

    has_verb = any(verb in summary_lower for verb in ACTION_VERBS)
    if not has_verb:
        failures.append("No action verbs found")

    top_themes = [
        item.get("theme", "").lower()
        for item in pain_points[:5]
        if isinstance(item, dict)
    ]
    has_theme = any(
        theme and theme in summary_lower
        for theme in top_themes
    )
    if not has_theme:
        failures.append("No specific pain point themes mentioned")

    return failures


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
        app_name    = app["app_name"]
        summary     = app.get("summary_text", "")
        pain_points = app.get("pain_points", [])
        item_id     = f"{app_name} / summary"

        if not summary:
            result.failed += 1
            result.details.append({
                "item_id": item_id,
                "passed":  False,
                "note":    "Summary is empty",
            })
            continue

        # Programmatic checks
        failures = _programmatic_checks(summary, pain_points)

        if failures:
            result.failed += 1
            result.details.append({
                "item_id": item_id,
                "passed":  False,
                "note":    f"Programmatic checks failed: {' | '.join(failures)}",
            })
            continue

        # LLM judge check
        criteria = (
            "Does this product manager summary contain specific actionable "
            "recommendations? It should name specific issues by name, suggest "
            "concrete actions using verbs like fix, prioritise, invest, and avoid "
            "generic statements that could apply to any app. "
            "Score 5 if fully specific and actionable. "
            "Score 3 if partially actionable but contains some generic statements. "
            "Score 1 if generic and vague throughout."
        )

        try:
            judgment = judge(criteria=criteria, content=summary)
            score    = judgment["score"]
            reason   = judgment["reason"]
            passed   = score >= 3.0

            if passed:
                result.passed += 1
            else:
                result.failed += 1

            result.details.append({
                "item_id": item_id,
                "passed":  passed,
                "score":   score,
                "note":    f"Judge score {score}/5 — {reason}",
            })

        except GrokJudgeError as e:
            result.skipped += 1
            result.details.append({
                "item_id": item_id,
                "passed":  False,
                "note":    f"Skipped — {e}",
            })

    result.finalise()
    return result.to_dict()