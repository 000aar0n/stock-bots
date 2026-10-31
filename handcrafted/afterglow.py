"""afterglow.py - AFTERGLOW. PLTR post print pullback craftsman.

PLTR prints move it violently (SIREN has it Mon Nov 2 after the
close). AFTERGLOW skips the violent day: it finds a 7%+ up day
inside the last five sessions, then buys the first pullback that
touches the EMA20 while price still holds over that day's gap
midpoint. Exit on the -8% rule. No big up day, no afterglow.

Run: python3 handcrafted/afterglow.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "AFTERGLOW", "PLTR"


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
    big = None
    for i in range(len(candles) - 5, len(candles) - 1):
        if scanner.pct(candles[i]["close"], candles[i - 1]["close"]) > 7:
            big = (candles[i], candles[i - 1]["close"])
    ema20 = d["ema20"]
    touched = ema20 and min(c["low"] for c in candles[-2:]) <= ema20 * 1.01
    setup = False
    mid = None
    if big:
        mid = (big[0]["open"] + big[1]) / 2
        setup = bool(touched and last > mid and ema20 and last >= ema20 * 0.99)
    print(f"AFTERGLOW - PLTR pullback  last ${last:.2f}  big up day in window: "
          f"{big is not None}  gap midpoint ${mid}  EMA20 touch: {bool(touched)}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT PLTR @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "AFTERGLOW exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY PLTR @ ${last:.2f} (pullback into the afterglow)")
        if log: log(BOT, SYM, "buy", last, "AFTERGLOW: EMA20 pullback over the gap midpoint")
    else:
        print("  no afterglow setup, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
