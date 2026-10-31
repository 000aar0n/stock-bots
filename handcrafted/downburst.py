"""downburst.py - DOWNBURST. RDDT breakdown short craftsman.

Not a fade: a breakdown. DOWNBURST shorts RDDT when it closes
UNDER its prior 20 day low on a red day (support gone, air
below). Exit on a close back over the SMA20 (structure repaired)
or at +6% against. RDDT already taught this city what post gap
breakdowns do; DOWNBURST trades the second leg, not the first.

Run: python3 handcrafted/downburst.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "DOWNBURST", "RDDT"
NEWS_FLAG = "news unverified: DOWNBURST cannot check for fresh fundamental news"


def my_short():
    from leaderboard import load_calls
    op = None
    for c in load_calls():
        if c["bot"] == BOT and c["ticker"] == SYM:
            if c["side"] == "short": op = op or c
            elif c["side"] == "exit": op = None
    return op


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    candles = scanner.fetch_daily(SYM)
    closes = [c["close"] for c in candles]
    last, d = closes[-1], ta.analyze(candles)
    lo20 = min(closes[-21:-1])
    red = last < candles[-1]["open"]
    setup = last < lo20 and red
    print(f"DOWNBURST - RDDT breakdown  last ${last:.2f}  prior 20d low "
          f"${lo20:.2f}  red day: {red}")
    op = my_short()
    if op:
        against = scanner.pct(last, op["entry_price"])
        repaired = d["sma20"] and last > d["sma20"]
        if against >= 6.0 or repaired:
            why = f"short {against:+.2f}% underwater" if against >= 6 else "back over SMA20, structure repaired"
            print(f"  CALL: EXIT short RDDT @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"DOWNBURST cover: {why}")
        else:
            print(f"  holding open short @ ${op['entry_price']:.2f}, now {against:+.2f}%")
    elif setup:
        print(f"  CALL: SHORT RDDT @ ${last:.2f} (support gone)  [{NEWS_FLAG}]")
        if log: log(BOT, SYM, "short", last, f"DOWNBURST breakdown short; {NEWS_FLAG}")
    else:
        print("  support holding, no short")
    return 0


if __name__ == "__main__":
    sys.exit(main())
