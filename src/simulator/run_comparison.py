import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from agents import orchestrator, idempotency
from simulator.baseline import NAIVE_RETRY_SUCCESS
import random

# reuse the same per-code "does the outcome eventually succeed" probabilities as the
# baseline, but only for actions our system actually attempts (retry/cascade) --
# actions like manual_review or compliant_dunning don't get an outcome roll here,
# since they're deliberately not attempting same-method recovery
RECOVERABLE_ACTIONS = {
    "retry_now", "retry_delayed", "retry_next_day", "retry_short_delay",
    "cascade_secondary", "send_upi_intent",
}

# recovery via compliant customer outreach (not a blind retry) -- conservative,
# grounded in the cited "basic dunning" range, not the full-stack range,
# since this models a single notification, not a whole campaign
DUNNING_RECOVERY_PROBABILITY = {
    "compliant_dunning": 0.15,
    "prompt_customer": 0.25,  # customer just needs to fix a typo'd VPA, higher odds
}

# # cascade and intent-switch get a boost over blind same-method retry --
# # this is the actual hypothesis being tested, documented as a simulator
# # assumption, not a measured number
# ACTION_SUCCESS_MULTIPLIER = {
#     "cascade_secondary": 2.5,
#     "send_upi_intent": 1.8,
# }

# fresh-attempt probabilities for actions that move to an unrelated method/channel --
# NOT derived from the original decline code's retry odds, since cascading to a
# different, working payment method has nothing to do with why the first one failed
FRESH_ATTEMPT_PROBABILITY = {
    "cascade_secondary": 0.75,   # different method entirely, roughly a normal payment attempt
    "send_upi_intent": 0.65,     # customer already engaged, but intent isn't guaranteed either
}

def _outcome_probability(row, action):
    if action in FRESH_ATTEMPT_PROBABILITY:
        return FRESH_ATTEMPT_PROBABILITY[action]
    return NAIVE_RETRY_SUCCESS.get(row["decline_code"], 0.1)

def run(csv_path="data/simulated_transactions.csv", seed=11):
    for path in (idempotency.DB_PATH, orchestrator.TRACE_DB):
        if os.path.exists(path):
            os.remove(path)

    rng = random.Random(seed)
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: float(r["event_time"]))  # replay in real chronological order

    total = 0
    recovered = 0
    for row in rows:
        total += 1
        result = orchestrator.process({
            "txn_id": row["txn_id"],
            "decline_code": row["decline_code"],
            "issuer": row.get("issuer", "unknown"),
            "event_time": float(row["event_time"]),
            "has_secondary_method": rng.random() < 0.4,
        })
        action = result["decision"]["action"]
        if action in RECOVERABLE_ACTIONS:
            if rng.random() < _outcome_probability(row, action):
                recovered += 1
        elif action in DUNNING_RECOVERY_PROBABILITY:
            if rng.random() < DUNNING_RECOVERY_PROBABILITY[action]:
                recovered += 1

    return {"total": total, "recovered": recovered, "recovery_rate": round(recovered / total, 4)}


if __name__ == "__main__":
    result = run()
    print(f"recovery copilot: {result['recovered']}/{result['total']} recovered "
          f"({result['recovery_rate'] * 100:.1f}%)")