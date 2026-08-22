import sys, os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from agents.dunning_agent import build_notice


def test_normal_notice_is_sendable():
    result = build_notice({"action": "compliant_dunning"})
    assert result["sendable"] is True
    assert result["channel"] == "email"


def test_blocks_notice_inside_rbi_window():
    too_soon = datetime.now() + timedelta(hours=5)  # less than 24h away
    result = build_notice({"action": "compliant_dunning"}, scheduled_charge_time=too_soon)
    assert result["sendable"] is False
    assert "RBI" in result["reason"]


def test_allows_notice_outside_rbi_window():
    plenty_of_time = datetime.now() + timedelta(hours=48)
    result = build_notice({"action": "compliant_dunning"}, scheduled_charge_time=plenty_of_time)
    assert result["sendable"] is True


def test_unknown_action_has_no_template():
    result = build_notice({"action": "hold_circuit_open"})
    assert result["sendable"] is False