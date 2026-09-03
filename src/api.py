import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents import orchestrator
from agents import llm_client
from agents.orchestrator import run_recovery_loop
from agents.circuit_breaker import status as breaker_status, record_technical_failure
from simulator.run_batch import run as run_batch
import csv, random as _random
from simulator.run_batch import run_curve
from agents.predictor import assess_customer_risk


TRACKED_ISSUERS = ["hdfc", "icici", "sbi", "axis", "kotak"]
app = FastAPI(title="Recovery Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TransactionRequest(BaseModel):
    txn_id: str
    decline_code: str
    issuer: str = "unknown"
    has_secondary_method: bool = False
    amount: float = 1500.0
    has_reserve_pay: bool = False
    promise_to_pay_date: str = None
    customer_id: str = None


@app.get("/predict")
def predict(customer_id: str):
    return assess_customer_risk(customer_id)

@app.post("/process")
def process_transaction(txn: TransactionRequest):
    return orchestrator.process(txn.dict())


@app.post("/process_loop")
def process_loop(txn: TransactionRequest):
    return run_recovery_loop(txn.dict(), use_llm=True)


@app.get("/batch")
def batch_summary():
    return run_batch()

@app.get("/curve")
def curve():
    return run_curve()

@app.get("/sample")
def sample_run(n: int = 8):
    n = min(max(n, 1), 25)  # keep it fast and free-tier-safe
    with open("data/simulated_transactions.csv") as f:
        rows = list(csv.DictReader(f))
    sample = _random.sample(rows, n)

    results = []
    for row in sample:
        r = run_recovery_loop({
            "txn_id": row["txn_id"], "decline_code": row["decline_code"],
            "issuer": row.get("issuer", "unknown"), "event_time": float(row["event_time"]),
            "amount": float(row["amount"]),
            "has_secondary_method": _random.random() < 0.4,
        }, use_llm=False)  # fast path, same reason batch stays non-LLM
        results.append({
            "txn_id": r["txn_id"], "decline_code": row["decline_code"],
            "final_action": r["final_action"], "recovered": r["recovered"],
            "amount": r["amount"], "attempts": r["attempts"],
        })
    total = sum(r["amount"] for r in results)
    recovered = sum(r["amount"] for r in results if r["recovered"])
    return {
        "results": results,
        "total_amount": round(total, 2),
        "recovered_amount": round(recovered, 2),
    }

@app.get("/llm_status")
def llm_status():
    key_loaded = llm_client.available()
    test_result = llm_client.call("Reply with exactly: OK", max_tokens=60) if key_loaded else None
    return {"key_loaded": key_loaded, "test_call_result": test_result}

@app.get("/trace")
def get_trace(limit: int = 50):
    conn = orchestrator._connect_recovery()
    rows = conn.execute(
        "SELECT * FROM recovery_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    columns = ["txn_id", "attempt", "action", "recovered", "amount", "created_at"]
    return {"trace": [dict(zip(columns, row)) for row in rows]}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/breakers")
def breakers():
    return {"issuers": [breaker_status(i) for i in TRACKED_ISSUERS]}


@app.post("/trip_breaker")
def trip_breaker(issuer: str = "hdfc"):
    for _ in range(5):
        record_technical_failure(issuer)
    return breaker_status(issuer)