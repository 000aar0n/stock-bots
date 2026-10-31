"""gyre.py - GYRE. PEP range swirl craftsman.

PEP swirls slower than KO, so GYRE demands the indecision print:
a doji within 1.5% of the 20 day low (sellers and buyers both
stopped at the floor). Exit on a close over the SMA20 (the swirl
lifted) or at +5%, or the -8% rule.

Run: python3 handcrafted/gyre.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "GYRE", "PEP"


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
    lo20 = min(closes[-20:])
    setup = scanner.pct(last, lo20) <= 1.5 and "doji" in d["patterns"]
    print(f"GYRE - PEP swirl  last ${last:.2f}  distance over 20d low: "
          f"{scanner.pct(last, lo20):+.2f}%  patterns "
          f"{', '.join(d['patterns']) or 'none'}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        lifted = d["sma20"] and last > d["sma20"]
        if lifted or move >= 5.0 or move <= -8.0:
            why = "lifted over SMA20" if lifted else ("+5% banked" if move >= 5 else "-8% rule")
            print(f"  CALL: EXIT PEP @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"GYRE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY PEP @ ${last:.2f} (doji on the floor)")
        if log: log(BOT, SYM, "buy", last, "GYRE: doji within 1.5% of 20d low")
    else:
        print("  no floor doji, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
