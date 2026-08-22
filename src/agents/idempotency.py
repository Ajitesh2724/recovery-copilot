import hashlib
import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "idempotency.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_keys (
            key TEXT PRIMARY KEY,
            created_at REAL
        )
    """)
    return conn


def make_key(txn_id, strategy_decision, window_seconds=300):
    # same txn + same decision within the same time window -> same key
    # so a crash-and-retry within that window collapses onto one attempt
    window = int(time.time() // window_seconds)
    raw = f"{txn_id}:{strategy_decision}:{window}"
    return hashlib.sha256(raw.encode()).hexdigest()


def already_processed(key):
    conn = _connect()
    row = conn.execute("SELECT 1 FROM processed_keys WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row is not None


def mark_processed(key):
    conn = _connect()
    conn.execute(
        "INSERT OR IGNORE INTO processed_keys (key, created_at) VALUES (?, ?)",
        (key, time.time()),
    )
    conn.commit()
    conn.close()


def attempt_once(txn_id, strategy_decision, action_fn):
    """
    Runs action_fn() only if this exact (txn, decision) hasn't already
    been processed in the current window. Returns (ran, result).
    """
    key = make_key(txn_id, strategy_decision)
    if already_processed(key):
        return False, None

    result = action_fn()
    mark_processed(key)
    return True, result