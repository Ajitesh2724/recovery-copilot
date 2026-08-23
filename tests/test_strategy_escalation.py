import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from agents.strategy_agent import escalate

def test_retry_escalates_to_cascade():
    assert escalate("retry_now", has_secondary_method=True) == "cascade_secondary"

def test_cascade_skipped_without_secondary_method():
    assert escalate("retry_now", has_secondary_method=False) == "compliant_dunning"

def test_terminal_action_has_no_escalation():
    assert escalate("compliant_dunning", has_secondary_method=True) is None