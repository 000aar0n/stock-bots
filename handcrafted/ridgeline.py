"""ridgeline.py - RIDGELINE. Universe higher highs swing craftsman. SWING.

Declared swing: trend following needs days. Rule: a close over
the 20 day high where that high is itself higher than the high
of the prior 20 day window (a rising ridgeline, not a single
spike). Exit on a close under the 10 day low (the ridge broke)
or the -8% rule.

Run: python3 handcrafted/ridgeline.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "RIDGELINE"


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
    print("RIDGELINE - rising higher highs over the wide universe (hold_style: swing)")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        hi_now = max(closes[-21:-1])
        hi_prior = max(closes[-41:-21])
        lo10 = min(closes[-11:-1])
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            if last < lo10 or move <= -8.0:
                why = "under the 10d low, ridge broken" if last < lo10 else "-8% rule"
                print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
                if log: log(BOT, sym, "exit", last, f"RIDGELINE exit: {why}")
            continue
        if last > hi_now and hi_now > hi_prior:
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (ridgeline rising: "
                  f"{hi_prior:.2f} then {hi_now:.2f})")
            if log: log(BOT, sym, "buy", last, "RIDGELINE: higher highs, rising window")
    if not hits:
        print("  no rising ridges today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
