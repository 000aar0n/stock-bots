"""foam.py - FOAM. High beta bench froth reversal craftsman.

Only RKLB, IONQ, SNDK. Entry: relative volume over 3 (froth)
with a hammer AFTER a red day: the speculative crowd washed out
intraday and buyers stepped into the foam. Exit at +8% (froth
pays fast or not at all) or a tighter -6% rule.

Run: python3 handcrafted/foam.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "FOAM"
NAMES = ["RKLB", "IONQ", "SNDK"]


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
    print("FOAM - froth reversal on RKLB, IONQ, SNDK")
    hits = 0
    for sym in NAMES:
        candles = scanner.fetch_daily(sym)
        closes = [c["close"] for c in candles]
        last, d = closes[-1], ta.analyze(candles)
        red_before = closes[-2] < closes[-3]
        setup = (d["rel_volume"] or 0) > 3 and "hammer" in d["patterns"] and red_before
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            if move >= 8.0 or move <= -6.0:
                why = "froth paid at +8%" if move >= 8 else "-6% rule"
                print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
                if log: log(BOT, sym, "exit", last, f"FOAM exit: {why}")
            continue
        if setup:
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (rel vol {d['rel_volume']}, hammer in the foam)")
            if log: log(BOT, sym, "buy", last, f"FOAM: rel vol {d['rel_volume']} hammer after red")
    if not hits:
        print("  no foam today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
