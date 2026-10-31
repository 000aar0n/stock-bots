"""vice.py - VICE. CVNA squeeze short craftsman.

CVNA squeezes harder than anything in the book, so VICE demands
a harder top than MIRROR: up over 20% in five sessions AND a
shooting star (the first rejection wick). Short entry there.
Exit at +5% against the short or two green closes, the standard
short discipline. Paper only; MIRROR's news warning applies here
too: no fresh news check exists, a human clears shorts first.

Run: python3 handcrafted/vice.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "VICE", "CVNA"
NEWS_FLAG = "news unverified: VICE cannot check for fresh fundamental news"


def my_short():
    from leaderboard import load_calls
    op = None
    for c in load_calls():
        if c["bot"] == BOT and c["ticker"] == SYM:
            if c["side"] == "short": op = op or c
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
    chg5 = scanner.pct(closes[-1], closes[-6])
    star = "shooting_star" in d["patterns"]
    setup = chg5 >= 20 and star
    print(f"VICE - CVNA squeeze short  last ${last:.2f}  5d {chg5:+.2f}% (need +20)  "
          f"shooting star: {star}")
    op = my_short()
    if op:
        against = scanner.pct(last, op["entry_price"])
        two_green = closes[-1] > closes[-2] > closes[-3]
        if against >= 5.0 or two_green:
            why = f"short is {against:+.2f}% underwater" if against >= 5 else "two green closes"
            print(f"  CALL: EXIT short CVNA @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"VICE cover: {why}")
        else:
            print(f"  holding open short @ ${op['entry_price']:.2f}, now {against:+.2f}%")
    elif setup:
        print(f"  CALL: SHORT CVNA @ ${last:.2f} (squeeze top)  [{NEWS_FLAG}]")
        if log: log(BOT, SYM, "short", last, f"VICE squeeze short; {NEWS_FLAG}")
    else:
        print("  squeeze not topped, no short")
    return 0


if __name__ == "__main__":
    sys.exit(main())
