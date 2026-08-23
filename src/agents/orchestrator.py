import os
import sys
import sqlite3
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from agents.strategy_agent import decide, escalate
from agents.dunning_agent import build_notice
from agents.idempotency import attempt_once
from agents import outcomes

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
    notice = build_notice(decision, txn.get("scheduled_charge_time"), use_llm=True)

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

MAX_ATTEMPTS = 3


def _connect_recovery():
    os.makedirs(os.path.dirname(TRACE_DB), exist_ok=True)
    conn = sqlite3.connect(TRACE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recovery_log (
            txn_id TEXT, attempt INTEGER, action TEXT,
            recovered INTEGER, amount REAL, created_at REAL
        )
    """)
    return conn


def _log_attempt(txn_id, attempt, action, recovered, amount):
    conn = _connect_recovery()
    try:
        conn.execute(
            "INSERT INTO recovery_log (txn_id, attempt, action, recovered, amount, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (txn_id, attempt, action, int(recovered), amount, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def run_recovery_loop(txn, max_attempts=MAX_ATTEMPTS, use_llm=False):
    """
    Detect (decline_code already known) -> Diagnose (classify, inside decide()) ->
    Decide -> Execute -> Verify -> loop or Stop. Bounded: never exceeds max_attempts,
    always ends in a stop-state (recovered, dunning sent, or manual review).
    """
    amount = float(txn.get("amount", 0))
    try:
        decision = decide(txn)
    except Exception as e:
        decision = {"action": "manual_review", "reason": f"decision failed, degrading safely: {e}"}

    history = []
    recovered = False
    classifier_source = decision.get("classifier_source", "n/a")

    for attempt in range(1, max_attempts + 1):
        action = decision["action"]
        key = f"{txn['txn_id']}_attempt{attempt}"
        executed, _ = attempt_once(key, action, lambda: action)
        outcome = outcomes.simulate_outcome(txn.get("decline_code", ""), action) if executed else False

        history.append({"attempt": attempt, "action": action, "reason": decision["reason"], "recovered": outcome})
        _log_attempt(txn["txn_id"], attempt, action, outcome, amount)

        if outcome:
            recovered = True
            break

        nxt_action = escalate(action, txn.get("has_secondary_method", False))
        if not nxt_action or attempt == max_attempts:
            break
        decision = {"action": nxt_action, "reason": f"attempt {attempt} ({action}) did not recover, escalating"}

    notice = build_notice(decision, txn.get("scheduled_charge_time"), use_llm=use_llm)

    return {
        "txn_id": txn["txn_id"], "attempts": history, "recovered": recovered,
        "amount": amount, "recovered_amount": amount if recovered else 0.0,
        "final_action": history[-1]["action"], "notice": notice,
        "classifier_source": classifier_source,
    }