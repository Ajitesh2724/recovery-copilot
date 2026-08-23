import csv
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from agents import orchestrator, idempotency
from simulator.baseline import NAIVE_RETRY_SUCCESS

# same recoverable/dunning action sets as run_comparison.py
RECOVERABLE_ACTIONS = {
    "retry_now", "retry_delayed", "retry_next_day", "retry_short_delay",
}
DUNNING_RECOVERY_PROBABILITY = {
    "compliant_dunning": 0.15,
    "prompt_customer": 0.25,
}

# the three scenarios: pessimistic, expected, optimistic
SCENARIOS = {
    "conservative": {"cascade_secondary": 0.55, "send_upi_intent": 0.45, "secondary_method_rate": 0.25},
    "expected":     {"cascade_secondary": 0.75, "send_upi_intent": 0.65, "secondary_method_rate": 0.40},
    "optimistic":   {"cascade_secondary": 0.85, "send_upi_intent": 0.75, "secondary_method_rate": 0.55},
}


def _outcome_probability(row, action, fresh_probs):
    if action in fresh_probs:
        return fresh_probs[action]
    return NAIVE_RETRY_SUCCESS.get(row["decline_code"], 0.1)


def run_scenario(name, params, csv_path="data/simulated_transactions.csv", seed=11):
    for path in (idempotency.DB_PATH, orchestrator.TRACE_DB):
        if os.path.exists(path):
            os.remove(path)

    rng = random.Random(seed)
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: float(r["event_time"]))

    fresh_probs = {"cascade_secondary": params["cascade_secondary"],
                   "send_upi_intent": params["send_upi_intent"]}

    total = 0
    recovered = 0
    for row in rows:
        total += 1
        result = orchestrator.process({
            "txn_id": row["txn_id"],
            "decline_code": row["decline_code"],
            "issuer": row.get("issuer", "unknown"),
            "event_time": float(row["event_time"]),
            "has_secondary_method": rng.random() < params["secondary_method_rate"],
        })
        action = result["decision"]["action"]
        if action in RECOVERABLE_ACTIONS:
            if rng.random() < _outcome_probability(row, action, fresh_probs):
                recovered += 1
        elif action in fresh_probs:
            if rng.random() < fresh_probs[action]:
                recovered += 1
        elif action in DUNNING_RECOVERY_PROBABILITY:
            if rng.random() < DUNNING_RECOVERY_PROBABILITY[action]:
                recovered += 1

    return round(recovered / total, 4)


if __name__ == "__main__":
    print("scenario       recovery_rate")
    for name, params in SCENARIOS.items():
        rate = run_scenario(name, params)
        print(f"{name:<14} {rate * 100:.1f}%")