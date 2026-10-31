"""hammock.py - HAMMOCK. COST lazy dip craftsman (mean reversion).

COST barely hurries, so HAMMOCK barely hurries: entry only when
COST has sagged 3% or more across ten sessions while staying
above its SMA200 (a sag, not a fall). Exit at the prior 10 day
high (back to where the sag started) or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/hammock.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "HAMMOCK", "COST"


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
    chg10 = scanner.pct(closes[-1], closes[-11])
    high10 = max(closes[-11:-1])
    setup = chg10 <= -3 and d["sma200"] and last > d["sma200"]
    print(f"HAMMOCK - COST sag  last ${last:.2f}  10d {chg10:+.2f}%  "
          f"prior 10d high ${high10:.2f}  SMA200 ${d['sma200']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if last >= high10 or move <= -8.0:
            why = "back at the prior 10d high" if last >= high10 else "-8% rule"
            print(f"  CALL: EXIT COST @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"HAMMOCK exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY COST @ ${last:.2f} (a sag, not a fall)")
        if log: log(BOT, SYM, "buy", last, "HAMMOCK: -3% in 10 sessions above SMA200")
    else:
        print("  no sag, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
