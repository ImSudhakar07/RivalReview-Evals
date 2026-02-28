"""
services/db.py
--------------
All database access for the eval platform.
"""

import json
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    Text, DateTime, Boolean, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from config import RIVALREVIEW_DB_PATH, EVALSTORE_DB_PATH as EVAL_DB_PATH

RRBase   = declarative_base()
EvalBase = declarative_base()

rr_engine = create_engine(
    f"sqlite:///{RIVALREVIEW_DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)
RRSession = sessionmaker(bind=rr_engine, autocommit=False, autoflush=False)


class RRProject(RRBase):
    __tablename__ = "projects"
    id                   = Column(String, primary_key=True)
    name                 = Column(String)
    store                = Column(String)
    status               = Column(String)
    progress_percent     = Column(Integer)
    current_status_label = Column(String)
    error_message        = Column(Text)
    period_start         = Column(DateTime)
    period_end           = Column(DateTime)


class RRApp(RRBase):
    __tablename__ = "apps"
    id                = Column(String, primary_key=True)
    project_id        = Column(String)
    name              = Column(String)
    review_count      = Column(Integer)
    selected_count    = Column(Integer)
    sampling_strategy = Column(String)


class RRReview(RRBase):
    __tablename__ = "reviews"
    id     = Column(String, primary_key=True)
    app_id = Column(String)
    text   = Column(Text, nullable=True)
    rating = Column(Integer)
    date   = Column(DateTime)


class RRAppAnalysis(RRBase):
    __tablename__ = "app_analyses"
    id                  = Column(String, primary_key=True)
    app_id              = Column(String)
    monthly_batches     = Column(Text)
    pain_points         = Column(Text)
    loves               = Column(Text)
    feature_requests    = Column(Text)
    top_review_excerpts = Column(Text)
    summary_text        = Column(Text)
    quality_score       = Column(Float)


class RRAnalysis(RRBase):
    __tablename__ = "analyses"
    id                  = Column(String, primary_key=True)
    project_id          = Column(String)
    sentiment_trend     = Column(Text)
    combined_summary    = Column(Text)
    quality_score       = Column(Float)
    differentiators     = Column(Text, nullable=True)
    shared_pain_points  = Column(Text, nullable=True)


class RRAgentMetrics(RRBase):
    __tablename__ = "agent_metrics"
    id                = Column(String, primary_key=True)
    agent_name        = Column(String)
    app_id            = Column(String, nullable=True)
    project_id        = Column(String, nullable=True)
    prompt_tokens     = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens      = Column(Integer)
    duration_seconds  = Column(Float)
    cost_usd          = Column(Float)
    called_at         = Column(DateTime)


eval_engine = create_engine(
    f"sqlite:///{EVAL_DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)
EvalSession = sessionmaker(bind=eval_engine, autocommit=False, autoflush=False)


class EvalVersion(EvalBase):
    __tablename__ = "eval_versions"
    id          = Column(String, primary_key=True)
    name        = Column(String)
    description = Column(Text)
    created_at  = Column(DateTime, default=datetime.utcnow)
    is_current  = Column(Boolean, default=False)
    is_baseline = Column(Boolean, default=False)

    runs = relationship("EvalRun", back_populates="version")


class EvalRun(EvalBase):
    __tablename__ = "eval_runs"
    id             = Column(String, primary_key=True)
    version_id     = Column(String, ForeignKey("eval_versions.id"))
    mode           = Column(String)
    started_at     = Column(DateTime, default=datetime.utcnow)
    completed_at   = Column(DateTime, nullable=True)
    total_evals    = Column(Integer, default=0)
    passed_evals   = Column(Integer, default=0)
    failed_evals   = Column(Integer, default=0)
    error_evals    = Column(Integer, default=0)
    notes          = Column(Text)
    project_name   = Column(String, nullable=True)

    version = relationship("EvalVersion", back_populates="runs")
    results = relationship("EvalResult", back_populates="run")


class EvalResult(EvalBase):
    __tablename__ = "eval_results"
    id           = Column(String, primary_key=True)
    run_id       = Column(String, ForeignKey("eval_runs.id"))
    eval_id      = Column(String)
    name         = Column(String)
    layer        = Column(Integer)
    score        = Column(Float)
    score_type   = Column(String)
    threshold    = Column(Float)
    passed_eval  = Column(Boolean)
    passed_count = Column(Integer)
    failed_count = Column(Integer)
    error        = Column(Text)
    details_json = Column(Text)
    metrics_json = Column(Text, nullable=True)   # P95/avg/min/max stats
    criteria     = Column(Text, nullable=True)   # human-readable pass criteria
    delta_json   = Column(Text, nullable=True)   # delta vs previous run

    run = relationship("EvalRun", back_populates="results")


def init_eval_db():
    EvalBase.metadata.create_all(eval_engine)


def load_json(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def get_rr_session():
    db = RRSession()
    try:
        yield db
    finally:
        db.close()


def get_eval_session():
    db = EvalSession()
    try:
        yield db
    finally:
        db.close()
