"""basin.py - BASIN. BAC range floor craftsman.

Banks slosh in ranges. BASIN buys BAC only at the basin floor:
close within 3% of the 60 day low, a green day, and RSI under 45
(cheap, not collapsing). Exit is a fixed +6% (the other side of
the slosh) or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/basin.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "BASIN", "BAC"


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
    low60 = min(closes[-60:])
    dist = scanner.pct(last, low60)
    green = last > closes[-2] and last > candles[-1]["open"]
    setup = dist <= 3 and green and d["rsi14"] is not None and d["rsi14"] < 45
    print(f"BASIN - BAC floor  last ${last:.2f}  distance over 60d low: "
          f"{dist:+.2f}%  green: {green}  RSI {d['rsi14']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move >= 6.0 or move <= -8.0:
            why = "other side of the slosh at +6%" if move >= 6.0 else "-8% rule"
            print(f"  CALL: EXIT BAC @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"BASIN exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY BAC @ ${last:.2f} (at the basin floor)")
        if log: log(BOT, SYM, "buy", last, "BASIN: within 3% of 60d low, green, RSI under 45")
    else:
        print("  not at the floor, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
