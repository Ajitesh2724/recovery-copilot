import sqlite3
from agents.orchestrator import TRACE_DB

RISK_THRESHOLD = 0.5


def assess_customer_risk(customer_id):
    """
    Looks at this customer's own history in recovery_log and estimates
    the odds their NEXT scheduled debit fails for the same reason again.
    A simple frequency heuristic, not a trained model -- stated explicitly.
    """
    conn = sqlite3.connect(TRACE_DB)
    try:
        rows = conn.execute(
            "SELECT action, recovered FROM recovery_log WHERE customer_id = ?",
            (customer_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"customer_id": customer_id, "risk_score": 0.0, "sample_size": 0,
                "recommendation": "no history — insufficient data to predict"}

    failures = sum(1 for _, recovered in rows if not recovered)
    risk_score = round(min(failures / max(len(rows), 1), 1.0), 2)

    recommendation = (
        "high risk — proactively shift next debit date before it fails"
        if risk_score >= RISK_THRESHOLD
        else "low risk — no proactive action needed"
    )
    return {"customer_id": customer_id, "risk_score": risk_score,
            "sample_size": len(rows), "recommendation": recommendation}