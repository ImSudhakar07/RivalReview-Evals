"""
evals/base.py
-------------
Defines the standard result structure every eval must return.

This is the contract between:
  - Individual eval modules  (they produce EvalResult)
  - The runner               (it collects EvalResult)
  - The dashboard            (it displays EvalResult)

Every eval module must implement:
  run(app_analyses, reviews, analyses) -> dict

And return EvalResult.to_dict() at the end.
"""

from dataclasses import dataclass, field, asdict


@dataclass
class EvalResult:
    eval_id:     str
    name:        str
    layer:       int
    passed:      int   = 0
    failed:      int   = 0
    skipped:     int   = 0
    score:       float = 0.0
    score_type:  str   = "ratio"    # "ratio" (0-1) or "likert" (1-5)
    threshold:   float = 0.0
    passed_eval: bool  = False
    error:       str   = ""
    details:     list  = field(default_factory=list)

    def finalise(self):
        """
        Call this after tallying all passed/failed counts.

        For ratio evals:  calculates score = passed / (passed + failed)
        For likert evals: score is set manually before calling finalise()

        Then sets passed_eval based on whether score meets threshold.
        """
        total = self.passed + self.failed
        if self.score_type == "ratio":
            self.score = round(self.passed / total, 4) if total > 0 else 0.0
        # Likert score is already set externally — don't overwrite it
        self.passed_eval = self.score >= self.threshold
        return self

    def to_dict(self) -> dict:
        return asdict(self)

"""
evals/base.py
-------------
Defines the standard result structure every eval must return.
"""

from dataclasses import dataclass, field, asdict


@dataclass
class EvalResult:
    eval_id:     str
    name:        str
    layer:       int
    passed:      int   = 0
    failed:      int   = 0
    skipped:     int   = 0
    score:       float = 0.0
    score_type:  str   = "ratio"
    threshold:   float = 0.0
    passed_eval: bool  = False
    error:       str   = ""
    details:     list  = field(default_factory=list)
    tag:         str   = ""       # "quality" | "reliability" | "coverage" | "cost" | "latency"

    def finalise(self):
        total = self.passed + self.failed
        if self.score_type == "ratio":
            self.score = round(self.passed / total, 4) if total > 0 else 0.0
        self.passed_eval = self.score >= self.threshold
        return self

    def to_dict(self) -> dict:
        return asdict(self)