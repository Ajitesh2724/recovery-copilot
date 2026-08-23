import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents import orchestrator
from agents import llm_client
from agents.orchestrator import run_recovery_loop
from simulator.run_batch import run as run_batch

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


@app.post("/process")
def process_transaction(txn: TransactionRequest):
    return orchestrator.process(txn.dict())


@app.post("/process_loop")
def process_loop(txn: TransactionRequest):
    return run_recovery_loop(txn.dict(), use_llm=True)


@app.get("/batch")
def batch_summary():
    return run_batch()

@app.get("/llm_status")
def llm_status():
    key_loaded = llm_client.available()
    test_result = llm_client.call("Reply with exactly: OK", max_tokens=60) if key_loaded else None
    return {"key_loaded": key_loaded, "test_call_result": test_result}

@app.get("/health")
def health():
    return {"status": "ok"}