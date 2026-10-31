"""rubber.py - RUBBER. NVDA snapback craftsman (mean reversion).

RUBBER waits for NVDA to get stretched DOWN fast: down 5% or more
across three sessions, RSI under 38, and still above the SMA200
(a stretched band, not a cut one). Entry on that close. Exit is
mechanical and greedy: +5% (band snapped back) or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/rubber.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "RUBBER", "NVDA"


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
    chg3 = scanner.pct(closes[-1], closes[-4])
    setup = (chg3 <= -5 and d["rsi14"] is not None and d["rsi14"] < 38
             and d["sma200"] and last > d["sma200"])
    print(f"RUBBER - NVDA snapback  last ${last:.2f}  3d {chg3:+.2f}%  "
          f"RSI {d['rsi14']}  SMA200 ${d['sma200']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move >= 5.0 or move <= -8.0:
            why = "snapback complete at +5%" if move >= 5.0 else "-8% rule"
            print(f"  CALL: EXIT NVDA @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"RUBBER exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY NVDA @ ${last:.2f} (band stretched, not cut)")
        if log: log(BOT, SYM, "buy", last, "RUBBER: -5% in 3 sessions, RSI under 38")
    else:
        print("  band not stretched enough, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
