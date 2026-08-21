# verified against razorpay.com/docs/errors/payments (cards + upi)
# category: soft = retryable same method, hard = not retryable same method, technical = transient

DECLINE_CODES = {
    "insufficient_funds": {
        "method": "card,upi",
        "category": "soft",
        "meaning": "account doesn't have enough balance",
        "retry_hint": "delay_to_month_start",
    },
    "payment_collect_request_expired": {
        "method": "upi",
        "category": "soft",
        "meaning": "customer didn't approve the collect request in time",
        "retry_hint": "switch_to_intent",
    },
    "authentication_failed": {
        "method": "card",
        "category": "soft",
        "meaning": "wrong otp / 3ds abandoned",
        "retry_hint": "immediate",
    },
    "card_expired": {
        "method": "card",
        "category": "hard",
        "meaning": "card expiry date passed",
        "retry_hint": "cascade_secondary",
    },
    "debit_instrument_blocked": {
        "method": "card",
        "category": "hard",
        "meaning": "card blocked by bank or customer",
        "retry_hint": "cascade_secondary",
    },
    "payment_risk_check_failed": {
        "method": "card",
        "category": "hard",
        "meaning": "bank flagged as fraud",
        "retry_hint": "manual_review_only",
    },
    "bank_technical_error": {
        "method": "card,upi",
        "category": "technical",
        "meaning": "issuing bank downtime",
        "retry_hint": "short_delay",
    },
    "gateway_technical_error": {
        "method": "card,upi",
        "category": "technical",
        "meaning": "gateway/partner bank downtime",
        "retry_hint": "short_delay",
    },
    "invalid_vpa": {
        "method": "upi",
        "category": "hard",
        "meaning": "upi id doesn't exist",
        "retry_hint": "prompt_customer",
    },
    "vpa_resolution_failed": {
        "method": "upi",
        "category": "hard",
        "meaning": "upi id couldn't be resolved",
        "retry_hint": "prompt_customer",
    },
    "transaction_limit_exceeded": {
        "method": "card",
        "category": "soft",
        "meaning": "daily card limit hit",
        "retry_hint": "retry_next_day",
    },
}


def lookup(code):
    return DECLINE_CODES.get(code)


def is_retryable(code):
    entry = lookup(code)
    if not entry:
        return None  # unknown code -> classifier should escalate to LLM
    return entry["category"] != "hard" or entry["retry_hint"] == "cascade_secondary"