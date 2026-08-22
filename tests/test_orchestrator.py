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


def test_full_pipeline_runs_and_logs():
    txn = {"txn_id": "orch_1", "decline_code": "insufficient_funds"}
    result = orchestrator.process(txn)
    assert result["executed"] is True
    trace = orchestrator.recent_trace(limit=1)
    assert trace[0][0] == "orch_1"  # txn_id is first column


def test_degrades_gracefully_on_missing_field():
    txn = {"txn_id": "orch_2"}  # no decline_code at all
    result = orchestrator.process(txn)
    assert result["decision"]["action"] == "manual_review"


def test_duplicate_txn_not_executed_twice():
    txn = {"txn_id": "orch_3", "decline_code": "insufficient_funds"}
    orchestrator.process(txn)
    second = orchestrator.process(txn)
    assert second["executed"] is False