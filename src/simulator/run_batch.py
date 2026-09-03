import csv, os, sys, random
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from agents import orchestrator, idempotency,  circuit_breaker
from simulator.baseline import NAIVE_RETRY_SUCCESS

from taxonomy.decline_codes import lookup

ASSUMED_LLM_COST_PER_CALL = 0.05  # stated assumption, rough ₹ estimate for a short gemini-flash call
NAIVE_DUNNING_FALLBACK = 0.15


def run(csv_path="data/simulated_transactions.csv", seed=None):
    seed = seed if seed is not None else int(time.time())
    for path in (idempotency.DB_PATH, orchestrator.TRACE_DB):
        if os.path.exists(path):
            os.remove(path)

    circuit_breaker.reset_all()
    random.seed(seed)  # keeps outcomes.simulate_outcome's internal rng reproducible too

    rng = random.Random(seed)
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: float(r["event_time"]))

    total_amount = naive_recovered = copilot_recovered = 0.0
    unknown_code_count = 0

    for row in rows:
        amount = float(row["amount"])
        total_amount += amount
        if lookup(row["decline_code"]) is None:
            unknown_code_count += 1

        p_naive = NAIVE_RETRY_SUCCESS.get(row["decline_code"], NAIVE_DUNNING_FALLBACK)
        if rng.random() < p_naive:
            naive_recovered += amount

        result = orchestrator.run_recovery_loop({
            "txn_id": row["txn_id"], "decline_code": row["decline_code"],
            "issuer": row.get("issuer", "unknown"), "event_time": float(row["event_time"]),
            "amount": amount, "customer_id": row.get("customer_id"), "has_secondary_method": rng.random() < 0.4,
        }, use_llm=False, persist=False)
        copilot_recovered += result["recovered_amount"]

    avg_cost = round((unknown_code_count * ASSUMED_LLM_COST_PER_CALL) / len(rows), 4) if rows else 0
    return {
        "total_amount": round(total_amount, 2),
        "naive_recovered": round(naive_recovered, 2),
        "copilot_recovered": round(copilot_recovered, 2),
        "naive_still_at_risk": round(total_amount - naive_recovered, 2),
        "copilot_still_at_risk": round(total_amount - copilot_recovered, 2),
        "naive_rate_pct": round(naive_recovered / total_amount * 100, 1) if total_amount else 0,
        "copilot_rate_pct": round(copilot_recovered / total_amount * 100, 1) if total_amount else 0,
        "avg_cost_per_txn": avg_cost,
    }


if __name__ == "__main__":
    r = run()
    print(f"total revenue at risk:      Rs {r['total_amount']:,.0f}")
    print(f"naive retry recovered:      Rs {r['naive_recovered']:,.0f}  (still at risk Rs {r['naive_still_at_risk']:,.0f})")
    print(f"recovery copilot recovered: Rs {r['copilot_recovered']:,.0f}  (still at risk Rs {r['copilot_still_at_risk']:,.0f})")

def run_curve(csv_path="data/simulated_transactions.csv", seed=None, checkpoints=10):
    seed = seed if seed is not None else int(time.time())
    import random as _r
    rng = _r.Random(seed)
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: float(r["event_time"]))

    step = max(1, len(rows) // checkpoints)
    points, naive_cum, copilot_cum = [], 0.0, 0.0

    for path in (idempotency.DB_PATH, orchestrator.TRACE_DB):
        if os.path.exists(path):
            os.remove(path)

    circuit_breaker.reset_all()

    for i, row in enumerate(rows):
        amount = float(row["amount"])
        if rng.random() < NAIVE_RETRY_SUCCESS.get(row["decline_code"], NAIVE_DUNNING_FALLBACK):
            naive_cum += amount
        result = orchestrator.run_recovery_loop({
            "txn_id": row["txn_id"], "decline_code": row["decline_code"],
            "issuer": row.get("issuer", "unknown"), "event_time": float(row["event_time"]),
            "amount": amount, "has_secondary_method": rng.random() < 0.4,
        }, use_llm=False,persist=False)
        copilot_cum += result["recovered_amount"]

        if (i + 1) % step == 0 or i == len(rows) - 1:
            points.append({"n": i + 1, "naive": round(naive_cum), "copilot": round(copilot_cum)})

    return {"points": points}