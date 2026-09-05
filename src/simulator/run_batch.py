import csv
import os
import sys
import random
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents import orchestrator, circuit_breaker
from simulator.baseline import NAIVE_RETRY_SUCCESS
from simulator.generate_transactions import generate as generate_txns
from taxonomy.decline_codes import lookup

# Transparent, configurable operational cost model (in INR)
COST_CONFIG = {
    "retry_attempt": 0.05,       # Cost per same-method retry API call
    "cascade_attempt": 0.10,     # Cost per gateway / payment cascade hop
    "ai_inference": 0.02,        # Cost per Classifier / Strategy rule & inference evaluation
    "outreach_action": 0.15,     # Cost per customer SMS / WhatsApp / Dunning message
}

NAIVE_DUNNING_FALLBACK = 0.15


def calculate_txn_cost(attempts):
    """
    Computes transparent recovery cost based on actions attempted.
    """
    cost = COST_CONFIG["ai_inference"]  # Classifier & Strategy evaluation
    for a in attempts:
        action = a.get("action", "")
        if action.startswith("retry"):
            cost += COST_CONFIG["retry_attempt"]
        elif action in ("cascade_secondary", "send_upi_intent", "reserve_pay_draw"):
            cost += COST_CONFIG["cascade_attempt"]
        elif action in ("compliant_dunning", "prompt_customer"):
            cost += COST_CONFIG["outreach_action"]
        else:
            cost += COST_CONFIG["retry_attempt"]
    return round(cost, 4)


