"""
main.py — RivalReview Eval Dashboard
"""

import uuid
import json
from datetime import datetime

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import joinedload

from services.db import (
    EvalSession, EvalVersion, EvalRun,
    EvalResult as EvalResultModel,
    RRSession, RRProject,
    init_eval_db, load_json,
)
from evals.runner import run_all, fetch_pipeline_health
from config import RIVALREVIEW_DB_PATH, score_label, score_colour, to_ist, to_ist_short, to_ist_time

app       = FastAPI(title="RivalReview Eval Dashboard")
templates = Jinja2Templates(directory="templates")

templates.env.globals["to_ist"]       = to_ist
templates.env.globals["to_ist_short"] = to_ist_short
templates.env.globals["to_ist_time"]  = to_ist_time

init_eval_db()

_last_run: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_baseline(eval_db) -> EvalVersion:
    baseline = eval_db.query(EvalVersion).filter(EvalVersion.is_baseline == True).first()
    if not baseline:
        eval_db.query(EvalVersion).update({"is_current": False})
        baseline = EvalVersion(
            id          = str(uuid.uuid4()),
            name        = "v1.0-baseline",
            description = "Auto-created baseline. This is your starting point — all future versions compare against this.",
            created_at  = datetime.utcnow(),
            is_current  = True,
            is_baseline = True,
        )
        eval_db.add(baseline)
        eval_db.commit()
    return baseline


def _get_all_versions(eval_db) -> list:
    # Baseline first, then newest to oldest
    baseline = eval_db.query(EvalVersion).filter(EvalVersion.is_baseline == True).all()
    others   = (
        eval_db.query(EvalVersion)
        .filter(EvalVersion.is_baseline == False)
        .order_by(EvalVersion.created_at.desc())
        .all()
    )
    return baseline + others


def _serialise_versions(versions, version_run_counts=None) -> list:
    return [
        {
            "id":          v.id,
            "name":        v.name,
            "description": v.description or "",
            "created_at":  v.created_at,
            "is_current":  v.is_current,
            "is_baseline": v.is_baseline,
            "run_count":   (version_run_counts or {}).get(v.id, 0),
        }
        for v in versions
    ]


def _fmt_duration(seconds: float) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s}s"



# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, selected_project: str = ""):
    try:
        health   = fetch_pipeline_health()
        db_error = ""
    except Exception as e:
        health   = []
        db_error = str(e)

    try:
        rr_db       = RRSession()
        rr_projects = rr_db.query(RRProject).order_by(RRProject.id.desc()).all()
        rr_db.close()
    except Exception:
        rr_projects = []

    eval_db = EvalSession()
    _get_or_create_baseline(eval_db)

    all_versions = _get_all_versions(eval_db)

    recent_runs = (
        eval_db.query(EvalRun)
        .order_by(EvalRun.started_at.desc())
        .limit(5)
        .all()
    )

    recent_runs_data = []
    for run in recent_runs:
        recent_runs_data.append({
            "id":           run.id,
            "started_at":   run.started_at,
            "passed":       run.passed_evals or 0,
            "failed":       run.failed_evals or 0,
            "project_name": run.project_name or "",
        })

    current_version = next((v for v in all_versions if v.is_current), all_versions[0] if all_versions else None)
    eval_db.close()

    # Pre-select project: from query param, or last run, or first project
    if not selected_project:
        selected_project = _last_run.get("project_id", "")
    if not selected_project and rr_projects:
        selected_project = rr_projects[0].id

    selected_version = _last_run.get("version_id", current_version.id if current_version else "")

    return templates.TemplateResponse("dashboard.html", {
        "request":          request,
        "health":           health,
        "db_error":         db_error,
        "db_path":          RIVALREVIEW_DB_PATH,
        "current_version":  current_version,
        "all_versions":     all_versions,
        "recent_runs":      recent_runs_data,
        "last_run":         _last_run,
        "rr_projects":      rr_projects,
        "selected_project": selected_project,
        "selected_version": selected_version,
    })


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

@app.get("/versions", response_class=HTMLResponse)
async def versions_page(request: Request, error: str = ""):
    eval_db = EvalSession()
    _get_or_create_baseline(eval_db)

    versions = _get_all_versions(eval_db)

    version_run_counts  = {}
    version_last_scores = {}

    for v in versions:
        count = eval_db.query(EvalRun).filter(EvalRun.version_id == v.id).count()
        version_run_counts[v.id] = count

        last_run = (
            eval_db.query(EvalRun)
            .filter(EvalRun.version_id == v.id)
            .order_by(EvalRun.started_at.desc())
            .first()
        )
        if last_run:
            version_last_scores[v.id] = {
                "passed": last_run.passed_evals or 0,
                "failed": last_run.failed_evals or 0,
                "total":  last_run.total_evals or 0,
                "date":   last_run.started_at,
            }

    serialised = _serialise_versions(versions, version_run_counts)
    eval_db.close()

    return templates.TemplateResponse("versions.html", {
        "request":             request,
        "versions":            serialised,
        "version_last_scores": version_last_scores,
        "error":               error,
    })


