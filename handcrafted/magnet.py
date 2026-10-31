"""magnet.py - MAGNET. GOOGL shock dip craftsman.

One violent day is the whole thesis: GOOGL drops over 4% in a
single session while the long trend (SMA200) is intact. MAGNET
buys the shock close. Exit on the first +3% bounce day (the snap
toward the magnet) or the -8% rule; it does not hold for a full
recovery.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/magnet.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "MAGNET", "GOOGL"


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
    chg1 = scanner.pct(closes[-1], closes[-2])
    setup = chg1 < -4 and d["sma200"] and last > d["sma200"]
    print(f"MAGNET - GOOGL shock dip  last ${last:.2f}  1d {chg1:+.2f}%  "
          f"SMA200 ${d['sma200']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if chg1 > 3 or move <= -8.0:
            why = f"bounce day at {chg1:+.2f}%" if chg1 > 3 else "-8% rule"
            print(f"  CALL: EXIT GOOGL @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"MAGNET exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY GOOGL @ ${last:.2f} (shock day, trend intact)")
        if log: log(BOT, SYM, "buy", last, "MAGNET: -4% shock day above SMA200")
    else:
        print("  no shock, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
