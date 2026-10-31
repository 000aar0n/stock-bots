"""undercurrent.py - UNDERCURRENT. UNH capitulation contrarian.

Entry on exhaustion, not on the dip: three black crows (three
straight heavy red candles) driving RSI under 33, in a name
still above its SMA200. UNDERCURRENT buys the day the sellers
finish, not while they work. Exit at RSI over 52 or the -8%
rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/undercurrent.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "UNDERCURRENT", "UNH"


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
    crows = "three_black_crows" in d["patterns"]
    setup = (crows and d["rsi14"] is not None and d["rsi14"] < 33
             and d["sma200"] and last > d["sma200"])
    print(f"UNDERCURRENT - UNH capitulation  last ${last:.2f}  three black crows: "
          f"{crows}  RSI {d['rsi14']}  SMA200 ${d['sma200']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["rsi14"] and d["rsi14"] > 52) or move <= -8.0:
            why = f"RSI normalized at {d['rsi14']}" if d["rsi14"] and d["rsi14"] > 52 else "-8% rule"
            print(f"  CALL: EXIT UNH @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"UNDERCURRENT exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY UNH @ ${last:.2f} (sellers exhausted above SMA200)")
        if log: log(BOT, SYM, "buy", last, "UNDERCURRENT: three black crows, RSI under 33")
    else:
        print("  no capitulation print, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
