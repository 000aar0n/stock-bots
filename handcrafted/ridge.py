"""ridge.py - RIDGE. AVGO staircase momentum craftsman.

Entry when AVGO climbs stairs, not elevators: 10 session gain
over +5%, at least three higher closes inside the last five
sessions, and price over the SMA20. Exit when price loses the
SMA20 (a stair broke), or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/ridge.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "RIDGE", "AVGO"


def my_open():
    from leaderboard import load_calls
    op = None
    for c in load_calls():
        if c["bot"] == BOT and c["ticker"] == SYM:
            if c["side"] == "buy": op = op or c
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
    chg10 = scanner.pct(closes[-1], closes[-11])
    stairs = sum(1 for i in range(-5, 0) if closes[i] > closes[i - 1])
    setup = chg10 > 5 and stairs >= 3 and d["sma20"] and last > d["sma20"]
    print(f"RIDGE - AVGO staircase  last ${last:.2f}  10d {chg10:+.2f}%  "
          f"higher closes in last 5: {stairs}  SMA20 ${d['sma20']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["sma20"] and last < d["sma20"]) or move <= -8.0:
            why = "lost the SMA20" if d["sma20"] and last < d["sma20"] else "-8% rule"
            print(f"  CALL: EXIT AVGO @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"RIDGE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY AVGO @ ${last:.2f} (staircase intact)")
        if log: log(BOT, SYM, "buy", last, "RIDGE: staircase momentum")
    else:
        print("  no staircase, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
