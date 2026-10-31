"""traverse.py - TRAVERSE. META 60 day range traverse craftsman. SWING.

Declared swing: crossing a 60 day range takes weeks. Rule:
META in the LOWER THIRD of its 60 day range, RSI under 50, and
still over the SMA200 (the range is a rest, not a collapse).
Entry there; exit in the UPPER THIRD of the range or the -8%
rule. ORBIT works META's tight sideways loops; TRAVERSE works
the whole mountain face.

Run: python3 handcrafted/traverse.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "TRAVERSE", "META"


def my_open():
    from leaderboard import load_calls
    op = None
    for c in load_calls():
        if c["bot"] == BOT and c["ticker"] == SYM:
            if c["side"] == "buy": op = op or c
            elif c["side"] == "exit": op = None
    return op


def position(candles):
    closes = [c["close"] for c in candles]
    lo, hi = min(closes[-60:]), max(closes[-60:])
    if hi == lo:
        return None, lo, hi
    return (closes[-1] - lo) / (hi - lo), lo, hi


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    candles = scanner.fetch_daily(SYM)
    closes = [c["close"] for c in candles]
    last, d = closes[-1], ta.analyze(candles)
    pos, lo, hi = position(candles)
    setup = bool(pos is not None and pos <= 1 / 3 and d["rsi14"] is not None
                 and d["rsi14"] < 50 and d["sma200"] and last > d["sma200"])
    print(f"TRAVERSE - META range face  last ${last:.2f}  range ${lo:.2f} to "
          f"${hi:.2f}, position {pos}  RSI {d['rsi14']} (hold_style: swing)")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (pos is not None and pos >= 2 / 3) or move <= -8.0:
            why = "upper third reached" if pos is not None and pos >= 2 / 3 else "-8% rule"
            print(f"  CALL: EXIT META @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"TRAVERSE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY META @ ${last:.2f} (lower third of the face)")
        if log: log(BOT, SYM, "buy", last, "TRAVERSE: lower third of the 60d range above SMA200")
    else:
        print("  mid face, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
