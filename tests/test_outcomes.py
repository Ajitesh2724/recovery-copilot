import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from agents.outcomes import simulate_outcome

def test_manual_review_never_recovers():
    assert simulate_outcome("payment_risk_check_failed", "manual_review", random.Random(1)) is False

def test_cascade_returns_bool():
    assert isinstance(simulate_outcome("card_expired", "cascade_secondary", random.Random(1)), bool)