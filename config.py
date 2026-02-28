"""
config.py
---------
Single source of truth for all configuration.

All settings are read from environment variables via .env file.
Never hardcode paths or secrets here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Database paths
# ---------------------------------------------------------------------------

RIVALREVIEW_DB_PATH = os.getenv(
    "RIVALREVIEW_DB_PATH",
    r"C:\Users\12322\Documents\RivalReview\rivalreview.db"
)

EVALSTORE_DB_PATH = os.getenv(
    "EVALSTORE_DB_PATH",
    r"C:\Users\12322\Documents\RivalReview-Evals\evalstore.db"
)

# ---------------------------------------------------------------------------
# Grok API
# ---------------------------------------------------------------------------

GROK_API_KEY      = os.getenv("GROK_API_KEY", "")
GROK_API_BASE_URL = os.getenv("GROK_API_BASE_URL", "https://api.x.ai/v1")
GROK_MODEL        = os.getenv("GROK_MODEL", "grok-3-mini")
GROK_TEMPERATURE  = float(os.getenv("GROK_TEMPERATURE", "0.1"))

# ---------------------------------------------------------------------------
# Eval thresholds
# ---------------------------------------------------------------------------
# One entry per eval_id.
# Value is the minimum score (0.0 to 1.0) required to pass.
# These are the single source of truth — never hardcode thresholds in eval files.

THRESHOLDS: dict[str, float] = {
    # Layer 1 — Monthly Batch Agent
    "1.1": 1.00,   # Schema Validation — must be perfect
    "1.2": 0.90,   # Theme Specificity — 90% must be 2+ words
    "1.3": 0.80,   # Excerpt Relevance — 80% of sampled themes score >= 3.5
    "1.4": 0.80,   # Sentiment Accuracy — 80% within 15pp tolerance
    "1.5": 1.00,   # Volume Plausibility — must be perfect
    "1.6": 0.80,   # Retry Effectiveness — deferred, placeholder

    # Layer 2 — App Synthesis Agent
    "2.1": 0.90,   # Theme Deduplication — 90% of pairs below 80% similarity
    "2.2": 1.00,   # Volume Consistency — must be perfect
    "2.3": 1.00,   # Ranking Correctness — must be perfect
    "2.4": 0.80,   # Summary Actionability — 80% pass all checks
    "2.5": 0.95,   # Coverage — 95% of top 5 themes traceable
    "2.6": 0.85,   # Excerpt Traceability — 85% traceable to source reviews

    # Layer 3 — Cross-App Synthesis Agent
    "3.1": 1.00,   # Sentiment Trend Math — deterministic, must be perfect
    "3.2": 1.00,   # Sentiment Completeness — must be perfect
    "3.4": 0.80,   # Differentiator Accuracy — 80% traceable to loves
    "3.5": 0.80,   # Summary Depth — 80% pass all checks

   # Layer 4 — Cost & Latency
    "4.1": 0.90,   # Token Usage — 90% of calls within expected range
    "4.2": 1.00,   # Cost Per Run — must be under $2.00
    "4.3": 0.90,   # Latency — 90% of calls within time limit
    "4.4": 1.00,   # Retry Rate — no agent exceeds 150% expected calls
}

# ---------------------------------------------------------------------------
# Dashboard helpers
# ---------------------------------------------------------------------------

def score_label(score: float) -> str:
    """Human readable label for a score."""
    if score >= 0.9:
        return "Excellent"
    elif score >= 0.7:
        return "Good"
    elif score >= 0.5:
        return "Fair"
    else:
        return "Poor"


def score_colour(score: float) -> str:
    """Tailwind colour class for a score."""
    if score >= 0.9:
        return "text-emerald-400"
    elif score >= 0.7:
        return "text-sky-400"
    elif score >= 0.5:
        return "text-amber-400"
    else:
        return "text-red-400"

# ---------------------------------------------------------------------------
# Timezone helper
# ---------------------------------------------------------------------------

from datetime import timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def to_ist(dt) -> str:
    """Convert a UTC datetime to IST string for display."""
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%d %b %Y, %H:%M IST")


def to_ist_short(dt) -> str:
    """Short IST format — date only."""
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%d %b %Y")


def to_ist_time(dt) -> str:
    """Time only in IST."""
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%H:%M IST")