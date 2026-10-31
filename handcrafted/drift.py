"""drift.py - DRIFT. MSFT uptrend pullback craftsman (momentum).

DRIFT never buys strength, it buys the pause inside strength:
SMA20 must be RISING (today's SMA20 over the SMA20 of five sessions
ago), price above SMA50, and the last close within 1.5% above the
EMA20 after touching it. Exit when price closes under SMA50, or
the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/drift.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "DRIFT", "MSFT"


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
    sma20_now, sma20_then = ta.sma(closes, 20), ta.sma(closes[:-5], 20)
    rising = sma20_now and sma20_then and sma20_now > sma20_then
    ema20 = d["ema20"]
    near = ema20 and last >= ema20 and scanner.pct(last, ema20) <= 1.5
    touched = min(c["low"] for c in candles[-3:]) <= (ema20 or 0) * 1.005
    setup = bool(rising and d["sma50"] and last > d["sma50"] and near and touched)
    print(f"DRIFT - MSFT pullback  last ${last:.2f}  SMA20 rising: {rising}  "
          f"EMA20 ${ema20}  near and touched: {bool(near and touched)}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["sma50"] and last < d["sma50"]) or move <= -8.0:
            why = "closed under SMA50, trend done" if last < (d["sma50"] or 0) else "-8% rule"
            print(f"  CALL: EXIT MSFT @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"DRIFT exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY MSFT @ ${last:.2f} (rising trend, EMA20 pullback)")
        if log: log(BOT, SYM, "buy", last, "DRIFT: uptrend pullback to EMA20")
    else:
        print("  no pullback setup, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
