"""ledge.py - LEDGE. JPM SMA200 support bounce craftsman.

One ledge, stood on many times: JPM closing within 2% ABOVE its
SMA200 with a hammer printed on it. Entry there. Exit at the
SMA50 (the climb's first landing) or a tight -5% stop instead of
the usual -8%: if the ledge breaks, LEDGE does not argue.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/ledge.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "LEDGE", "JPM"


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
    dist = scanner.pct(last, d["sma200"]) if d["sma200"] else None
    setup = (dist is not None and 0 <= dist <= 2
             and "hammer" in d["patterns"])
    print(f"LEDGE - JPM SMA200 bounce  last ${last:.2f}  distance over SMA200: "
          f"{dist}%  patterns {', '.join(d['patterns']) or 'none'}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        at50 = d["sma50"] and last >= d["sma50"]
        if at50 or move <= -5.0:
            why = "reached the SMA50 landing" if at50 else "ledge broke: -5% stop"
            print(f"  CALL: EXIT JPM @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"LEDGE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY JPM @ ${last:.2f} (hammer on the SMA200 ledge)")
        if log: log(BOT, SYM, "buy", last, "LEDGE: hammer within 2% over SMA200")
    else:
        print("  not standing on the ledge, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
