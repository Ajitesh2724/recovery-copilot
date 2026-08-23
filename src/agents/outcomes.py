import random

# fresh-attempt probabilities for actions that move to a different method/channel entirely --
# not derived from the original decline code, since a cascade has nothing to do with why
# the first method failed
FRESH_ATTEMPT_PROBABILITY = {
    "cascade_secondary": 0.75,
    "send_upi_intent": 0.65,
}

# same-method retry probabilities, per decline code
RETRY_PROBABILITY = {
    "insufficient_funds": 0.25,
    "authentication_failed": 0.45,
    "bank_technical_error": 0.55,
    "gateway_technical_error": 0.55,
    "transaction_limit_exceeded": 0.40,
}

# recovery via compliant outreach, not a blind retry -- conservative, single-notification estimate
DUNNING_PROBABILITY = {
    "compliant_dunning": 0.15,
    "prompt_customer": 0.25,
}


def simulate_outcome(decline_code, action, rng=None):
    """True if this attempt would have recovered the payment. Simulated -- no real charge happens."""
    rng = rng or random
    if action in FRESH_ATTEMPT_PROBABILITY:
        p = FRESH_ATTEMPT_PROBABILITY[action]
    elif action in DUNNING_PROBABILITY:
        p = DUNNING_PROBABILITY[action]
    elif action.startswith("retry"):
        p = RETRY_PROBABILITY.get(decline_code, 0.1)
    else:
        p = 0.0  # manual_review / hold_circuit_open -> no immediate recovery
    return rng.random() < p