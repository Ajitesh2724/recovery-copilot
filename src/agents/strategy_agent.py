import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from agents.classifier_agent import classify
from agents.circuit_breaker import is_tripped, record_technical_failure
from agents.idempotency import attempt_once

# soft-decline retry hints -> concrete action labels
TIMING_ACTIONS = {
    "delay_to_month_start": "retry_delayed",
    "immediate": "retry_now",
    "retry_next_day": "retry_next_day",
}


def decide(txn):
    """
    Pure decision logic -- no side effects, no db writes.
    txn = {txn_id, customer_id, decline_code, issuer, has_secondary_method}
    """
    classification = classify(txn["decline_code"])
    code = classification["code"]
    category = classification["category"]

    # fraud is the one dead end -- never auto-retried, never overridden
    if code == "payment_risk_check_failed":
        return {"action": "manual_review", "reason": "fraud flag, no auto-retry"}

    # collect expired doesn't get re-collected -- push intent instead, it converts better
    if code == "payment_collect_request_expired":
        return {"action": "send_upi_intent", "channel": "whatsapp",
                "reason": "collect missed, intent has higher completion"}

    if category == "technical":
        issuer = txn.get("issuer", "unknown")
        tripped = is_tripped(issuer)
        record_technical_failure(issuer)
        if tripped:
            return {"action": "hold_circuit_open", "issuer": issuer,
                    "reason": "issuer failure burst detected, pausing retries"}
        return {"action": "retry_short_delay", "reason": "transient bank/gateway issue"}

    if category == "hard":
        if classification["retryable"] and txn.get("has_secondary_method"):
            return {"action": "cascade_secondary", "reason": "primary method dead, secondary available"}
        if code in ("invalid_vpa", "vpa_resolution_failed"):
            return {"action": "prompt_customer", "reason": "customer needs to fix upi id"}
        return {"action": "compliant_dunning", "reason": "no recovery path, notify customer"}

    # remaining soft-decline codes
    action = TIMING_ACTIONS.get(classification["retry_hint"], "retry_now")
    return {"action": action, "reason": f"soft decline, hint={classification['retry_hint']}"}


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