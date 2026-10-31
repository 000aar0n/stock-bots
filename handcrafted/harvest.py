"""harvest.py - HARVEST. NNE volume climax short craftsman.

NNE tops on frenzy days. HARVEST shorts the frenzy itself:
daily relative volume over 3, a shooting star, and a five
session run over +12% already behind it (the climax of a move,
not the start). Exit at +5% against or two green closes.

Run: python3 handcrafted/harvest.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "HARVEST", "NNE"
NEWS_FLAG = "news unverified: HARVEST cannot check for fresh fundamental news"


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
    frenzy = (d["rel_volume"] or 0) > 3 and "shooting_star" in d["patterns"]
    setup = frenzy and chg5 > 12
    print(f"HARVEST - NNE climax short  last ${last:.2f}  5d {chg5:+.2f}%  "
          f"rel vol {d['rel_volume']}  shooting star: {'shooting_star' in d['patterns']}")
    op = my_short()
    if op:
        against = scanner.pct(last, op["entry_price"])
        two_green = closes[-1] > closes[-2] > closes[-3]
        if against >= 5.0 or two_green:
            why = f"short {against:+.2f}% underwater" if against >= 5 else "two green closes"
            print(f"  CALL: EXIT short NNE @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"HARVEST cover: {why}")
        else:
            print(f"  holding open short @ ${op['entry_price']:.2f}, now {against:+.2f}%")
    elif setup:
        print(f"  CALL: SHORT NNE @ ${last:.2f} (climax day)  [{NEWS_FLAG}]")
        if log: log(BOT, SYM, "short", last, f"HARVEST climax short; {NEWS_FLAG}")
    else:
        print("  no climax, no short")
    return 0


if __name__ == "__main__":
    sys.exit(main())
