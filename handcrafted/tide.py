"""tide.py - TIDE. AMZN band wash craftsman (mean reversion).

TIDE buys AMZN only when price washes a full 1.5 ATR BELOW its
SMA20 with RSI under 40 (a real washout, not a dip). The exit is
the tide coming back in: a close back above the SMA20, or the
-8% rule. No partial credit for almost washed out.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/tide.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "TIDE", "AMZN"


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
    wash_line = (d["sma20"] - 1.5 * d["atr14"]) if d["sma20"] and d["atr14"] else None
    setup = (wash_line and last < wash_line and d["rsi14"] is not None
             and d["rsi14"] < 40)
    print(f"TIDE - AMZN washout  last ${last:.2f}  wash line ${wash_line} "
          f"(SMA20 minus 1.5 ATR)  RSI {d['rsi14']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["sma20"] and last > d["sma20"]) or move <= -8.0:
            why = "tide back in: closed over SMA20" if d["sma20"] and last > d["sma20"] else "-8% rule"
            print(f"  CALL: EXIT AMZN @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"TIDE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY AMZN @ ${last:.2f} (full washout under the band)")
        if log: log(BOT, SYM, "buy", last, "TIDE: close under SMA20 minus 1.5 ATR, RSI under 40")
    else:
        print("  tide not far enough out, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
