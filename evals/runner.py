"""
evals/runner.py
---------------
Orchestrates all eval runs.
"""

import uuid
import json
import traceback
import statistics
from datetime import datetime

from services.db import (
    RRSession, EvalSession,
    RRApp, RRAppAnalysis, RRAnalysis, RRReview, RRProject,
    RRAgentMetrics,
    EvalRun, EvalResult as EvalResultModel,
    EvalVersion,
    load_json, init_eval_db,
)
from evals.base import EvalResult

# ---------------------------------------------------------------------------
# Eval registry
# ---------------------------------------------------------------------------

from evals.layer1 import eval_1_1_schema
from evals.layer1 import eval_1_2_theme_specificity
from evals.layer1 import eval_1_3_excerpt_relevance
from evals.layer1 import eval_1_4_sentiment_accuracy
from evals.layer1 import eval_1_5_volume_plausibility

from evals.layer2 import eval_2_1_theme_deduplication
from evals.layer2 import eval_2_2_volume_consistency
from evals.layer2 import eval_2_3_ranking_correctness
from evals.layer2 import eval_2_4_summary_actionability
from evals.layer2 import eval_2_5_coverage
from evals.layer2 import eval_2_6_excerpt_traceability

from evals.layer3 import eval_3_1_sentiment_math
from evals.layer3 import eval_3_2_sentiment_completeness
from evals.layer3 import eval_3_4_differentiator_accuracy
from evals.layer3 import eval_3_5_summary_depth

from evals.layer4 import eval_4_1_token_usage
from evals.layer4 import eval_4_2_cost_estimate
from evals.layer4 import eval_4_3_latency
from evals.layer4 import eval_4_4_retry_rate

NEEDS_REVIEWS = {
    eval_1_4_sentiment_accuracy,
    eval_2_6_excerpt_traceability,
    eval_3_1_sentiment_math,
    eval_3_2_sentiment_completeness,
}

NEEDS_METRICS = {
    eval_4_1_token_usage,
    eval_4_2_cost_estimate,
    eval_4_3_latency,
    eval_4_4_retry_rate,
}

ALL_EVALS = [
    eval_1_1_schema, eval_1_2_theme_specificity, eval_1_3_excerpt_relevance,
    eval_1_4_sentiment_accuracy, eval_1_5_volume_plausibility,
    eval_2_1_theme_deduplication, eval_2_2_volume_consistency,
    eval_2_3_ranking_correctness, eval_2_4_summary_actionability,
    eval_2_5_coverage, eval_2_6_excerpt_traceability,
    eval_3_1_sentiment_math, eval_3_2_sentiment_completeness,
    eval_3_4_differentiator_accuracy, eval_3_5_summary_depth,
    eval_4_1_token_usage, eval_4_2_cost_estimate,
    eval_4_3_latency, eval_4_4_retry_rate,
]

EVAL_MAP = {getattr(m, "EVAL_ID", None): m for m in ALL_EVALS}

# ---------------------------------------------------------------------------
# Criteria descriptions — shown in run detail per eval
# ---------------------------------------------------------------------------

