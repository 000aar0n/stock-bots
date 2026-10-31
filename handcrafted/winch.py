"""winch.py - WINCH. HOOD tight range release craftsman.

HOOD bases in flat, dull ranges before its runs. WINCH requires
the dullest base: the ten session high to low range under 3% of
price (nothing happened for two weeks), then a close over the
ten day high (the winch starts pulling). Exit on the -8% rule.

Run: python3 handcrafted/winch.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "WINCH", "HOOD"


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
    base = candles[-11:-1]
    hi10 = max(c["high"] for c in base)
    lo10 = min(c["low"] for c in base)
    width_pct = scanner.pct(hi10, lo10)
    setup = width_pct < 3 and last > hi10
    print(f"WINCH - HOOD base release  last ${last:.2f}  ten session base "
          f"${lo10:.2f} to ${hi10:.2f} ({width_pct:.2f}% wide, need under 3%)")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT HOOD @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "WINCH exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY HOOD @ ${last:.2f} (the winch starts pulling)")
        if log: log(BOT, SYM, "buy", last, "WINCH: sub 3% base, break of the 10d high")
    else:
        print("  base too wide or no release, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
