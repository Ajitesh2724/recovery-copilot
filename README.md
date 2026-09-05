# Recovery Copilot

An agentic system that decides what to do with a failed payment — retry it, cascade it to a different payment method, or hand it off to compliant customer outreach — instead of the industry-default fixed-schedule retry.

Built for the **Razorpay AI Buildathon**, AI Revenue Recovery track.

Deployed: https://recovery-copilot-99q5.onrender.com/ 

---

## The problem

Indian businesses on Razorpay see **8–15% payment failure rates** — elevated specifically because of RBI e-mandate compliance requirements. Most of that revenue isn't actually lost, it's mishandled:

- Naive, fixed-schedule retry recovers roughly **20–45%** of failed payments.
- Full-stack, decline-reason-aware recovery can reach **65–75%**.
- Expired cards alone cause **42%** of subscription payment failures — fully preventable with the right fallback.

That gap between "retry blindly" and "retry intelligently" is what Recovery Copilot is built to close.

## What it does

For every failed payment, Recovery Copilot answers three questions that fixed-schedule retry logic can't:

1. **Why did this actually fail?** — matched against a decline-code taxonomy built directly from Razorpay's own public API error documentation, with an LLM fallback for genuinely unrecognized codes.
2. **Should we retry, and how?** — a bounded, verify-and-escalate loop (max 3 attempts) that cascades to a secondary method or UPI Reserve Pay, switches a missed UPI Collect to a UPI Intent deep-link, or waits on a customer's own Promise-to-Pay commitment — instead of retrying the same dead method repeatedly.
3. **How do we tell the customer, safely?** — RBI-compliant notice timing, with a contact-governance cap so one customer never gets contacted by multiple independent recovery flows in the same week.

## Architecture

```
Failed Payment → Classifier Agent → Strategy Agent → Dunning Agent → Verify + Log
                  (rules → LLM        (cascade,        (RBI-compliant,   (bounded loop,
                   fallback)           circuit breaker,  personalized      max 3 attempts,
                                       Reserve Pay,       via LLM)         full audit trail)
                                       Promise-to-Pay)
```

**Safety mechanisms, not afterthoughts:**
- **Idempotency lock** — SHA-256 hash + SQLite constraint guarantees a crash mid-retry can never double-charge a customer.
- **Circuit breaker** — scoped per issuing bank, trips on a technical-failure burst and reroutes instead of hammering an outage.
- **Bounded stopping rules** — every non-recovered transaction ends with an explicit reason: hit the retry ceiling, or ran out of recovery paths entirely.
- **Contact governance** — caps total dunning touches per customer across all their failing transactions in a rolling week.

## Tech stack

- **Backend**: Python, FastAPI
- **LLM**: Google Gemini (used only for ambiguous decline-code classification and message personalization — most decisions are free, deterministic rule matches)
- **Persistence**: SQLite (idempotency store, recovery/decision audit log)
- **Frontend**: Vanilla HTML/CSS/JS dashboard — Live Decision trace, System Health (circuit breaker monitor), Analytics (batch simulation, sensitivity analysis), Recovery Cases (full audit trail, exportable as JSON)
- **Evaluation**: Custom synthetic transaction simulator + naive-baseline comparison + sensitivity analysis across conservative/expected/optimistic scenarios

## Running it locally

```powershell
git clone https://github.com/<your-username>/recovery-copilot.git
cd recovery-copilot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Add a `.env` file with a free [Gemini API key](https://aistudio.google.com/apikey) (optional — the system degrades gracefully to rule-based-only if omitted):
```
GEMINI_API_KEY=your_key_here
```

Generate the synthetic dataset and start the backend:
```powershell
python src\simulator\generate_transactions.py
uvicorn src.api:app --reload --port 8000
```

Open `http://127.0.0.1:8000` in a browser for the dashboard.

Run the test suite:
```powershell
pytest -v
```

## Results (synthetic evaluation)

On a 2,000-transaction synthetic backtest, grounded in the industry statistics above:

| Scenario | Recovery Rate |
|---|---|
| Naive fixed-schedule retry | ~25% |
| Recovery Copilot (conservative assumptions) | ~32% |
| Recovery Copilot (expected assumptions) | ~39–54% |
| Recovery Copilot (optimistic assumptions) | ~44% |

**Honesty note:** all figures above come from a synthetic dataset generated from published industry statistics and Razorpay's public error documentation — not real Razorpay transaction data. The sensitivity analysis exists specifically so the result isn't presented as a single, cherry-picked number.

## Known limitations

- Runs on synthetic data; no real transaction data was available or used.
- Scheduled retries (e.g., "retry near month-start") compute a real target time but don't yet execute against a live job scheduler.
- The customer risk predictor is a transparent, explainable heuristic over logged outcomes — not a trained model.
- No real Razorpay webhook ingestion; transactions are submitted directly via API for demo purposes.

## Roadmap

- Real webhook ingestion matching Razorpay's `payment.failed` payload shape
- An actual scheduler executing the delayed-retry times the system already computes
- A risk model trained on real recovered/failed outcomes over time

## Positioning

Razorpay's own Agent Studio includes a Subscription Recovery Agent. Recovery Copilot isn't built to replace it — it's a focused exploration of the decision-engine and safety layer underneath a system like that: decline-code taxonomy, circuit breaker, idempotency guarantee, and bounded stopping logic.

---
