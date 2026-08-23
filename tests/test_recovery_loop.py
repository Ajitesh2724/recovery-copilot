import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pytest
from agents import orchestrator, idempotency

@pytest.fixture(autouse=True)
def clean_dbs():
    for path in (idempotency.DB_PATH, orchestrator.TRACE_DB):
        if os.path.exists(path):
            os.remove(path)
    yield
    for path in (idempotency.DB_PATH, orchestrator.TRACE_DB):
        if os.path.exists(path):
            os.remove(path)

def test_loop_terminates_within_max_attempts():
    txn = {"txn_id": "loop_1", "decline_code": "card_expired", "amount": 500, "has_secondary_method": False}
    result = orchestrator.run_recovery_loop(txn, max_attempts=3)
    assert len(result["attempts"]) <= 3
    assert result["final_action"] in ("compliant_dunning", "manual_review")

def test_fraud_never_loops():
    txn = {"txn_id": "loop_2", "decline_code": "payment_risk_check_failed", "amount": 500}
    result = orchestrator.run_recovery_loop(txn)
    assert len(result["attempts"]) == 1