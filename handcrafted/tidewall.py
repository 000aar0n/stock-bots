"""tidewall.py - TIDEWALL. CVX wide range craftsman.

CVX's range is wider and slower than KO's, so TIDEWALL uses the
60 day walls: buy within 3% of the 60 day low with RSI under 42,
exit within 3% of the 60 day high or at RSI over 68, or the -8%
rule. Months per round trip is fine.

Run: python3 handcrafted/tidewall.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "TIDEWALL", "CVX"


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
    lo60, hi60 = min(closes[-60:]), max(closes[-60:])
    at_floor = scanner.pct(last, lo60) <= 3
    at_top = scanner.pct(hi60, last) <= 3
    setup = at_floor and d["rsi14"] is not None and d["rsi14"] < 42
    print(f"TIDEWALL - CVX wide range  last ${last:.2f}  60d walls ${lo60:.2f} "
          f"to ${hi60:.2f}  RSI {d['rsi14']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if at_top or (d["rsi14"] and d["rsi14"] > 68) or move <= -8.0:
            why = "top wall" if at_top else ("RSI over 68" if d["rsi14"] and d["rsi14"] > 68 else "-8% rule")
            print(f"  CALL: EXIT CVX @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"TIDEWALL exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY CVX @ ${last:.2f} (at the low tidewall)")
        if log: log(BOT, SYM, "buy", last, "TIDEWALL: within 3% of 60d low, RSI under 42")
    else:
        print("  between the walls, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