EVAL_CRITERIA = {
    "1.1": "100% of app analysis outputs must match the expected JSON schema with all required fields present.",
    "1.2": "≥90% of themes must be specific (≥3 words, not generic). Vague themes like 'app issues' fail.",
    "1.3": "≥80% of excerpts must be relevant to their assigned theme based on keyword overlap.",
    "1.4": "≥80% of sentiment labels must match the review rating direction (positive/negative).",
    "1.5": "≥90% of apps must have review volumes within a plausible range (not zero, not suspiciously high).",
    "2.1": "≥85% theme similarity across apps must be below 0.8 cosine similarity — themes should be distinct.",
    "2.2": "≥90% of volume counts across monthly batches must be internally consistent.",
    "2.3": "100% of ranked lists must be in correct descending order by volume.",
    "2.4": "≥70% of summaries must contain at least one actionable recommendation (verb + specific suggestion).",
    "2.5": "≥80% of themes must be traceable back to source monthly batch data.",
    "2.6": "≥85% of excerpts must appear verbatim or near-verbatim in the source review text.",
    "3.1": "100% of sentiment trend calculations must be mathematically correct (values sum correctly).",
    "3.2": "≥90% of apps must have sentiment data present in the cross-app analysis.",
    "3.4": "≥75% of differentiator claims must be supported by evidence in the underlying app analyses.",
    "3.5": "≥70% of summaries must meet minimum depth (≥50 words, covering multiple themes).",
    "4.1": "≥90% of agent calls must use tokens within expected range per agent type.",
    "4.2": "≥90% of agent calls must stay within expected cost range ($0.001–$0.10 per call).",
    "4.3": "≥90% of agent calls must complete within expected latency range (1–120 seconds).",
    "4.4": "Retry rate must be below 10% of total agent calls.",
}


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _fetch_rr_data(project_id: str):
    db = RRSession()
    try:
        apps    = db.query(RRApp).filter(RRApp.project_id == project_id).all()
        app_ids = [app.id for app in apps]

        if not app_ids:
            return [], [], [], []

        app_analyses = []
        for app in apps:
            analysis = (
                db.query(RRAppAnalysis)
                .filter(RRAppAnalysis.app_id == app.id)
                .first()
            )
            if not analysis:
                continue
            app_analyses.append({
                "app_id":           app.id,
                "app_name":         app.name,
                "selected_count":   app.selected_count,
                "monthly_batches":  load_json(analysis.monthly_batches) or {},
                "pain_points":      load_json(analysis.pain_points) or [],
                "loves":            load_json(analysis.loves) or [],
                "feature_requests": load_json(analysis.feature_requests) or [],
                "summary_text":     analysis.summary_text or "",
                "quality_score":    analysis.quality_score,
            })

        analyses = []
        cross = (
            db.query(RRAnalysis)
            .filter(RRAnalysis.project_id == project_id)
            .first()
        )
        if cross:
            project = db.query(RRProject).filter(RRProject.id == project_id).first()
            diff = load_json(cross.differentiators) if hasattr(cross, 'differentiators') else {}
            analyses.append({
                "project_id":        project_id,
                "project_name":      project.name if project else "",
                "sentiment_trend":   load_json(cross.sentiment_trend) or {},
                "combined_summary":  cross.combined_summary or "",
                "quality_score":     cross.quality_score,
                "differentiators":   diff or {},
                "shared_pain_points": load_json(cross.shared_pain_points) if hasattr(cross, 'shared_pain_points') else [],
            })

        reviews = (
            db.query(RRReview)
            .filter(RRReview.app_id.in_(app_ids))
            .all()
        )

        metrics = (
            db.query(RRAgentMetrics)
            .filter(RRAgentMetrics.project_id == project_id)
            .all()
        )

        return app_analyses, analyses, reviews, metrics

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Metrics computation (P95, avg, min, max)
# ---------------------------------------------------------------------------

def _compute_metrics(result: dict, metrics: list, eval_id: str) -> dict:
    """
    For layer 4 evals, compute P95/avg/min/max from detail items.
    Returns a dict to store as metrics_json.
    """
    if not result.get("details"):
        return {}

    if eval_id == "4.1":
        values = [d.get("total_tokens") for d in result["details"] if d.get("total_tokens") is not None]
        key = "tokens"
    elif eval_id == "4.2":
        values = [d.get("cost_usd") for d in result["details"] if d.get("cost_usd") is not None]
        key = "cost_usd"
    elif eval_id == "4.3":
        values = [d.get("duration_seconds") for d in result["details"] if d.get("duration_seconds") is not None]
        key = "duration_seconds"
    elif eval_id == "4.4":
        return {}
    else:
        return {}

    if not values:
        return {}

    sorted_vals = sorted(values)
    p95_idx = max(0, int(len(sorted_vals) * 0.95) - 1)

    return {
        "key":   key,
        "count": len(values),
        "min":   round(min(values), 3),
        "max":   round(max(values), 3),
        "avg":   round(statistics.mean(values), 3),
        "p95":   round(sorted_vals[p95_idx], 3),
    }


