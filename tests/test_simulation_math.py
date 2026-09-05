import pytest
from src.agents.predictor import assess_customer_risk
from src.simulator.run_batch import run, generate_txns

def test_customer_risk_math_invariants():
    """Verify that customer risk assessment adheres strictly to mathematical axioms."""
    test_customers = ["cust_00042", "cust_00651", "cust_00282", "cust_00999"]
    for cid in test_customers:
        res = assess_customer_risk(cid)
        total = res["total_transactions"]
        success = res["successful_payments"]
        failures = res["failed_payments"]

        # Invariant 1: Conservation of transactions
        assert success + failures == total, f"Failed for {cid}: {success} + {failures} != {total}"
        assert total > 0

        # Invariant 2: Accurate historical reliability percentage
        expected_reliability = round((success / total) * 100, 1)
        expected_failure_rate = round((failures / total) * 100, 1)
        assert res["payment_reliability_pct"] == expected_reliability
        assert res["failure_rate_pct"] == expected_failure_rate
        assert round(res["payment_reliability_pct"] + res["failure_rate_pct"], 1) == 100.0

        # Invariant 3: Explicit separation of risk score (0-100)
        assert 0 <= res["predicted_risk_score"] <= 100
        assert res["risk_level"] in ["LOW RISK", "MEDIUM RISK", "HIGH RISK"]


def test_simulation_batch_data_correctness():
    """Verify that batch simulation metrics, amounts, buckets, and costs are consistent."""
    result = run(n_transactions=500, generate_new=True)

    total_txns = result["total_transactions"]
    assert total_txns == 500

    # Bucket conservation
    buckets = result["buckets"]
    assert len(buckets) >= 5
    bucket_count_sum = sum(b["count"] for b in buckets)
    assert bucket_count_sum == total_txns, f"Sum of bucket counts ({bucket_count_sum}) != total ({total_txns})"

    bucket_amount_sum = sum(b["sum_amount"] for b in buckets)
    assert pytest.approx(bucket_amount_sum, rel=1e-2) == result["total_amount"]

    # Revenue and transaction recoveries
    assert result["copilot_recovered"] <= result["total_amount"]
    assert result["naive_recovered"] <= result["total_amount"]
    assert result["copilot_recovered_count"] <= total_txns
    assert result["naive_recovered_count"] <= total_txns

    # Cost model
    assert result["avg_recovery_cost_per_txn"] > 0
    assert result["total_recovery_cost"] > 0
    expected_avg = round(result["total_recovery_cost"] / total_txns, 2)
    assert abs(result["avg_recovery_cost_per_txn"] - expected_avg) <= 0.02

    # Funnel
    funnel = result["funnel"]
    assert funnel["total_failed"] == total_txns
    assert funnel["ai_analyzed"] == total_txns
    assert funnel["action_executed"] <= total_txns
    assert funnel["recovered"] == result["copilot_recovered_count"]


def test_simulation_generates_varying_cohorts():
    """Verify that multiple simulation runs generate varied, realistic results."""
    run1 = run(n_transactions=300, generate_new=True)
    run2 = run(n_transactions=300, generate_new=True)

    # Invariants hold on both
    assert run1["copilot_recovered"] > 0
    assert run2["copilot_recovered"] > 0

    # Values must not be hardcoded identical
    assert (run1["total_amount"] != run2["total_amount"]) or (run1["copilot_recovered"] != run2["copilot_recovered"])
