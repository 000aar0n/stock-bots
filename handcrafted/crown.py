"""crown.py - CROWN. WMT coronation breakout craftsman.

The slowest breakout in the city: WMT must print a new 60 day
high to be crowned. Exit under the SMA50 (a long dethroning) or
the -8% rule. CROWN trades maybe a few times a year and does not
care.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/crown.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "CROWN", "WMT"


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
    hi60 = max(closes[-61:-1])
    setup = last > hi60
    print(f"CROWN - WMT coronation  last ${last:.2f}  prior 60d high ${hi60:.2f}  "
          f"SMA50 ${d['sma50']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["sma50"] and last < d["sma50"]) or move <= -8.0:
            why = "under SMA50, dethroned" if d["sma50"] and last < d["sma50"] else "-8% rule"
            print(f"  CALL: EXIT WMT @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"CROWN exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY WMT @ ${last:.2f} (new 60 day high)")
        if log: log(BOT, SYM, "buy", last, "CROWN: new 60d high")
    else:
        print("  no coronation, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
