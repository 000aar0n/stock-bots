"""crosscurrent.py - CROSSCURRENT. Value vs growth rotation craftsman.

DIA (industrials, value) vs QQQ (growth) over five sessions
says which current is running. DIA ahead: buy the top of the
value basket (JPM, XOM, KO, WMT). QQQ ahead: buy the top of the
growth basket (NVDA, MSFT, PLTR, AMZN). Top means the best five
session move in that basket. Exit when the other current takes
over, or the -8% rule.

Run: python3 handcrafted/crosscurrent.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "CROSSCURRENT"
VALUE = ["JPM", "XOM", "KO", "WMT"]
GROWTH = ["NVDA", "MSFT", "PLTR", "AMZN"]


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


def top(basket):
    rows = []
    for sym in basket:
        candles = scanner.fetch_daily(sym)
        rows.append((chg5(candles), sym, candles[-1]["close"]))
    rows.sort(reverse=True)
    return rows[0]


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    dia5, qqq5 = chg5(scanner.fetch_daily("DIA")), chg5(scanner.fetch_daily("QQQ"))
    value_runs = dia5 > qqq5
    basket = VALUE if value_runs else GROWTH
    op = opens()
    print(f"CROSSCURRENT - rotation  DIA 5d {dia5:+.2f}% vs QQQ {qqq5:+.2f}%: "
          f"{'value' if value_runs else 'growth'} current running")
    for sym in list(op):
        candles = scanner.fetch_daily(sym)
        last = candles[-1]["close"]
        move = scanner.pct(last, op[sym]["entry_price"])
        if sym not in basket or move <= -8.0:
            why = "the other current took over" if sym not in basket else "-8% rule"
            print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
            if log: log(BOT, sym, "exit", last, f"CROSSCURRENT exit: {why}")
    chg, sym, last = top(basket)
    if sym not in op:
        print(f"  CALL: BUY {sym} @ ${last:.2f} (top of the running current, 5d {chg:+.2f}%)")
        if log: log(BOT, sym, "buy", last, f"CROSSCURRENT: {'value' if value_runs else 'growth'} basket top")
    return 0


if __name__ == "__main__":
    sys.exit(main())
