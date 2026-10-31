"""comet.py - COMET. PLTR breakout craftsman with an RSI band.

Entry only on a new 20 day high WHILE RSI(14) sits between 55 and
75: strong but not yet vertical. Above 75 COMET refuses (that is
the top of the arc, not the start). Exit when RSI pushes over 80
(blowoff) or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/comet.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "COMET", "PLTR"


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
    new_high = last > max(closes[-21:-1])
    rsi = d["rsi14"]
    in_band = rsi is not None and 55 <= rsi <= 75
    print(f"COMET - PLTR banded breakout  last ${last:.2f}  new 20d high: "
          f"{new_high}  RSI {rsi} (band 55 to 75)")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (rsi is not None and rsi > 80) or move <= -8.0:
            why = f"RSI blowoff at {rsi}" if rsi and rsi > 80 else "-8% rule"
            print(f"  CALL: EXIT PLTR @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"COMET exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif new_high and in_band:
        print(f"  CALL: BUY PLTR @ ${last:.2f} (20d high inside the RSI band)")
        if log: log(BOT, SYM, "buy", last, "COMET: 20d high, RSI in the 55-75 band")
    else:
        miss = "no new 20d high" if not new_high else f"RSI {rsi} outside the band"
        print(f"  no trade: {miss}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
