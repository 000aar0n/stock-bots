"""tic.py - TIC. PLTR intraday breakout craftsman (5 minute).

The smallest unit in the city: a tic. Entry when a 5 minute
close breaks over the high of the prior 12 bars (one hour of
range) on PLTR. Exit on a tight -3% intraday stop (the tic was
noise) or a fall back under that hour's low. No overnight, ever.

Run: python3 handcrafted/tic.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "TIC", "PLTR"


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
    bars = scanner.fetch_intraday(SYM)
    if len(bars) < 14:
        print("TIC - not enough 5 minute bars, no read")
        return 0
    window = bars[-13:-1]
    hi = max(b["high"] for b in window)
    lo = min(b["low"] for b in window)
    last = bars[-1]["close"]
    print(f"TIC - PLTR 5m breakout  last ${last:.2f}  prior hour range "
          f"${lo:.2f} to ${hi:.2f}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -3.0 or last < lo:
            why = "-3% intraday stop" if move <= -3 else "back under the hour low"
            print(f"  CALL: EXIT PLTR @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"TIC exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif last > hi:
        print(f"  CALL: BUY PLTR @ ${last:.2f} (tic over the hour high)")
        if log: log(BOT, SYM, "buy", last, "TIC: 5m break of the prior 12 bar high")
    else:
        print("  inside the hour range, no tic")
    return 0


if __name__ == "__main__":
    sys.exit(main())
