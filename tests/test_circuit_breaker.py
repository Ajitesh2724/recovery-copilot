import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agents.circuit_breaker import record_technical_failure, is_tripped, reset


def test_stays_closed_below_threshold():
    reset("hdfc_test")
    for _ in range(3):
        record_technical_failure("hdfc_test")
    assert is_tripped("hdfc_test") is False


def test_trips_after_threshold():
    reset("icici_test")
    for _ in range(5):
        record_technical_failure("icici_test")
    assert is_tripped("icici_test") is True


def test_different_issuer_unaffected():
    reset("sbi_test")
    reset("axis_test")
    for _ in range(5):
        record_technical_failure("sbi_test")
    assert is_tripped("axis_test") is False