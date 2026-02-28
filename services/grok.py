"""
services/grok.py
----------------
Grok-as-judge client for LLM-based eval scoring.

Used by evals that cannot be checked programmatically:
  - Eval 1.3  excerpt relevance
  - Eval 2.4  summary actionability
  - Eval 3.5  summary depth

Temperature is set very low (0.1) to make scoring as consistent as possible.
"""

import json
import httpx

from config import GROK_API_KEY, GROK_API_BASE_URL, GROK_MODEL, GROK_TEMPERATURE

GROK_JUDGE_TIMEOUT = 60.0  # seconds — LLM calls can be slow


class GrokJudgeError(Exception):
    """Raised when the Grok judge call fails or returns unparseable output."""
    pass


def judge(criteria: str, content: str) -> dict:
    """
    Score content against criteria using Grok as the judge.

    Args:
        criteria: What we are evaluating. Be specific.
        content:  The actual content to evaluate.

    Returns:
        {"score": int (1-5), "reason": str}

    Raises:
        GrokJudgeError if the API call fails or response cannot be parsed.
    """
    if not GROK_API_KEY:
        raise GrokJudgeError(
            "GROK_API_KEY is not set in your .env file. "
            "LLM-as-judge evals cannot run without it."
        )

    prompt = f"""You are an expert evaluator. Score the following on a scale of 1-5 where:
1 = completely fails the criteria
3 = partially meets the criteria
5 = fully meets the criteria

Criteria: {criteria}

Content to evaluate:
{content}

Respond ONLY with a JSON object:
{{"score": <1-5>, "reason": "<one sentence explanation>"}}"""

    payload = {
        "model":       GROK_MODEL,
        "temperature": GROK_TEMPERATURE,
        "max_tokens":  150,
        "messages":    [{"role": "user", "content": prompt}],
    }

    url = f"{GROK_API_BASE_URL}/chat/completions"

    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=GROK_JUDGE_TIMEOUT,
        )
        response.raise_for_status()

    except httpx.HTTPStatusError as e:
        raise GrokJudgeError(
            f"Grok API returned {e.response.status_code}: {e.response.text}"
        )
    except httpx.RequestError as e:
        raise GrokJudgeError(f"Network error calling Grok: {e}")

    raw = response.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        result = json.loads(raw)
        return {
            "score":  int(result["score"]),
            "reason": str(result["reason"]),
        }
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise GrokJudgeError(
            f"Could not parse Grok judge response: {raw!r} — {e}"
        )