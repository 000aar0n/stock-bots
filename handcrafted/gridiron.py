"""gridiron.py - GRIDIRON. Defense trio breakout craftsman.

KTOS, LMT, RTX: three very different defense names, one rule.
GRIDIRON buys whichever prints a new 20 day high (defense
breakouts ride contract news and hold), one position at a time,
first come first served. Exit on the -8% rule.

Run: python3 handcrafted/gridiron.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "GRIDIRON"
TRIO = ["KTOS", "LMT", "RTX"]


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
    print("GRIDIRON - defense trio breakouts")
    busy = bool(op)
    for sym in TRIO:
        candles = scanner.fetch_daily(sym)
        closes = [c["close"] for c in candles]
        last = closes[-1]
        hi20 = max(closes[-21:-1])
        if sym in op:
            if scanner.pct(last, op[sym]["entry_price"]) <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (-8% rule)")
                if log: log(BOT, sym, "exit", last, "GRIDIRON exit: -8% rule")
                busy = False
            continue
        if last > hi20 and not busy:
            print(f"  CALL: BUY {sym} @ ${last:.2f} (defense breakout over ${hi20:.2f})")
            if log: log(BOT, sym, "buy", last, "GRIDIRON: 20d high in the defense trio")
            busy = True
    if not busy and not op:
        print("  no breakout on the line, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
