"""
eval_3_5_summary_depth.py
--------------------------
Eval 3.5 — Summary Depth

Layer:   3
EVAL_TAG = "quality"
Type:    Mixed — programmatic checks + LLM-as-judge
Source:  Analysis.combined_summary

WHAT WE CHECK:
Programmatic:
  1. Summary is 8-12 sentences
  2. References at least 2 specific app names
  3. Contains at least one action verb

LLM judge:
  4. Is the summary genuinely insightful and actionable for a PM?
     Also verifies shared pain points are grounded across multiple apps.

PASS CRITERIA: 80% of summaries pass all checks (threshold = 0.80)
"""

import re
from services.grok import judge, GrokJudgeError
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "3.5"
EVAL_NAME = "Summary Depth"
LAYER     = 3

ACTION_VERBS = [
    "fix", "prioritise", "prioritize", "invest", "address",
    "build", "improve", "resolve", "focus", "implement",
    "develop", "optimise", "optimize", "exploit", "leverage"
]


def _count_sentences(text: str) -> int:
    """Count sentences by splitting on . ! ? endings."""
    sentences = re.split(r'[.!?]+', text.strip())
    return len([s for s in sentences if s.strip()])


def _programmatic_checks(
    summary: str,
    app_names: list[str]
) -> list[str]:
    """Returns list of failure reasons. Empty = all passed."""
    failures    = []
    summary_lower = summary.lower()

    sentence_count = _count_sentences(summary)
    if not (8 <= sentence_count <= 12):
        failures.append(
            f"Summary has {sentence_count} sentences (expected 8-12)"
        )

    apps_mentioned = sum(
        1 for name in app_names
        if name.lower() in summary_lower
    )
    if apps_mentioned < 2:
        failures.append(
            f"Only {apps_mentioned} app names mentioned (expected 2+)"
        )

    has_verb = any(verb in summary_lower for verb in ACTION_VERBS)
    if not has_verb:
        failures.append("No action verbs found")

    return failures


def run(app_analyses: list[dict], analyses: list[dict]) -> dict:
    result = EvalResult(
        eval_id   = EVAL_ID,
        name      = EVAL_NAME,
        layer     = LAYER,
        threshold = THRESHOLDS[EVAL_ID],
    )

    if not analyses:
        result.error = "No Analysis records found."
        return result.to_dict()

    app_names = [a["app_name"] for a in app_analyses]

    for analysis in analyses:
        summary      = analysis.get("combined_summary", "")
        project_name = analysis.get("project_name", "?")
        item_id      = f"{project_name} / combined_summary"

        if not summary:
            result.failed += 1
            result.details.append({
                "item_id": item_id,
                "passed":  False,
                "note":    "Combined summary is empty",
            })
            continue

        # Programmatic checks
        failures = _programmatic_checks(summary, app_names)

        if failures:
            result.failed += 1
            result.details.append({
                "item_id": item_id,
                "passed":  False,
                "note":    f"Programmatic checks failed: {' | '.join(failures)}",
            })
            continue

        # LLM judge
        app_list = ", ".join(app_names)
        criteria = (
            f"This is a cross-app competitive analysis summary for a product manager. "
            f"The apps analysed are: {app_list}. "
            f"Evaluate whether the summary: "
            f"(1) identifies specific shared pain points across multiple apps, "
            f"(2) identifies what each app does uniquely well as differentiators, "
            f"(3) gives concrete strategic recommendations a PM can act on, "
            f"(4) avoids generic statements that could apply to any app. "
            f"Score 5 if all four criteria are met. "
            f"Score 3 if two or three criteria are met. "
            f"Score 1 if the summary is generic and lacks specific insights."
        )

        try:
            judgment = judge(criteria=criteria, content=summary)
            score    = judgment["score"]
            reason   = judgment["reason"]
            passed   = score >= 3.5

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