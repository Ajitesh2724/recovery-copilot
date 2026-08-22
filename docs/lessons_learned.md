# Lessons Learned (for panel Q&A prep)

## Graceful degradation has to be enforced end-to-end, not just at the entry point

When building the Orchestrator, the decision step (`decide()`) correctly caught a missing
`decline_code` and fell back to `manual_review`. But the logging step (`_log()`) read
`txn["decline_code"]` directly again and crashed on the same missing field — the error
just moved one step further down the pipeline instead of being fixed.

Lesson: "graceful degradation" isn't a property of one function, it's a property every
downstream consumer of that data has to uphold. Fixed by using `txn.get("decline_code",
"unknown")` instead of direct key access, and wrapping the DB write in `try/finally` so
the connection always closes even if something else fails later — which also fixed a
second bug (a stuck SQLite file handle on Windows blocking test cleanup).

Good answer if asked "tell me about a bug you hit and how you found it."


## A backtest that compresses real time breaks time-windowed logic

The circuit breaker uses a rolling time window (5 failures within 5 minutes trips it,
600-second cooldown). That's correct for live traffic spread across a day — but the
simulator replayed 2000 transactions in milliseconds of real wall-clock time, so every
issuer's failures landed in the same instant. Each issuer's breaker tripped almost
immediately and, since the whole run finished before the cooldown could ever elapse,
stayed tripped for nearly the entire dataset — silently blocking recovery for ~13% of
transactions and dragging the overall number below the naive baseline.

Lesson: any time-windowed safety mechanism (circuit breakers, rate limits, cooldowns)
needs a simulator that replays events on a synthetic clock spread realistically over
time — not "as fast as the CPU can loop." Fixed by giving each simulated transaction
an event_time spread across a synthetic 30-day window, threading that timestamp through
the Strategy Agent instead of relying on wall-clock time, and sorting the replay by
event_time so the breaker observes events in true chronological order.

Good answer if asked "how did you validate the circuit breaker actually behaves
correctly, not just that it compiles?"


## Circuit breaker granularity matters — a wrong key can silently swallow recovery

When first wiring the Strategy Agent to simulated data, the circuit breaker was keyed
on payment method ("card" / "upi") instead of a real issuing bank. Since all card
transactions shared one identity, ~13% of transactions being technical failures was
enough to trip the breaker almost immediately and keep it tripped for nearly the whole
run — silently routing hundreds of recoverable transactions to `hold_circuit_open`
instead of retrying them, which pulled the overall recovery rate below the naive
baseline it was supposed to beat.

Lesson: a circuit breaker's protective value depends entirely on being scoped to the
actual unit of failure (one bank's outage), not a proxy for it (payment method).
Feeding it the wrong granularity doesn't just weaken the safeguard — it can make
the system provably worse than doing nothing. Fixed by generating distinct synthetic
issuing banks in the simulator and wiring the real issuer field through instead of
payment method.

Good answer if asked "did anything about your own results surprise you, and what did
you do about it?" — this is a stronger story than everything working first try.


## Comparing two systems fairly means scoring every code path the same way

After fixing the circuit-breaker bugs, Recovery Copilot beat the naive baseline, but
only narrowly. The cause wasn't a bug in either agent — it was an inconsistency in how
the comparison itself scored outcomes. The naive baseline rolled a recovery probability
for every transaction uniformly. Recovery Copilot's comparison script only rolled an
outcome for actions like retry/cascade, silently scoring compliant_dunning and
prompt_customer as zero — even though real dunning does recover a meaningful share of
cases, a fact already cited in the project's own problem statement.

Lesson: a "smarter" system doing the safer thing (not blindly retrying a hard decline)
can look artificially worse in a backtest if the comparison doesn't also credit the
recovery path it takes instead. Fixed by modeling a separate, more conservative
recovery probability for outreach-driven actions, grounded in the same published
dunning-recovery figures already cited in the report, rather than leaving them at zero
or inflating them to match the retry-path numbers.

Good answer if asked "how do you know your evaluation methodology itself is fair?"


## A multiplier on the wrong baseline understates your own system's advantage

Early cascade-success modeling scaled the original decline code's same-method retry
probability (e.g. card_expired: 0.02) by a multiplier, to represent cascading to a
different payment method. But a cascade to a working secondary method has nothing to
do with why the original method failed -- multiplying an already-near-zero number
by 2.5x still leaves it near zero, which meant the comparison was barely crediting
Recovery Copilot's actual biggest advantage (moving off a dead method entirely).

Lesson: when a decision routes to a fundamentally different recovery path, don't scale
the old path's probability -- model the new path's own realistic probability instead.
Fixed by giving cascade_secondary and send_upi_intent their own fresh-attempt
probabilities, independent of the original decline code's retry odds.

Good answer if asked "walk me through how you validated that your evaluation isn't
accidentally biased against your own system."