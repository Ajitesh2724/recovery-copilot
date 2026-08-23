import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agents.classifier_agent import classify


def test_known_code_uses_rule():
    result = classify("card_expired")
    assert result["source"] == "rule"
    assert result["category"] == "hard"


def test_unknown_code_has_valid_shape():
    result = classify("something_totally_new")
    assert result["category"] in ("soft", "hard", "technical", "unknown")
    assert isinstance(result["retryable"], bool)


def test_fraud_code_not_retryable():
    result = classify("payment_risk_check_failed")
    assert result["retryable"] is False