"""greenhouse.py - GREENHOUSE. Biotech trio bounce craftsman.

REGN, LLY, MRNA. Biotech gaps are binary news, so GREENHOUSE
never chases a gap; it buys the CALM bounce after: a name that
is turning_up (RSI/MACD bounce off a low) while holding over its
SMA200 (the greenhouse glass is intact). Exit at RSI over 65
(the plant outgrew the bounce) or the -8% rule.

Run: python3 handcrafted/greenhouse.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "GREENHOUSE"
TRIO = ["REGN", "LLY", "MRNA"]


def opens():
    from leaderboard import load_calls
    o = {}
    for c in load_calls():
        if c["bot"] != BOT:
            continue
        if c["side"] in ("buy", "short"):
            o.setdefault(c["ticker"], c)
        elif c["side"] == "exit":
            o.pop(c["ticker"], None)
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    op = opens()
    print("GREENHOUSE - biotech bounces over SMA200")
    hits = 0
    for sym in TRIO:
        candles = scanner.fetch_daily(sym)
        last = candles[-1]["close"]
        d = ta.analyze(candles)
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            if (d["rsi14"] and d["rsi14"] > 65) or move <= -8.0:
                why = f"RSI {d['rsi14']} over 65" if d["rsi14"] and d["rsi14"] > 65 else "-8% rule"
                print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
                if log: log(BOT, sym, "exit", last, f"GREENHOUSE exit: {why}")
            continue
        if d["turning_up"] and d["sma200"] and last > d["sma200"]:
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (calm bounce, glass intact)")
            if log: log(BOT, sym, "buy", last, "GREENHOUSE: turning_up over SMA200")
    if not hits:
        print("  nothing sprouting, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
