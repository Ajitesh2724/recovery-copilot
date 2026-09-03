import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from agents import llm_client

RBI_MIN_NOTICE_HOURS = 24

CHANNEL_BY_ACTION = {
    "send_upi_intent": "whatsapp",
    "compliant_dunning": "email",
    "prompt_customer": "sms",
    "cascade_secondary": "sms",
}

MESSAGE_TEMPLATES = {
    "send_upi_intent": "Your payment didn't go through in time. Tap to complete it now: {link}",
    "compliant_dunning": "We were unable to process your payment. Please update your payment method to avoid service interruption.",
    "prompt_customer": "The UPI ID on file couldn't be verified. Please check and re-enter it.",
    "retry_delayed": "Heads up — we'll retry your payment on {retry_date}. No action needed if funds are available by then.",
    "cascade_secondary": "Your primary payment method didn't work, so we used your backup method instead. No action needed.",
}


def build_notice(decision, scheduled_charge_time=None, use_llm=False, customer_id=None):
    if customer_id:
        from agents.contact_governor import can_contact
        allowed, count = can_contact(customer_id)
        if not allowed:
            return {"sendable": False, "reason": f"contact cap reached ({count} touches this week) — governance hold, not a system failure"}

    action = decision["action"]

    if scheduled_charge_time:
        notice_deadline = scheduled_charge_time - timedelta(hours=RBI_MIN_NOTICE_HOURS)
        if datetime.now() > notice_deadline:
            return {"sendable": False, "reason": f"would violate RBI {RBI_MIN_NOTICE_HOURS}h advance-notice rule"}

    template = MESSAGE_TEMPLATES.get(action)
    if not template:
        return {"sendable": False, "reason": f"no outreach template for action '{action}'"}

    message, source = template, "template"
    if use_llm and llm_client.available() and "{" not in template:
        rewritten = _personalize(template)
        if rewritten:
            message, source = rewritten, "llm"

    return {"sendable": True, "channel": CHANNEL_BY_ACTION.get(action, "email"), "message": message, "source": source}


def _personalize(base_template):
    prompt = (
        "Rewrite the message below in a warm, concise, professional tone, under 30 words. "
        "Output rules: no markdown, no bullet points, no numbering, no explanations, "
        "no mention of 'options' or your reasoning -- output ONLY the final rewritten "
        f"sentence and nothing else.\n\nMessage: '{base_template}'"
    )
    result = llm_client.call(prompt, max_tokens=800)
    if not result:
        return None

    result = result.strip().strip('"')

    red_flags = ["constraint", "under 30 words", "option", "**", "reasoning",
                 "here is", "here's the", "rewritten message"]
    looks_broken = (
        len(result) < 15
        or result.startswith(":")
        or not result.rstrip().endswith((".", "!", "?"))  # catches mid-word truncation
        or any(flag in result.lower() for flag in red_flags)
    )
    if looks_broken:
        print("LLM dunning rewrite looked malformed or truncated, using template instead:", result)
        return None

    return result