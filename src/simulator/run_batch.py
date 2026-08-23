import csv, os, sys, random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from agents import orchestrator, idempotency
from simulator.baseline import NAIVE_RETRY_SUCCESS

NAIVE_DUNNING_FALLBACK = 0.15


def run(csv_path="data/simulated_transactions.csv", seed=21):
    for path in (idempotency.DB_PATH, orchestrator.TRACE_DB):
        if os.path.exists(path):
            os.remove(path)
    random.seed(seed)  # keeps outcomes.simulate_outcome's internal rng reproducible too

    rng = random.Random(seed)
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: float(r["event_time"]))

    total_amount = naive_recovered = copilot_recovered = 0.0

    for row in rows:
        amount = float(row["amount"])
        total_amount += amount

        p_naive = NAIVE_RETRY_SUCCESS.get(row["decline_code"], NAIVE_DUNNING_FALLBACK)
        if rng.random() < p_naive:
            naive_recovered += amount

        result = orchestrator.run_recovery_loop({
            "txn_id": row["txn_id"], "decline_code": row["decline_code"],
            "issuer": row.get("issuer", "unknown"), "event_time": float(row["event_time"]),
            "amount": amount, "has_secondary_method": rng.random() < 0.4,
        }, use_llm=False)
        copilot_recovered += result["recovered_amount"]

    return {
        "total_amount": round(total_amount, 2),
        "naive_recovered": round(naive_recovered, 2),
        "copilot_recovered": round(copilot_recovered, 2),
        "naive_still_at_risk": round(total_amount - naive_recovered, 2),
        "copilot_still_at_risk": round(total_amount - copilot_recovered, 2),
    }


if __name__ == "__main__":
    r = run()
    print(f"total revenue at risk:      Rs {r['total_amount']:,.0f}")
    print(f"naive retry recovered:      Rs {r['naive_recovered']:,.0f}  (still at risk Rs {r['naive_still_at_risk']:,.0f})")
    print(f"recovery copilot recovered: Rs {r['copilot_recovered']:,.0f}  (still at risk Rs {r['copilot_still_at_risk']:,.0f})")