@app.post("/versions")
async def create_version(
    name:        str = Form(...),
    description: str = Form(""),
):
    # Description is mandatory
    if not description.strip():
        return RedirectResponse(url="/versions?error=Please+describe+what+changed+in+this+version.", status_code=303)

    eval_db = EvalSession()
    # New version always becomes current
    eval_db.query(EvalVersion).update({"is_current": False})
    version = EvalVersion(
        id          = str(uuid.uuid4()),
        name        = name.strip(),
        description = description.strip(),
        created_at  = datetime.utcnow(),
        is_current  = True,
        is_baseline = False,
    )
    eval_db.add(version)
    eval_db.commit()
    eval_db.close()
    return RedirectResponse(url="/versions", status_code=303)


@app.post("/versions/{version_id}/set-current")
async def set_current_version(version_id: str):
    eval_db = EvalSession()
    eval_db.query(EvalVersion).update({"is_current": False})
    eval_db.query(EvalVersion).filter(EvalVersion.id == version_id).update({"is_current": True})
    eval_db.commit()
    eval_db.close()
    return RedirectResponse(url="/versions", status_code=303)


@app.post("/versions/{version_id}/delete")
async def delete_version(version_id: str):
    eval_db = EvalSession()
    version = eval_db.query(EvalVersion).filter(EvalVersion.id == version_id).first()
    if version and not version.is_baseline:
        # Delete all runs and results for this version
        runs = eval_db.query(EvalRun).filter(EvalRun.version_id == version_id).all()
        for run in runs:
            eval_db.query(EvalResultModel).filter(EvalResultModel.run_id == run.id).delete()
        eval_db.query(EvalRun).filter(EvalRun.version_id == version_id).delete()
        eval_db.delete(version)
        eval_db.commit()
    eval_db.close()
    return RedirectResponse(url="/versions", status_code=303)



# ---------------------------------------------------------------------------
# Run evals
# ---------------------------------------------------------------------------

@app.post("/run")
async def run_evals(
    version_id: str = Form(...),
    project_id: str = Form(...),
):
    global _last_run
    _last_run = run_all(version_id=version_id, mode="existing_data", project_id=project_id)
    _last_run["project_id"] = project_id
    _last_run["version_id"] = version_id
    return RedirectResponse(url="/", status_code=303)


@app.post("/run-single")
async def run_single_eval(
    eval_id:    str = Form(...),
    project_id: str = Form(...),
    version_id: str = Form(...),
):
    global _last_run
    result = run_all(version_id=version_id, mode="existing_data", project_id=project_id, selected_ids=[eval_id])

    if _last_run.get("results"):
        for new_r in result.get("results", []):
            for i, existing_r in enumerate(_last_run["results"]):
                if existing_r["eval_id"] == new_r["eval_id"]:
                    _last_run["results"][i] = new_r
                    break
            else:
                _last_run["results"].append(new_r)

        by_layer = {1: [], 2: [], 3: [], 4: []}
        for r in _last_run["results"]:
            layer = r.get("layer", 0)
            if layer in by_layer:
                by_layer[layer].append(r)
        _last_run["by_layer"]   = by_layer
        _last_run["is_partial"] = True
    else:
        _last_run               = result
        _last_run["project_id"] = project_id
        _last_run["version_id"] = version_id
        _last_run["is_partial"] = True

    return RedirectResponse(url="/", status_code=303)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    eval_db = EvalSession()

    runs = (
        eval_db.query(EvalRun)
        .options(joinedload(EvalRun.version))
        .order_by(EvalRun.started_at.desc())
        .limit(50)
        .all()
    )

    runs_data = []
    for run in runs:
        runs_data.append({
            "id":           run.id,
            "started_at":   run.started_at,
            "passed":       run.passed_evals or 0,
            "failed":       run.failed_evals or 0,
            "errors":       run.error_evals or 0,
            "total":        run.total_evals or 0,
            "version_name": run.version.name if run.version else "—",
            "version_id":   run.version_id,
            "project_name": run.project_name or "—",
            "is_baseline":  run.version.is_baseline if run.version else False,
        })

    versions = _get_all_versions(eval_db)
    eval_db.close()

    return templates.TemplateResponse("history.html", {
        "request":  request,
        "runs":     runs_data,
        "versions": _serialise_versions(versions),
    })


@app.post("/history/{run_id}/delete")
async def delete_run(run_id: str):
    eval_db = EvalSession()
    # Protect baseline runs
    run = eval_db.query(EvalRun).options(joinedload(EvalRun.version)).filter(EvalRun.id == run_id).first()
    if run and (not run.version or not run.version.is_baseline):
        eval_db.query(EvalResultModel).filter(EvalResultModel.run_id == run_id).delete()
        eval_db.query(EvalRun).filter(EvalRun.id == run_id).delete()
        eval_db.commit()
    eval_db.close()
    return RedirectResponse(url="/history", status_code=303)


