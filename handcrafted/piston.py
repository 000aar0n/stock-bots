"""piston.py - PISTON. XOM energy breakout craftsman.

Entry on a new 20 day high with RSI over 50 (the piston fires
only mid stroke, not from rest). Exit on the -8% rule only:
energy breakouts are slow and PISTON refuses to be shaken out by
one average.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/piston.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "PISTON", "XOM"


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
    hi20 = max(closes[-21:-1])
    setup = last > hi20 and d["rsi14"] is not None and d["rsi14"] > 50
    print(f"PISTON - XOM breakout  last ${last:.2f}  prior 20d high ${hi20:.2f}  "
          f"RSI {d['rsi14']} (need over 50)")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT XOM @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "PISTON exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY XOM @ ${last:.2f} (20d high mid stroke)")
        if log: log(BOT, SYM, "buy", last, "PISTON: 20d high with RSI over 50")
    else:
        print("  piston at rest, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
