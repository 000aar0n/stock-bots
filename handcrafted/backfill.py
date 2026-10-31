"""backfill.py - BACKFILL. Gap fill strength, whole universe.

A name that gaps DOWN over 4% at the open and then claws all the
way back to close at or over the prior close has shown the
strongest hand in the market that day: every seller got absorbed.
BACKFILL buys that close. Exit on the -8% rule.

Run: python3 handcrafted/backfill.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "BACKFILL"


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
    print("BACKFILL - gap down, fully recovered, over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        last, today, prev_close = closes[-1], candles[-1], closes[-2]
        gap = scanner.pct(today["open"], prev_close)
        if sym in op:
            if scanner.pct(last, op[sym]["entry_price"]) <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (-8% rule)")
                if log: log(BOT, sym, "exit", last, "BACKFILL exit: -8% rule")
            continue
        if gap < -4 and last >= prev_close:
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (gapped {gap:+.2f}% and "
                  f"backfilled the whole hole)")
            if log: log(BOT, sym, "buy", last, f"BACKFILL: {gap:+.1f}% gap fully recovered")
    if not hits:
        print("  no full recoveries today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
