import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from agents import strategy_agent, idempotency


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(idempotency.DB_PATH):
        os.remove(idempotency.DB_PATH)
    yield
    if os.path.exists(idempotency.DB_PATH):
        os.remove(idempotency.DB_PATH)


def test_fraud_goes_to_manual_review():
    txn = {"txn_id": "t1", "decline_code": "payment_risk_check_failed"}
    assert strategy_agent.decide(txn)["action"] == "manual_review"


def test_collect_expired_switches_to_intent():
    txn = {"txn_id": "t2", "decline_code": "payment_collect_request_expired"}
    assert strategy_agent.decide(txn)["action"] == "send_upi_intent"


def test_expired_card_cascades_when_secondary_exists():
    txn = {"txn_id": "t3", "decline_code": "card_expired", "has_secondary_method": True}
    assert strategy_agent.decide(txn)["action"] == "cascade_secondary"


def test_expired_card_falls_to_dunning_without_secondary():
    txn = {"txn_id": "t4", "decline_code": "card_expired", "has_secondary_method": False}
    assert strategy_agent.decide(txn)["action"] == "compliant_dunning"


def test_technical_failure_retries_until_breaker_trips():
    issuer = "test_bank_1"
    last_action = None
    for _ in range(6):
        txn = {"txn_id": f"tech_{_}", "decline_code": "bank_technical_error", "issuer": issuer}
        last_action = strategy_agent.decide(txn)["action"]
    assert last_action == "hold_circuit_open"


def test_apply_blocks_duplicate_execution():
    txn = {"txn_id": "t5", "decline_code": "insufficient_funds"}
    first = strategy_agent.apply(txn)
    second = strategy_agent.apply(txn)
    assert first["executed"] is True
    assert second["executed"] is False