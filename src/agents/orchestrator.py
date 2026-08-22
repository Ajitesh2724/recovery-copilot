import os
import sys
import sqlite3
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from agents.strategy_agent import decide
from agents.dunning_agent import build_notice
from agents.idempotency import attempt_once

TRACE_DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "trace_log.db")


def _connect():
    os.makedirs(os.path.dirname(TRACE_DB), exist_ok=True)
    conn = sqlite3.connect(TRACE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decision_trace (
            txn_id TEXT,
            decline_code TEXT,
            action TEXT,
            reason TEXT,
            executed INTEGER,
            notice_sendable INTEGER,
            notice_channel TEXT,
            created_at REAL
        )
    """)
    return conn


def _log(txn, decision, notice, executed):
    conn = _connect()
    conn.execute(
        """INSERT INTO decision_trace
           (txn_id, decline_code, action, reason, executed, notice_sendable, notice_channel, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            txn["txn_id"],
            txn["decline_code"],
            decision["action"],
            decision["reason"],
            int(executed),
            int(notice.get("sendable", False)),
            notice.get("channel"),
            time.time(),
        ),
    )
    conn.commit()
    conn.close()


def _log(txn, decision, notice, executed):
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO decision_trace
               (txn_id, decline_code, action, reason, executed, notice_sendable, notice_channel, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                txn["txn_id"],
                txn.get("decline_code", "unknown"),
                decision["action"],
                decision["reason"],
                int(executed),
                int(notice.get("sendable", False)),
                notice.get("channel"),
                time.time(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def process(txn):
    """
    Runs one failed transaction through the full pipeline.
    Falls back gracefully -- a missing field never crashes the pipeline,
    it just degrades to a safer default decision.
    """
    try:
        decision = decide(txn)
    except Exception as e:
        decision = {"action": "manual_review", "reason": f"decision failed, degrading safely: {e}"}

    executed, _ = attempt_once(txn["txn_id"], decision["action"], lambda: decision["action"])
    notice = build_notice(decision, txn.get("scheduled_charge_time"))

    _log(txn, decision, notice, executed)

    return {
        "txn_id": txn["txn_id"],
        "decision": decision,
        "notice": notice,
        "executed": executed,
    }

def recent_trace(limit=20):
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM decision_trace ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows