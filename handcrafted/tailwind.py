"""tailwind.py - TAILWIND. Energy relative strength vs XLE.

Only three names: XOM, CVX, LNG. TAILWIND ranks their five
session moves against the XLE sector fund and calls the leader
when it beats the fund by over 3 points (a real lead in a slow
sector). Exit when RS falls under zero or the -8% rule.

Run: python3 handcrafted/tailwind.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "TAILWIND"
NAMES = ["XOM", "CVX", "LNG"]


def chg5(candles):
    closes = [c["close"] for c in candles]
    return scanner.pct(closes[-1], closes[-6])


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
    bench5 = chg5(scanner.fetch_daily("XLE"))
    rows = []
    for sym in NAMES:
        candles = scanner.fetch_daily(sym)
        rows.append((chg5(candles) - bench5, sym, candles))
    rows.sort(reverse=True)
    op = opens()
    print(f"TAILWIND - energy RS vs XLE (XLE 5d {bench5:+.2f}%): "
          + ", ".join(f"{s} {r:+.1f}" for r, s, _ in rows))
    for rs, sym, candles in rows:
        if sym in op:
            last = candles[-1]["close"]
            move = scanner.pct(last, op[sym]["entry_price"])
            if rs < 0 or move <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (RS discipline)")
                if log: log(BOT, sym, "exit", last, "TAILWIND exit: RS under zero or -8% rule")
    top_rs, top_sym, top_c = rows[0]
    if top_sym not in op and top_rs > 3:
        last = top_c[-1]["close"]
        print(f"  CALL: BUY {top_sym} @ ${last:.2f} (energy leader, RS {top_rs:+.2f} pts)")
        if log: log(BOT, top_sym, "buy", last, f"TAILWIND: energy RS leader at {top_rs:+.1f} pts")
    elif top_sym not in op:
        print("  no real lead in a slow sector, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