# ---------------------------------------------------------------------------
# Delta calculation
# ---------------------------------------------------------------------------

def _fetch_previous_scores(version_id: str, project_id: str) -> dict:
    """
    Find scores to compare against for delta calculation.

    Strategy:
    - If this IS the baseline version → compare against previous run of same version (run-over-run)
    - If this is ANY other version → always compare against the baseline version's last run
    - Nothing found → return empty dict (shows "first run")
    """
    eval_db = EvalSession()
    try:
        this_version = (
            eval_db.query(EvalVersion)
            .filter(EvalVersion.id == version_id)
            .first()
        )

        if this_version and this_version.is_baseline:
            # For baseline itself: compare against its own previous run
            previous_run = (
                eval_db.query(EvalRun)
                .filter(EvalRun.version_id == version_id)
                .filter(EvalRun.completed_at != None)
                .order_by(EvalRun.started_at.desc())
                .first()
            )
        else:
            # For all other versions: compare against baseline's last run
            baseline = (
                eval_db.query(EvalVersion)
                .filter(EvalVersion.is_baseline == True)
                .first()
            )
            if baseline:
                previous_run = (
                    eval_db.query(EvalRun)
                    .filter(EvalRun.version_id == baseline.id)
                    .filter(EvalRun.completed_at != None)
                    .order_by(EvalRun.started_at.desc())
                    .first()
                )
            else:
                # No baseline — fall back to most recent run of any other version
                previous_run = (
                    eval_db.query(EvalRun)
                    .filter(EvalRun.version_id != version_id)
                    .filter(EvalRun.completed_at != None)
                    .order_by(EvalRun.started_at.desc())
                    .first()
                )

        if not previous_run:
            return {}

        results = (
            eval_db.query(EvalResultModel)
            .filter(EvalResultModel.run_id == previous_run.id)
            .all()
        )
        return {r.eval_id: r.score for r in results}

    finally:
        eval_db.close()


def _calculate_delta(current_score: float, previous_score) -> dict:
    if previous_score is None:
        return {"value": None, "direction": "new", "display": "new", "prev": None, "curr": current_score}

    delta        = round(current_score - previous_score, 4)
    prev_pct     = round(previous_score * 100)
    curr_pct     = round(current_score  * 100)

    if delta > 0.005:
        return {"value": delta, "direction": "up",      "display": f"+{round(delta * 100, 1)}pp", "prev": prev_pct, "curr": curr_pct}
    elif delta < -0.005:
        return {"value": delta, "direction": "down",    "display": f"{round(delta * 100, 1)}pp",  "prev": prev_pct, "curr": curr_pct}
    else:
        return {"value": delta, "direction": "neutral", "display": "no change",                   "prev": prev_pct, "curr": curr_pct}



# ---------------------------------------------------------------------------
# Pipeline health
# ---------------------------------------------------------------------------