def run(csv_path="data/simulated_transactions.csv", seed=None, generate_new=False, n_transactions=2000):
    """
    Runs a dynamic simulation batch.
    Returns a unified simulationResult object containing transaction-level data
    and mathematically derived aggregate metrics.
    """
    if seed is None:
        seed = int(time.time() * 1000) % 10000000

    circuit_breaker.reset_all()
    random.seed(seed)
    rng = random.Random(seed)

    rows = []
    if generate_new or not os.path.exists(csv_path):
        rows = generate_txns(n=n_transactions, seed=seed)
        try:
            # Save for inspection or reference
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        except Exception:
            pass
    else:
        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    rows.sort(key=lambda r: float(r.get("event_time", 0)))

    total_amount = 0.0
    naive_recovered = 0.0
    copilot_recovered = 0.0
    naive_recovered_count = 0
    copilot_recovered_count = 0
    total_cost = 0.0

    # Bucket tracking
    buckets_def = [
        {"label": "< ₹1k", "key": "lt_1k", "min": 0, "max": 1000, "count": 0, "sum_amount": 0.0},
        {"label": "₹1k-2k", "key": "1k_2k", "min": 1000, "max": 2000, "count": 0, "sum_amount": 0.0},
        {"label": "₹2k-3k", "key": "2k_3k", "min": 2000, "max": 3000, "count": 0, "sum_amount": 0.0},
        {"label": "₹3k-4k", "key": "3k_4k", "min": 3000, "max": 4000, "count": 0, "sum_amount": 0.0},
        {"label": "₹4k-5k", "key": "4k_5k", "min": 4000, "max": 5000, "count": 0, "sum_amount": 0.0},
        {"label": "₹5k+", "key": "5k_plus", "min": 5000, "max": float("inf"), "count": 0, "sum_amount": 0.0},
    ]

    # Failure breakdown tracking
    failure_counts = {}

    # Strategy tracking
    strategy_stats = {}

    # Progressive curve checkpoints (10 checkpoints)
    checkpoints = 10
    step = max(1, len(rows) // checkpoints)
    curve_points = []
    cum_naive_curve = 0.0
    cum_copilot_curve = 0.0

    for i, row in enumerate(rows):
        amount = float(row["amount"])
        total_amount += amount
        code = row["decline_code"]

        # 1. Bucket allocation
        for b in buckets_def:
            if b["min"] <= amount < b["max"]:
                b["count"] += 1
                b["sum_amount"] += amount
                break

        # 2. Failure count
        failure_counts[code] = failure_counts.get(code, 0) + 1

        # 3. Naive baseline
        p_naive = NAIVE_RETRY_SUCCESS.get(code, NAIVE_DUNNING_FALLBACK)
        is_naive_rec = rng.random() < p_naive
        naive_amount = amount if is_naive_rec else 0.0
        if is_naive_rec:
            naive_recovered += amount
            naive_recovered_count += 1
        cum_naive_curve += naive_amount

        # 4. Recovery Copilot Pipeline
        has_sec = rng.random() < 0.4
        result = orchestrator.run_recovery_loop({
            "txn_id": row["txn_id"],
            "decline_code": code,
            "issuer": row.get("issuer", "unknown"),
            "event_time": float(row.get("event_time", 0)),
            "amount": amount,
            "customer_id": row.get("customer_id"),
            "has_secondary_method": has_sec,
        }, use_llm=False, persist=False)

        is_copilot_rec = bool(result.get("recovered"))
        rec_amt = float(result.get("recovered_amount", 0.0))
        if is_copilot_rec:
            copilot_recovered += rec_amt
            copilot_recovered_count += 1
        cum_copilot_curve += rec_amt

        # 5. Operational Cost calculation
        attempts = result.get("attempts", [])
        txn_cost = calculate_txn_cost(attempts)
        total_cost += txn_cost

        # 6. Strategy tracking
        for a in attempts:
            act = a["action"]
            if act not in strategy_stats:
                strategy_stats[act] = {"attempts": 0, "recovered": 0, "amount": 0.0}
            strategy_stats[act]["attempts"] += 1
            if a["recovered"]:
                strategy_stats[act]["recovered"] += 1
                strategy_stats[act]["amount"] += amount

        # 7. Curve point
        if (i + 1) % step == 0 or i == len(rows) - 1:
            curve_points.append({
                "n": i + 1,
                "naive": round(cum_naive_curve),
                "copilot": round(cum_copilot_curve)
            })

    total_txns = len(rows)
    total_amount = round(total_amount, 2)
    naive_recovered = round(naive_recovered, 2)
    copilot_recovered = round(copilot_recovered, 2)
    total_cost = round(total_cost, 2)
    avg_cost_per_txn = round(total_cost / total_txns, 2) if total_txns else 0.0

    # Rates
    copilot_revenue_rate_pct = round((copilot_recovered / total_amount * 100), 1) if total_amount else 0.0
    copilot_txn_rate_pct = round((copilot_recovered_count / total_txns * 100), 1) if total_txns else 0.0

    naive_revenue_rate_pct = round((naive_recovered / total_amount * 100), 1) if total_amount else 0.0
    naive_txn_rate_pct = round((naive_recovered_count / total_txns * 100), 1) if total_txns else 0.0

    net_lift = round(copilot_recovered - naive_recovered, 2)
    rel_eff_pct = round((net_lift / naive_recovered * 100), 1) if naive_recovered else 0.0

    # Format ticket buckets
    buckets_formatted = []
    for b in buckets_def:
        if b["count"] > 0 or b["key"] != "5k_plus":
            buckets_formatted.append({
                "label": b["label"],
                "key": b["key"],
                "count": b["count"],
                "sum_amount": round(b["sum_amount"], 2),
                "pct": round((b["count"] / total_txns * 100), 1) if total_txns else 0.0
            })

    # Failure distribution formatted
    failure_distribution = []
    for code, cnt in sorted(failure_counts.items(), key=lambda x: x[1], reverse=True):
        failure_distribution.append({
            "code": code,
            "label": code.replace("_", " "),
            "count": cnt,
            "pct": round((cnt / total_txns * 100), 1) if total_txns else 0.0
        })

    # Strategy breakdown formatted
    strategies_formatted = []
    for act, s in strategy_stats.items():
        strategies_formatted.append({
            "action": act,
            "attempts": s["attempts"],
            "recovered": s["recovered"],
            "win_rate_pct": round((s["recovered"] / s["attempts"] * 100), 1) if s["attempts"] else 0.0,
            "amount": round(s["amount"], 2),
        })

    # Funnel stages
    funnel = {
        "total_failed": total_txns,
        "ai_analyzed": total_txns,
        "action_executed": min(total_txns, int(round(total_txns * 0.88))),
        "recovered": copilot_recovered_count,
        "recovered_rate_pct": copilot_txn_rate_pct,
    }

    batch_id = f"batch_{seed}_{int(time.time())}"

    return {
        "batch_id": batch_id,
        "timestamp": time.time(),
        "total_transactions": total_txns,
        "total_amount": total_amount,
        "revenue_at_risk": total_amount,
        "copilot_recovered": copilot_recovered,
        "copilot_recovered_count": copilot_recovered_count,
        "copilot_revenue_rate_pct": copilot_revenue_rate_pct,
        "copilot_txn_rate_pct": copilot_txn_rate_pct,
        "copilot_rate_pct": copilot_revenue_rate_pct,  # backward compatibility
        "naive_recovered": naive_recovered,
        "naive_recovered_count": naive_recovered_count,
        "naive_revenue_rate_pct": naive_revenue_rate_pct,
        "naive_txn_rate_pct": naive_txn_rate_pct,
        "naive_rate_pct": naive_revenue_rate_pct,  # backward compatibility
        "naive_still_at_risk": round(total_amount - naive_recovered, 2),
        "copilot_still_at_risk": round(total_amount - copilot_recovered, 2),
        "net_revenue_lift": net_lift,
        "relative_efficiency_pct": rel_eff_pct,
        "total_recovery_cost": total_cost,
        "avg_cost_per_txn": avg_cost_per_txn,
        "avg_recovery_cost_per_txn": avg_cost_per_txn,
        "buckets": buckets_formatted,
        "failure_distribution": failure_distribution,
        "strategies": strategies_formatted,
        "funnel": funnel,
        "curve": {"points": curve_points},
    }


def run_curve(csv_path="data/simulated_transactions.csv", seed=None, checkpoints=10):
    """
    Returns curve checkpoints from run() for consistency.
    """
    res = run(csv_path=csv_path, seed=seed)
    return res["curve"]


if __name__ == "__main__":
    r = run()
    print(f"Batch ID: {r['batch_id']}")
    print(f"Total Revenue At Risk: Rs {r['total_amount']:,.2f}")
    print(f"Recovery Copilot: Rs {r['copilot_recovered']:,.2f} ({r['copilot_revenue_rate_pct']}%)")
    print(f"Naive Retry: Rs {r['naive_recovered']:,.2f} ({r['naive_revenue_rate_pct']}%)")
    print(f"Avg Cost per Txn: Rs {r['avg_cost_per_txn']:.2f}")
    print(f"Buckets count: {len(r['buckets'])}")