# ---------------------------------------------------------------------------
# Run detail
# ---------------------------------------------------------------------------

@app.get("/history/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    eval_db = EvalSession()
    run     = eval_db.query(EvalRun).filter(EvalRun.id == run_id).first()

    run_data = None
    if run:
        duration = None
        if run.started_at and run.completed_at:
            duration = (run.completed_at - run.started_at).total_seconds()
        run_data = {
            "id":           run.id[:8],
            "mode":         run.mode,
            "started_at":   run.started_at,
            "completed_at": run.completed_at,
            "total_evals":  run.total_evals or 0,
            "passed_evals": run.passed_evals or 0,
            "failed_evals": run.failed_evals or 0,
            "error_evals":  run.error_evals or 0,
            "project_name": run.project_name or "—",
            "duration":     _fmt_duration(duration),
        }

    results = (
        eval_db.query(EvalResultModel)
        .filter(EvalResultModel.run_id == run_id)
        .all()
    )

    parsed_results = []
    for r in results:
        parsed_results.append({
            "eval_id":     r.eval_id,
            "name":        r.name,
            "layer":       r.layer,
            "score":       r.score,
            "score_type":  r.score_type,
            "threshold":   r.threshold,
            "passed_eval": r.passed_eval,
            "passed":      r.passed_count,
            "failed":      r.failed_count,
            "error":       r.error,
            "details":     load_json(r.details_json) or [],
            "metrics":     load_json(r.metrics_json) or {},
            "criteria":    r.criteria or "",
            "delta":       load_json(r.delta_json) or {},
        })

    eval_db.close()

    # Sort: failing first within each layer
    by_layer = {1: [], 2: [], 3: [], 4: []}
    for r in parsed_results:
        layer = r.get("layer", 0)
        if layer in by_layer:
            by_layer[layer].append(r)

    for layer_num in by_layer:
        by_layer[layer_num].sort(key=lambda x: (x.get("passed_eval", True), x.get("score", 1.0)))

    return templates.TemplateResponse("run_detail.html", {
        "request":  request,
        "run":      run_data,
        "results":  parsed_results,
        "by_layer": by_layer,
    })


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

@app.get("/compare", response_class=HTMLResponse)
async def compare_versions(request: Request, version_a: str = "", version_b: str = ""):
    eval_db      = EvalSession()
    versions     = _get_all_versions(eval_db)
    versions_ser = _serialise_versions(versions)
    compare_data = []

    if version_a and version_b:
        def get_last_run_results(vid):
            last_run = (
                eval_db.query(EvalRun)
                .filter(EvalRun.version_id == vid)
                .order_by(EvalRun.started_at.desc())
                .first()
            )
            if not last_run:
                return {}, {}, {}, None
            results = eval_db.query(EvalResultModel).filter(EvalResultModel.run_id == last_run.id).all()
            scores  = {r.eval_id: r.score for r in results}
            metrics = {r.eval_id: load_json(r.metrics_json) or {} for r in results}
            names   = {r.eval_id: r.name for r in results}
            return scores, metrics, names, last_run

        scores_a, metrics_a, names_a, run_a = get_last_run_results(version_a)
        scores_b, metrics_b, names_b, run_b = get_last_run_results(version_b)

        ver_a = next((v for v in versions if v.id == version_a), None)
        ver_b = next((v for v in versions if v.id == version_b), None)

        all_ids = sorted(set(list(scores_a.keys()) + list(scores_b.keys())))

        for eval_id in all_ids:
            score_a = scores_a.get(eval_id)
            score_b = scores_b.get(eval_id)
            m_a     = metrics_a.get(eval_id, {})
            m_b     = metrics_b.get(eval_id, {})

            if score_a is not None and score_b is not None:
                delta = round(score_b - score_a, 4)
                if delta > 0.005:   direction = "up"
                elif delta < -0.005: direction = "down"
                else:               direction = "neutral"
            else:
                delta     = None
                direction = "new"

            compare_data.append({
                "eval_id":   eval_id,
                "name":      names_a.get(eval_id) or names_b.get(eval_id) or eval_id,
                "score_a":   score_a,
                "score_b":   score_b,
                "delta":     delta,
                "direction": direction,
                "metrics_a": m_a,
                "metrics_b": m_b,
            })

        eval_db.close()
        return templates.TemplateResponse("compare.html", {
            "request":    request,
            "versions":   versions_ser,
            "version_a":  version_a,
            "version_b":  version_b,
            "ver_a_name": ver_a.name if ver_a else "—",
            "ver_b_name": ver_b.name if ver_b else "—",
            "run_a":      run_a,
            "run_b":      run_b,
            "compare":    compare_data,
        })

    eval_db.close()
    return templates.TemplateResponse("compare.html", {
        "request":   request,
        "versions":  versions_ser,
        "version_a": version_a,
        "version_b": version_b,
        "compare":   [],
    })
