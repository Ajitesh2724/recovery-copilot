import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from taxonomy.decline_codes import lookup, is_retryable


def test_known_code():
    assert lookup("card_expired")["category"] == "hard"


def test_unknown_code_returns_none():
    assert lookup("made_up_code") is None
    assert is_retryable("made_up_code") is None


def test_fraud_never_retryable():
    assert is_retryable("payment_risk_check_failed") is False


def test_expired_card_still_recoverable_via_cascade():
    assert is_retryable("card_expired") is True