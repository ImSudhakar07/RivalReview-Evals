# Architecture

This document covers two things: how the RivalReview AI pipeline works, and how the eval platform monitors it.

---

## 1. RivalReview Pipeline

RivalReview processes app store reviews through three sequential AI agents. Each agent is independently evaluated by the eval platform.

```mermaid
flowchart TD
    subgraph INPUT["Input"]
        RS[App Store Reviews\nPlay Store / App Store]
        PM[Project Config\nApps + Date Range]
    end

    subgraph LAYER1["Layer 1 — Monthly Batch Agent"]
        MBA[monthly_batch_agent\nProcesses reviews month by month]
        MBA_OUT["Per-app monthly output:\n• Pain points\n• Loves\n• Feature requests\n• Theme excerpts\n• Sentiment labels\n• Volume counts"]
    end

    subgraph LAYER2["Layer 2 — App Synthesis Agent"]
        ASA[app_synthesis_agent\nSynthesises across months per app]
        ASA_OUT["Per-app analysis:\n• Ranked themes\n• Deduplicated pain points\n• Actionable summary\n• Quality score"]
    end

    subgraph LAYER3["Layer 3 — Cross-App Synthesis Agent"]
        CAA[cross_app_agent\nSynthesises across all apps]
        CAA_OUT["Project-level analysis:\n• Sentiment trend\n• Differentiators\n• Combined summary\n• Shared pain points"]
    end

    subgraph OUTPUT["Output"]
        DASH[RivalReview Dashboard\nResults displayed to user]
    end

    RS --> MBA
    PM --> MBA
    MBA --> MBA_OUT
    MBA_OUT --> ASA
    ASA --> ASA_OUT
    ASA_OUT --> CAA
    CAA --> CAA_OUT
    CAA_OUT --> DASH

    style INPUT  fill:#09090b,stroke:#27272a,color:#71717a
    style LAYER1 fill:#0a1520,stroke:#1e3a5f,color:#38bdf8
    style LAYER2 fill:#0a1520,stroke:#1e3a5f,color:#38bdf8
    style LAYER3 fill:#0a1520,stroke:#1e3a5f,color:#38bdf8
    style OUTPUT fill:#09090b,stroke:#27272a,color:#71717a
```

---

## 2. Eval Platform Architecture

The eval platform sits alongside RivalReview, reads its database read-only, and runs quality checks against the pipeline outputs.

```mermaid
flowchart TD
    subgraph RR["RivalReview DB (read-only)"]
        RR_DB[(rivalreview.db\nprojects, apps, reviews\napp_analyses, analyses\nagent_metrics)]
    end

    subgraph EVALS["Eval Platform"]
        RUNNER[runner.py\nOrchestrates all eval runs]

        subgraph L1["Layer 1 — Monthly Batch Agent"]
            E11[1.1 Schema Validation]
            E12[1.2 Theme Specificity]
            E13[1.3 Excerpt Relevance\nLLM judge]
            E14[1.4 Sentiment Accuracy]
            E15[1.5 Volume Plausibility]
        end

        subgraph L2["Layer 2 — App Synthesis Agent"]
            E21[2.1 Theme Deduplication]
            E22[2.2 Volume Consistency]
            E23[2.3 Ranking Correctness]
            E24[2.4 Summary Actionability\nLLM judge]
            E25[2.5 Coverage]
            E26[2.6 Excerpt Traceability]
        end

        subgraph L3["Layer 3 — Cross-App Agent"]
            E31[3.1 Sentiment Trend Math]
            E32[3.2 Sentiment Completeness]
            E34[3.4 Differentiator Accuracy]
            E35[3.5 Summary Depth\nLLM judge]
        end

        subgraph L4["Layer 4 — Cost and Latency"]
            E41[4.1 Token Usage\nP95 tracked]
            E42[4.2 Cost Per Run]
            E43[4.3 Latency\nP95 tracked]
            E44[4.4 Retry Rate]
        end

        GROK[Grok API\ngrok-3-mini\nLLM judge calls]
        EVAL_DB[(evalstore.db\nversions, runs, results)]
    end

    subgraph DASHBOARD["Dashboard — localhost:8001"]
        D1[Dashboard\nRun evals + live results]
        D2[History\nAll past runs]
        D3[Versions\nVersion management]
        D4[Compare\nSide-by-side version comparison]
        D5[Run Detail\nPer-eval drilldown]
    end

    RR_DB -->|fetch project data| RUNNER
    RUNNER --> L1
    RUNNER --> L2
    RUNNER --> L3
    RUNNER --> L4
    E13 & E24 & E35 -->|judge prompts| GROK
    GROK -->|scores| RUNNER
    RUNNER -->|save results + deltas| EVAL_DB
    EVAL_DB --> DASHBOARD

    style RR        fill:#1a0a00,stroke:#7c2d12,color:#fb923c
    style EVALS     fill:#09090b,stroke:#27272a,color:#f4f4f5
    style L1        fill:#0a1520,stroke:#1e3a5f,color:#38bdf8
    style L2        fill:#0a1520,stroke:#1e3a5f,color:#38bdf8
    style L3        fill:#0a1520,stroke:#1e3a5f,color:#38bdf8
    style L4        fill:#0d1a0d,stroke:#14532d,color:#34d399
    style DASHBOARD fill:#0d0d1a,stroke:#312e81,color:#a5b4fc
```

