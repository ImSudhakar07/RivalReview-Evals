# RivalReview Evals

An internal eval platform that continuously monitors the quality of the [RivalReview](https://github.com/ImSudhakar07/Rival-review) AI pipeline. Built with FastAPI and SQLite, it runs 19 automated evals across 4 layers — from raw output schema checks to cost and latency tracking.

---

## What it does

RivalReview uses multiple AI agents to process app store reviews and generate competitive analysis. This eval platform answers the question: **did a pipeline change make things better or worse?**

Every eval run produces a score per eval, a pass/fail against a threshold, and a delta vs the baseline version. Results are stored, versioned, and comparable over time through a web dashboard.

---

## Project structure

```
RivalReview-Evals/
├── main.py                  # FastAPI app — all routes
├── config.py                # Thresholds, DB paths, env config
├── requirements.txt
├── .env.example
│
├── evals/
│   ├── base.py              # EvalResult dataclass — contract for all evals
│   ├── runner.py            # Orchestrates runs, computes deltas, saves results
│   ├── layer1/              # Monthly Batch Agent evals (1.1–1.5)
│   ├── layer2/              # App Synthesis Agent evals (2.1–2.6)
│   ├── layer3/              # Cross-App Synthesis Agent evals (3.1–3.5)
│   └── layer4/              # Cost & Latency evals (4.1–4.4)
│
├── services/
│   ├── db.py                # SQLAlchemy models for both DBs
│   └── grok.py              # Grok API client (used by judge evals)
│
└── templates/               # Jinja2 HTML templates
    ├── dashboard.html
    ├── history.html
    ├── versions.html
    ├── run_detail.html
    └── compare.html
```

---

## Prerequisites

- Python 3.11+
- A running [RivalReview](https://github.com/ImSudhakar07/Rival-review) instance with a populated `rivalreview.db`
- A Grok API key (used by LLM judge evals — 1.3, 2.4, 3.5)

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/your-username/rivalreview-evals.git
cd rivalreview-evals
```

**2. Create and activate virtual environment**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment**
```bash
cp .env.example .env
```

Edit `.env` with your values:
```env
RIVALREVIEW_DB_PATH=C:\path\to\rivalreview.db
EVALSTORE_DB_PATH=C:\path\to\evalstore.db
GROK_API_KEY=your_grok_api_key_here
GROK_MODEL=grok-3-mini
```

**5. Run the server**
```bash
uvicorn main:app --reload --port 8001
```

Open `http://localhost:8001` in your browser.

---

## How to use

### Running evals
1. Go to the dashboard at `http://localhost:8001`
2. Click a project card to select it
3. Choose a version from the dropdown
4. Click **Run All Evals**

### Versioning
- Every meaningful pipeline change should be a new version
- Go to **Versions** → create a new version with a description of what changed
- New versions automatically become the current version
- The baseline version (`v1.0-baseline`) is protected and cannot be deleted — it is the anchor all other versions compare against

### Comparing versions
- Go to **Compare** and select two versions
- Scores are shown side by side per eval with delta
- Use this after making a pipeline change to confirm improvement

### Viewing run history
- Go to **History** to see all past runs
- Click any run to see full eval results, criteria, scores, and deltas

---

## Eval layers

| Layer | Agent | Evals | What it checks |
|-------|-------|-------|----------------|
| 1 | Monthly Batch Agent | 1.1–1.5 | Schema validity, theme specificity, excerpt relevance, sentiment accuracy, volume plausibility |
| 2 | App Synthesis Agent | 2.1–2.6 | Theme deduplication, volume consistency, ranking correctness, summary actionability, coverage, excerpt traceability |
| 3 | Cross-App Synthesis Agent | 3.1–3.5 | Sentiment trend math, sentiment completeness, differentiator accuracy, summary depth |
| 4 | All Agents | 4.1–4.4 | Token usage, cost per run, latency, retry rate |

---

## How to add a new eval

1. Create a new file in the correct layer folder, e.g. `evals/layer2/eval_2_7_my_eval.py`
2. Follow this structure:

```python
from evals.base import EvalResult
from config import THRESHOLDS

EVAL_ID   = "2.7"
EVAL_NAME = "My New Eval"
LAYER     = 2

def run(app_analyses: list[dict], analyses: list[dict]) -> dict:
    result = EvalResult(
        eval_id   = EVAL_ID,
        name      = EVAL_NAME,
        layer     = LAYER,
        threshold = THRESHOLDS[EVAL_ID],
    )

    for item in app_analyses:
        passed = # your check here
        if passed:
            result.passed += 1
        else:
            result.failed += 1
        result.details.append({
            "item_id": item["app_id"],
            "passed":  passed,
            "note":    "...",
        })

    result.finalise()
    return result.to_dict()
```

3. Add the threshold to `config.py` under `THRESHOLDS`
4. Import and register it in `evals/runner.py`:
   - Import at the top
   - Add to `ALL_EVALS` list
   - Add to `NEEDS_REVIEWS` or `NEEDS_METRICS` sets if needed
   - Add a criteria string to `EVAL_CRITERIA` dict

That's it — the runner, dashboard, history, and compare pages all handle it automatically.

---

## Tech stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI |
| Templates | Jinja2 |
| Database | SQLite via SQLAlchemy |
| LLM judge | Grok API (grok-3-mini) |
| Fuzzy matching | thefuzz |
| Frontend | Vanilla HTML + Tailwind CDN |

---

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RIVALREVIEW_DB_PATH` | Path to RivalReview's SQLite DB | — |
| `EVALSTORE_DB_PATH` | Path to eval platform's SQLite DB | `./evalstore.db` |
| `GROK_API_KEY` | Grok API key for LLM judge evals | — |
| `GROK_MODEL` | Grok model to use | `grok-3-mini` |
| `GROK_TEMPERATURE` | Temperature for judge calls | `0.1` |
