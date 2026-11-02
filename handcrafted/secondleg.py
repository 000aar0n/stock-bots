"""secondleg.py - SECONDLEG. Second leg down short, whole universe.

Declines travel in legs: a 10% or greater drop into a recent
low, a relief bounce of 3% or more that stalls, then the first
red close under the bounce's lows starts the second leg, which
is usually the faster one because the bounce buyers are now
trapped too. Short the start of the second leg, while price is
still above the low (the retest is the target, not the entry).
Cover at +4% against or at the recent low itself, the retest
complete. News unverified on every short; a human clears
shorts before anyone acts.

Run: python3 handcrafted/secondleg.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "SECONDLEG"
FLAG = "news unverified: SECONDLEG cannot check for fresh fundamental news"
DROP_MIN = -10.0
STOP_PCT = 4.0


def universe():
    out = []
    for names in scanner.UNIVERSE.values():
        for t in names:
            if t not in out:
                out.append(t)
    return out


def opens():
    from leaderboard import load_calls
    o = {}
    for c in load_calls():
        if c["bot"] != BOT:
            continue
        if c["side"] in ("buy", "short"):
            o.setdefault(c["ticker"], c)
        elif c["side"] == "exit":
            o.pop(c["ticker"], None)
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    op = opens()
    print("SECONDLEG - second leg down shorts over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(candles) < 30:
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        recent_low = min(closes[-8:])
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or last <= recent_low * 1.001:
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or low retested)")
                if log: log(BOT, sym, "exit", last, "SECONDLEG cover")
            continue
        drop = scanner.pct(recent_low, closes[-13])
        bounce_high = max(closes[-3:])
        bounce = scanner.pct(bounce_high, recent_low)
        stalling = last < min(closes[-3:-1]) if len(closes) >= 3 else False
        if (drop <= DROP_MIN and bounce >= 3.0 and stalling
                and last < candles[-1]["open"]
                and last >= recent_low * 1.005):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (dropped {drop:.1f}%, bounce of {bounce:.1f}% stalled, second leg starting)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"SECONDLEG second leg down short; {FLAG}")
    if not hits:
        print("  no second leg today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
