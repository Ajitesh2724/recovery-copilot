import random
import csv

# probability a blind, same-method, fixed-schedule retry (retry 3x, no reasoning about why it failed)
# eventually succeeds -- these are simulator assumptions, tuned to roughly match the industry
# recovery-rate ranges cited in the report, not measured Razorpay figures
NAIVE_RETRY_SUCCESS = {
    "insufficient_funds": 0.25,
    "card_expired": 0.02,
    "payment_collect_request_expired": 0.30,
    "authentication_failed": 0.45,
    "bank_technical_error": 0.55,
    "gateway_technical_error": 0.55,
    "debit_instrument_blocked": 0.02,
    "payment_risk_check_failed": 0.01,
    "invalid_vpa": 0.05,
    "vpa_resolution_failed": 0.05,
    "transaction_limit_exceeded": 0.40,
}


def run(csv_path="data/simulated_transactions.csv", seed=7):
    rng = random.Random(seed)
    recovered = 0
    total = 0

    with open(csv_path) as f:
        for row in csv.DictReader(f):
            total += 1
            p = NAIVE_RETRY_SUCCESS.get(row["decline_code"], 0.1)
            if rng.random() < p:
                recovered += 1

    rate = recovered / total
    return {"total": total, "recovered": recovered, "recovery_rate": round(rate, 4)}


if __name__ == "__main__":
    result = run()
    print(f"naive baseline: {result['recovered']}/{result['total']} recovered "
          f"({result['recovery_rate'] * 100:.1f}%)")