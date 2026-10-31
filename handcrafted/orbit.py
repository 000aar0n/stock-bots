"""orbit.py - ORBIT. META sideways orbit craftsman.

ORBIT only works when META is NOT trending: the SMA50 must be
flat (within 1% of where it sat ten sessions ago). In that
orbit, buy closes near the SMA20 with RSI under 48 (the low
side of the loop), exit at RSI over 62. If META starts trending,
ORBIT stands down and leaves the name to SPRING and TRAVERSE.

Run: python3 handcrafted/orbit.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "ORBIT", "META"


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
    sma50_then = ta.sma(closes[:-10], 50)
    flat = (d["sma50"] and sma50_then
            and abs(scanner.pct(d["sma50"], sma50_then)) < 1.0)
    near20 = d["sma20"] and abs(scanner.pct(last, d["sma20"])) <= 1.0
    setup = bool(flat and near20 and d["rsi14"] is not None and d["rsi14"] < 48)
    print(f"ORBIT - META sideways loop  last ${last:.2f}  SMA50 flat: {bool(flat)}  "
          f"near SMA20: {bool(near20)}  RSI {d['rsi14']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["rsi14"] and d["rsi14"] > 62) or move <= -8.0:
            why = f"RSI {d['rsi14']} at the top of the loop" if d["rsi14"] and d["rsi14"] > 62 else "-8% rule"
            print(f"  CALL: EXIT META @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"ORBIT exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY META @ ${last:.2f} (low side of a flat orbit)")
        if log: log(BOT, SYM, "buy", last, "ORBIT: flat SMA50, near SMA20, RSI under 48")
    else:
        print("  trending or mid loop, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
