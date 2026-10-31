"""keystone.py - KEYSTONE. Growth vs defensive spread craftsman.

The keystone number is the QQQ minus SPY five session spread.
Over +3: growth is carrying the arch, buy the growth basket's
RSI sweet spot name (NVDA, MSFT, PLTR with RSI 50 to 70). Under
-3: the arch leans defensive, buy the defensive basket's top
five session name (KO, JPM, UNH, WMT). Between: the arch is
balanced and KEYSTONE calls nothing. Exit when the spread
crosses to the other side, or the -8% rule.

Run: python3 handcrafted/keystone.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "KEYSTONE"
GROWTH = ["NVDA", "MSFT", "PLTR"]
DEFENSE = ["KO", "JPM", "UNH", "WMT"]


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
    spread = chg5(scanner.fetch_daily("QQQ")) - chg5(scanner.fetch_daily("SPY"))
    side = "growth" if spread > 3 else ("defense" if spread < -3 else None)
    basket = GROWTH if side == "growth" else (DEFENSE if side == "defense" else [])
    op = opens()
    print(f"KEYSTONE - QQQ minus SPY spread {spread:+.2f} pts: "
          f"{side or 'balanced, no side'}")
    for sym in list(op):
        candles = scanner.fetch_daily(sym)
        last = candles[-1]["close"]
        move = scanner.pct(last, op[sym]["entry_price"])
        if sym not in basket or move <= -8.0:
            why = "spread crossed, arch rebalanced" if sym not in basket else "-8% rule"
            print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
            if log: log(BOT, sym, "exit", last, f"KEYSTONE exit: {why}")
    if not side:
        print("  arch balanced, no call")
        return 0
    rows = []
    for sym in basket:
        if sym in op:
            continue
        candles = scanner.fetch_daily(sym)
        d = ta.analyze(candles)
        rows.append((chg5(candles), d["rsi14"], sym, candles[-1]["close"]))
    if side == "growth":
        rows = [r for r in rows if r[1] is not None and 50 <= r[1] <= 70]
    rows.sort(reverse=True)
    if rows:
        chg, rsi, sym, last = rows[0]
        print(f"  CALL: BUY {sym} @ ${last:.2f} ({side} keystone name, 5d "
              f"{chg:+.2f}%, RSI {rsi})")
        if log: log(BOT, sym, "buy", last, f"KEYSTONE: {side} spread at {spread:+.1f} pts")
    else:
        print("  side chosen but no name fits its test, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
