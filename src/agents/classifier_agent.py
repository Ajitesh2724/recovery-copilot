import os
import sys
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from taxonomy.decline_codes import lookup, is_retryable
from agents import llm_client


def classify(decline_code):
    entry = lookup(decline_code)
    if entry is not None:
        return {
            "code": decline_code,
            "category": entry["category"],
            "retryable": is_retryable(decline_code),
            "retry_hint": entry["retry_hint"],
            "source": "rule",
        }
    return _classify_unknown(decline_code)


def _classify_unknown(decline_code):
    if llm_client.available():
        result = _ask_llm(decline_code)
        if result:
            return result

    # no key, or the LLM call failed -- conservative, safe default
    return {
        "code": decline_code,
        "category": "unknown",
        "retryable": False,
        "retry_hint": "manual_review_only",
        "source": "fallback_no_llm",
    }


def _ask_llm(decline_code):
    prompt = (
        f"Classify this payment gateway decline code: '{decline_code}'. "
        'Reply with ONLY this JSON, no markdown: '
        '{"category": "soft" or "hard" or "technical", "retryable": true or false, "reasoning": "under 6 words"}. '
        "soft = temporary, worth retrying same method. hard = permanent, don't retry same method. "
        "technical = bank/gateway issue, retry after a delay. If unsure, use hard and retryable=false."
    )
    raw = llm_client.call(prompt, max_tokens=1200)
    if not raw:
        return None

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        print("LLM classify: no JSON found in response:", raw)
        return None

    try:
        data = json.loads(match.group(0))
        return {
            "code": decline_code,
            "category": data["category"],
            "retryable": bool(data["retryable"]),
            "retry_hint": "immediate" if data["retryable"] else "manual_review_only",
            "source": "llm",
            "reasoning": data.get("reasoning", ""),
        }
    except (json.JSONDecodeError, KeyError) as e:
        print("LLM classify: failed to parse:", e, "raw:", raw)
        return None