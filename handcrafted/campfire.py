"""campfire.py - CAMPFIRE. WMT slow swing dip craftsman. SWING.

Declared swing: WMT pays slowly. Rule: any single down day over
2% while WMT holds over its SMA200 gets bought (small dips in a
giant's uptrend are gifts, not warnings). Exit at +4% or the -8%
rule. CAMPFIRE is CROWN's patient sibling: CROWN buys WMT's
highs, CAMPFIRE buys its dips.

Run: python3 handcrafted/campfire.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "CAMPFIRE", "WMT"


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
    chg1 = scanner.pct(closes[-1], closes[-2])
    setup = chg1 < -2 and d["sma200"] and last > d["sma200"]
    print(f"CAMPFIRE - WMT dip  last ${last:.2f}  1d {chg1:+.2f}%  "
          f"SMA200 ${d['sma200']} (hold_style: swing)")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move >= 4.0 or move <= -8.0:
            why = "banked at +4%" if move >= 4 else "-8% rule"
            print(f"  CALL: EXIT WMT @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"CAMPFIRE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY WMT @ ${last:.2f} (a gift dip in a giant)")
        if log: log(BOT, SYM, "buy", last, "CAMPFIRE: -2% day above SMA200")
    else:
        print("  no gift today, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
