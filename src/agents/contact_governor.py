import sqlite3
import time
from agents.orchestrator import TRACE_DB, _connect

CONTACT_CAP = 3
WINDOW_SECONDS = 7 * 24 * 3600  # rolling 7 days


def can_contact(customer_id, now=None):
    """
    Caps total dunning touches per customer across ALL their failing
    transactions in a rolling window -- prevents multiple independent
    recovery flows from spamming the same person at once.
    """
    now = now or time.time()
    cutoff = now - WINDOW_SECONDS
    conn = _connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM decision_trace WHERE txn_id LIKE ? AND notice_sendable = 1 AND created_at >= ?",
            (f"{customer_id}%", cutoff),
        ).fetchone()[0]
    finally:
        conn.close()
    return count < CONTACT_CAP, count