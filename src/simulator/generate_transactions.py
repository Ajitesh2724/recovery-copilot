import random
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from taxonomy.decline_codes import DECLINE_CODES

# rough distribution based on published industry stats (insufficient funds ~30-35%,
# expired cards a big chunk of subscription failures, rest split across the smaller categories)
# these are simulator assumptions, not measured Razorpay data -- documented as such in the report
CODE_WEIGHTS = {
    "insufficient_funds": 32,
    "card_expired": 20,
    "payment_collect_request_expired": 12,
    "authentication_failed": 10,
    "bank_technical_error": 8,
    "gateway_technical_error": 5,
    "debit_instrument_blocked": 5,
    "payment_risk_check_failed": 3,
    "invalid_vpa": 2,
    "vpa_resolution_failed": 2,
    "transaction_limit_exceeded": 1,
}

METHOD_FOR_CODE = {code: DECLINE_CODES[code]["method"].split(",")[0] for code in CODE_WEIGHTS}


def generate(n=2000, seed=42):
    rng = random.Random(seed)
    codes = list(CODE_WEIGHTS.keys())
    weights = list(CODE_WEIGHTS.values())

    rows = []
    for i in range(n):
        code = rng.choices(codes, weights=weights, k=1)[0]
        rows.append({
            "txn_id": f"txn_{i:05d}",
            "customer_id": f"cust_{rng.randint(1, n // 3):05d}",  # some customers repeat, some don't
            "decline_code": code,
            "method": METHOD_FOR_CODE[code],
            "amount": round(rng.uniform(199, 4999), 2),
        })
    return rows


def save(rows, path="data/simulated_transactions.csv"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rows = generate()
    save(rows)
    print(f"generated {len(rows)} transactions -> data/simulated_transactions.csv")