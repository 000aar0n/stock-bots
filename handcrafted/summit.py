"""summit.py - SUMMIT. LLY slow breakout craftsman.

LLY grinds for months, so SUMMIT demands a higher summit: a new
50 day high, nothing less. Exit under the SMA20 (the climb is
over for now) or the -8% rule. No volume condition: LLY breakouts
whisper.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/summit.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "SUMMIT", "LLY"


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
    hi50 = max(closes[-51:-1])
    setup = last > hi50
    print(f"SUMMIT - LLY breakout  last ${last:.2f}  prior 50d high ${hi50:.2f}  "
          f"SMA20 ${d['sma20']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["sma20"] and last < d["sma20"]) or move <= -8.0:
            why = "under SMA20, climb over" if d["sma20"] and last < d["sma20"] else "-8% rule"
            print(f"  CALL: EXIT LLY @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"SUMMIT exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY LLY @ ${last:.2f} (new 50 day summit)")
        if log: log(BOT, SYM, "buy", last, "SUMMIT: new 50d high")
    else:
        print("  no summit, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