def fetch_pipeline_health():
    db = RRSession()
    try:
        projects = db.query(RRProject).order_by(RRProject.id.desc()).all()
        health   = []

        for project in projects:
            apps = db.query(RRApp).filter(RRApp.project_id == project.id).all()
            app_details = []

            for app in apps:
                analysis = (
                    db.query(RRAppAnalysis)
                    .filter(RRAppAnalysis.app_id == app.id)
                    .first()
                )
                app_details.append({
                    "app_id":         app.id,
                    "app_name":       app.name,
                    "review_count":   app.review_count,
                    "selected_count": app.selected_count,
                    "has_analysis":   analysis is not None,
                })

            cross = (
                db.query(RRAnalysis)
                .filter(RRAnalysis.project_id == project.id)
                .first()
            )

            total_reviews = sum(a.get("review_count") or 0 for a in app_details)

            health.append({
                "project_id":    project.id,
                "project_name":  project.name,
                "status":        project.status,
                "error_message": project.error_message,
                "period_start":  project.period_start,
                "period_end":    project.period_end,
                "apps":          app_details,
                "total_reviews": total_reviews,
                "has_cross":     cross is not None,
            })

        return health

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_all(
    version_id:   str,
    mode:         str = "existing_data",
    project_id:   str = None,
    selected_ids: list = None,
) -> dict:
    init_eval_db()

    if not project_id:
        return {"run_id": None, "results": [], "summary": {}, "db_error": "No project selected."}

    is_partial    = bool(selected_ids)
    run_id        = str(uuid.uuid4())
    eval_db       = EvalSession()
    _project_name = ""

    try:
        _rr_db = RRSession()
        _proj  = _rr_db.query(RRProject).filter(RRProject.id == project_id).first()
        _project_name = _proj.name if _proj else ""
        _rr_db.close()
    except Exception:
        pass

    run_record = EvalRun(
        id           = run_id,
        version_id   = version_id,
        mode         = "partial" if is_partial else mode,
        started_at   = datetime.utcnow(),
        project_name = _project_name,
    )
    eval_db.add(run_record)
    eval_db.commit()

    try:
        app_analyses, analyses, reviews, metrics = _fetch_rr_data(project_id)
    except Exception as e:
        eval_db.close()
        return {"run_id": run_id, "results": [], "summary": {}, "db_error": str(e)}

    previous_scores = _fetch_previous_scores(version_id, project_id)

    evals_to_run = []
    if selected_ids:
        for eid in selected_ids:
            module = EVAL_MAP.get(eid)
            if module:
                evals_to_run.append(module)
    else:
        evals_to_run = ALL_EVALS

    results = []

    for module in evals_to_run:
        eval_id = getattr(module, "EVAL_ID", None)

        try:
            if module in NEEDS_METRICS:
                result = module.run(app_analyses, analyses, metrics)
            elif module in NEEDS_REVIEWS:
                result = module.run(app_analyses, analyses, reviews)
            else:
                result = module.run(app_analyses, analyses)
        except Exception:
            result = EvalResult(
                eval_id = eval_id or "?",
                name    = getattr(module, "EVAL_NAME", "Unknown"),
                layer   = getattr(module, "LAYER", 0),
                error   = traceback.format_exc(),
            ).to_dict()

        # Attach criteria
        result["criteria"] = EVAL_CRITERIA.get(eval_id, "")

        # Compute metrics (P95 etc) for layer 4
        mj = _compute_metrics(result, metrics, eval_id or "")
        result["metrics"] = mj

        # Delta
        prev_score      = previous_scores.get(eval_id)
        result["delta"] = _calculate_delta(result.get("score", 0.0), prev_score)

        # Save to DB
        result_record = EvalResultModel(
            id           = str(uuid.uuid4()),
            run_id       = run_id,
            eval_id      = result.get("eval_id", ""),
            name         = result.get("name", ""),
            layer        = result.get("layer", 0),
            score        = result.get("score", 0.0),
            score_type   = result.get("score_type", "ratio"),
            threshold    = result.get("threshold", 0.0),
            passed_eval  = result.get("passed_eval", False),
            passed_count = result.get("passed", 0),
            failed_count = result.get("failed", 0),
            error        = result.get("error", ""),
            details_json = json.dumps(result.get("details", [])),
            metrics_json = json.dumps(mj) if mj else None,
            criteria     = result.get("criteria", ""),
            delta_json   = json.dumps(result.get("delta", {})),
        )
        eval_db.add(result_record)
        results.append(result)

    total  = len(results)
    passed = sum(1 for r in results if r.get("passed_eval"))
    failed = sum(1 for r in results if not r.get("passed_eval") and not r.get("error"))
    errors = sum(1 for r in results if r.get("error"))

    run_record.completed_at = datetime.utcnow()
    run_record.total_evals  = total
    run_record.passed_evals = passed
    run_record.failed_evals = failed
    run_record.error_evals  = errors
    eval_db.commit()
    eval_db.close()

    by_layer = {1: [], 2: [], 3: [], 4: []}
    for r in results:
        layer = r.get("layer", 0)
        if layer in by_layer:
            by_layer[layer].append(r)

    return {
        "run_id":     run_id,
        "results":    results,
        "is_partial": is_partial,
        "summary":    {"total": total, "passed": passed, "failed": failed, "errors": errors},
        "by_layer":   by_layer,
    }
