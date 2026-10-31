"""breakwater.py - BREAKWATER. LNG expanding breakout craftsman.

Entry needs the wave to be GROWING: a new 20 day high, price
above SMA50, and ATR(14) larger than it was ten sessions ago
(volatility expanding into the break, not dying into it). Exit
on the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/breakwater.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "BREAKWATER", "LNG"


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
    atr_then = ta.atr(candles[:-10])
    expanding = d["atr14"] and atr_then and d["atr14"] > atr_then
    setup = bool(last > hi20 and d["sma50"] and last > d["sma50"] and expanding)
    print(f"BREAKWATER - LNG breakout  last ${last:.2f}  prior 20d high "
          f"${hi20:.2f}  ATR {atr_then} -> {d['atr14']} (expanding: {bool(expanding)})")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT LNG @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "BREAKWATER exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY LNG @ ${last:.2f} (breakout on an expanding wave)")
        if log: log(BOT, SYM, "buy", last, "BREAKWATER: 20d high, ATR expanding")
    else:
        print("  wave not growing, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
