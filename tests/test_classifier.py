import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agents.classifier_agent import classify


def test_known_code_uses_rule():
    result = classify("card_expired")
    assert result["source"] == "rule"
    assert result["category"] == "hard"


def test_unknown_code_defaults_to_manual_review():
    result = classify("something_totally_new")
    assert result["source"] == "fallback_no_llm"
    assert result["retryable"] is False


def test_fraud_code_not_retryable():
    result = classify("payment_risk_check_failed")
    assert result["retryable"] is False