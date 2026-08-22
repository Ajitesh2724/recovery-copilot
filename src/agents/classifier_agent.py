import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from taxonomy.decline_codes import lookup, is_retryable


def classify(decline_code):
    """
    Returns a dict describing what we know about this failure.
    Rule-based path first -- fast, free, explainable.
    Falls back to the LLM path only for codes we've never seen.
    """
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
    """
    Codes not in our taxonomy go here. This is where an LLM call belongs --
    kept as a stub for now since it needs an API key we haven't wired up yet.
    Defaults conservatively: unknown codes are treated as non-retryable
    until a human or the LLM says otherwise, since guessing wrong on an
    unknown code is worse than being cautious.
    """
    if os.getenv("USE_LLM_FALLBACK") == "1":
        # TODO: call the LLM here once the API key is set up
        raise NotImplementedError("LLM fallback not wired up yet")

    return {
        "code": decline_code,
        "category": "unknown",
        "retryable": False,
        "retry_hint": "manual_review_only",
        "source": "fallback_no_llm",
    }