import time
from collections import defaultdict

# in-memory failure log per issuer: {issuer: [timestamp, timestamp, ...]}
_failure_log = defaultdict(list)

TRIP_THRESHOLD = 5          # this many failures...
WINDOW_SECONDS = 300        # ...within this window...
COOLDOWN_SECONDS = 600      # ...trips the breaker for this long


def record_technical_failure(issuer, now=None):
    now = now or time.time()
    _failure_log[issuer].append(now)
    _prune_old(issuer, now)


def _prune_old(issuer, now):
    cutoff = now - WINDOW_SECONDS
    _failure_log[issuer] = [t for t in _failure_log[issuer] if t >= cutoff]


def is_tripped(issuer, now=None):
    now = now or time.time()
    _prune_old(issuer, now)

    recent_failures = _failure_log[issuer]
    if len(recent_failures) < TRIP_THRESHOLD:
        return False

    # tripped if the threshold was crossed within the last cooldown window
    most_recent = max(recent_failures)
    return (now - most_recent) < COOLDOWN_SECONDS


def reset(issuer):
    _failure_log[issuer] = []

def status(issuer, now=None):
    now = now or time.time()
    _prune_old(issuer, now)
    recent = _failure_log[issuer]
    tripped = is_tripped(issuer, now)
    remaining = 0
    if tripped and recent:
        remaining = max(0, COOLDOWN_SECONDS - (now - max(recent)))
    return {"issuer": issuer, "tripped": tripped, "recent_failures": len(recent), "cooldown_remaining": round(remaining)}

def reset_all():
    _failure_log.clear()