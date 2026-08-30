import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from agents.classifier_agent import classify
from agents.circuit_breaker import is_tripped, record_technical_failure
from agents.idempotency import attempt_once
from datetime import datetime, timedelta

# soft-decline retry hints -> concrete action labels
TIMING_ACTIONS = {
    "delay_to_month_start": "retry_delayed",
    "immediate": "retry_now",
    "retry_next_day": "retry_next_day",
}

# what to try next if the current action doesn't recover the payment --
# every path ends in a stop-state, so the loop can never run forever
ESCALATION_PATH = {
    "retry_now": "cascade_secondary",
    "retry_delayed": "cascade_secondary",
    "retry_next_day": "cascade_secondary",
    "retry_short_delay": "cascade_secondary",
    "cascade_secondary": "compliant_dunning",
    "send_upi_intent": "compliant_dunning",
}


def next_retry_time(retry_hint, now=None):
    now = now or datetime.now()
    if retry_hint == "delay_to_month_start":
        target_month = now.month + 1 if now.day > 5 else now.month
        year = now.year + (1 if target_month > 12 else 0)
        target_month = 1 if target_month > 12 else target_month
        return datetime(year, target_month, 1, 0, 0).isoformat()
    if retry_hint == "retry_next_day":
        nxt = now + timedelta(days=1)
        return nxt.replace(hour=0, minute=5, second=0, microsecond=0).isoformat()
    return None  # immediate / no scheduling needed

def escalate(action, has_secondary_method):
    """Next action to try, or None if this action is already a stop-state."""
    nxt = ESCALATION_PATH.get(action)
    if nxt == "cascade_secondary" and not has_secondary_method:
        return "compliant_dunning"
    return nxt

def decide(txn):
    classification = classify(txn["decline_code"])
    code = classification["code"]
    category = classification["category"]

    if code == "payment_risk_check_failed":
        result = {"action": "manual_review", "reason": "fraud flag, no auto-retry"}
    elif category == "unknown":
        result = {"action": "manual_review",
                   "reason": "unrecognized code, classifier couldn't confirm it's safe to retry"}
    elif code == "payment_collect_request_expired":
        result = {"action": "send_upi_intent", "channel": "whatsapp",
                   "reason": "collect missed, intent has higher completion"}
    elif category == "technical":
        issuer = txn.get("issuer", "unknown")
        now = txn.get("event_time")
        tripped = is_tripped(issuer, now=now)
        record_technical_failure(issuer, now=now)
        if tripped:
            result = {"action": "hold_circuit_open", "issuer": issuer,
                       "reason": "issuer failure burst detected, pausing retries"}
        else:
            result = {"action": "retry_short_delay", "reason": "transient bank/gateway issue"}
    elif category == "hard":
        if classification["retryable"] and txn.get("has_secondary_method"):
            result = {"action": "cascade_secondary", "reason": "primary method dead, secondary available"}
        elif code in ("invalid_vpa", "vpa_resolution_failed"):
            result = {"action": "prompt_customer", "reason": "customer needs to fix upi id"}
        else:
            result = {"action": "compliant_dunning", "reason": "no recovery path, notify customer"}
    else:
        action = TIMING_ACTIONS.get(classification["retry_hint"], "retry_now")
        scheduled = next_retry_time(classification["retry_hint"])
        result = {"action": action, "reason": f"soft decline, hint={classification['retry_hint']}"}
        if scheduled:
            result["scheduled_for"] = scheduled

    result["classifier_source"] = classification["source"]
    return result

def apply(txn, action_fn=None):
    """
    Runs the decision through the idempotency lock so the same txn+decision
    never fires twice within the lock window.
    """
    decision = decide(txn)
    action_fn = action_fn or (lambda: decision["action"])
    executed, _ = attempt_once(txn["txn_id"], decision["action"], action_fn)
    decision["executed"] = executed
    return decision