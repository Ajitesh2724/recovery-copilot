import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))

RBI_MIN_NOTICE_HOURS = 24

CHANNEL_BY_ACTION = {
    "send_upi_intent": "whatsapp",
    "compliant_dunning": "email",
    "prompt_customer": "sms",
}

MESSAGE_TEMPLATES = {
    "send_upi_intent": "Your payment didn't go through in time. Tap to complete it now: {link}",
    "compliant_dunning": "We were unable to process your payment. Please update your payment method to avoid service interruption.",
    "prompt_customer": "The UPI ID on file couldn't be verified. Please check and re-enter it.",
    "retry_delayed": "Heads up — we'll retry your payment on {retry_date}. No action needed if funds are available by then.",
}


def build_notice(decision, scheduled_charge_time=None):
    """
    Builds the outreach message for a strategy decision.
    If a recurring charge is scheduled, enforces the RBI 24-hour minimum
    notice window as a hard constraint -- not something the LLM can shorten.
    """
    action = decision["action"]

    if scheduled_charge_time:
        notice_deadline = scheduled_charge_time - timedelta(hours=RBI_MIN_NOTICE_HOURS)
        if datetime.now() > notice_deadline:
            return {
                "sendable": False,
                "reason": f"would violate RBI {RBI_MIN_NOTICE_HOURS}h advance-notice rule",
            }

    template = MESSAGE_TEMPLATES.get(action)
    if not template:
        return {"sendable": False, "reason": f"no outreach template for action '{action}'"}

    return {
        "sendable": True,
        "channel": CHANNEL_BY_ACTION.get(action, "email"),
        "message": template,
    }