---

## 3. Delta and Versioning Model

```mermaid
flowchart LR
    subgraph VERSIONS["Version lifecycle"]
        BL["v1.0-baseline\n(protected anchor)"]
        V1["v1.1-prompt-fix\n(new version)"]
        V2["v1.2-next-change\n(new version)"]
    end

    subgraph DELTA["Delta calculation"]
        D1["New version run\n→ compare vs baseline's\nlast run"]
        D2["Re-run same version\n→ compare vs same\nversion's last run"]
    end

    BL -->|"first run ever\nno delta → first run"| BL
    BL -->|"re-run baseline\ndelta vs its own prev run"| D2
    V1 -->|"first run of v1.1\ndelta vs baseline"| D1
    V1 -->|"second run of v1.1\ndelta vs v1.1 prev run"| D2
    V2 -->|"first run of v1.2\ndelta vs baseline"| D1

    style VERSIONS fill:#09090b,stroke:#27272a,color:#f4f4f5
    style DELTA    fill:#0a1520,stroke:#1e3a5f,color:#38bdf8
```

---

## 4. Data flow summary

| Step | What happens |
|------|-------------|
| User clicks Run All Evals | `POST /run` → `runner.run_all()` |
| Runner fetches data | Reads `rivalreview.db` for the selected project |
| Runner fetches previous scores | Finds baseline's last run for delta comparison |
| Each eval runs | Returns `EvalResult.to_dict()` with score, details, pass/fail |
| Layer 4 evals | Also compute P95/avg/min/max from `agent_metrics` table |
| LLM judge evals | Call Grok API with eval prompt, parse score from response |
| Results saved | Written to `evalstore.db` with delta, criteria, metrics JSON |
| Dashboard renders | Reads from `evalstore.db`, displays per-layer results with deltas |

---

## 5. Eval result structure

Every eval returns a standard dict defined in `evals/base.py`:

```
EvalResult
├── eval_id       "1.2"
├── name          "Theme Specificity"
├── layer         1
├── score         0.99          ← ratio 0.0–1.0
├── threshold     0.90          ← from config.py THRESHOLDS
├── passed_eval   true          ← score >= threshold
├── passed        47            ← count of passing items
├── failed        1             ← count of failing items
├── criteria      "≥90% of themes must be specific..."
├── delta         { prev: 99, curr: 99, direction: "neutral" }
├── metrics       { p95, avg, min, max }  ← layer 4 only
└── details       [ { item_id, passed, note }, ... ]
```
