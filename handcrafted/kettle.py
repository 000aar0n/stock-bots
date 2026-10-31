"""kettle.py - KETTLE. AMD simmering squeeze craftsman.

COIL watches the range; KETTLE watches the volatility itself.
Entry setup: ATR(14) today is SMALLER than ATR ten sessions ago
(the kettle is simmering down) while price holds over the
SMA20, and the trigger is a close over the prior ten day high.
Exit on the -8% rule.

Run: python3 handcrafted/kettle.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "KETTLE", "AMD"


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
    atr_then = ta.atr(candles[:-10])
    simmering = d["atr14"] and atr_then and d["atr14"] < atr_then
    hi10 = max(closes[-11:-1])
    setup = bool(simmering and d["sma20"] and last > d["sma20"] and last > hi10)
    print(f"KETTLE - AMD simmer  last ${last:.2f}  ATR {atr_then} -> {d['atr14']} "
          f"(simmering: {bool(simmering)})  prior 10d high ${hi10:.2f}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT AMD @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "KETTLE exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY AMD @ ${last:.2f} (simmer broke upward)")
        if log: log(BOT, SYM, "buy", last, "KETTLE: shrinking ATR, break of the 10d high")
    else:
        print("  still simmering, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
