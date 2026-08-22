import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from agents import idempotency


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(idempotency.DB_PATH):
        os.remove(idempotency.DB_PATH)
    yield
    if os.path.exists(idempotency.DB_PATH):
        os.remove(idempotency.DB_PATH)


def test_first_attempt_runs():
    calls = []
    ran, result = idempotency.attempt_once("txn_test_1", "retry_now", lambda: calls.append(1))
    assert ran is True
    assert len(calls) == 1


def test_duplicate_attempt_blocked():
    calls = []
    idempotency.attempt_once("txn_test_2", "retry_now", lambda: calls.append(1))
    ran_again, result = idempotency.attempt_once("txn_test_2", "retry_now", lambda: calls.append(1))
    assert ran_again is False
    assert len(calls) == 1


def test_different_decision_is_a_different_attempt():
    ran, _ = idempotency.attempt_once("txn_test_3", "cascade_secondary", lambda: True)
    assert ran is True