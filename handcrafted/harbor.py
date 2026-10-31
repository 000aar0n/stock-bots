"""harbor.py - HARBOR. Defensive basket, risk off only craftsman.

HARBOR only exists for bad weather: it activates when QQQ sits
UNDER its SMA50 (risk off tape). Then it buys the defensive
basket name (KO, PEP, WMT, COST, JPM, UNH) with the LOWEST RSI
still over 30 (cheapest shelter that is not collapsing) on a
green day. Exit everything when QQQ reclaims its SMA50: the
storm passed and shelter is dead money.

Run: python3 handcrafted/harbor.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "HARBOR"
BASKET = ["KO", "PEP", "WMT", "COST", "JPM", "UNH"]


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
    qqq = scanner.fetch_daily("QQQ")
    qd = ta.analyze(qqq)
    storm = qd["sma50"] and qqq[-1]["close"] < qd["sma50"]
    op = opens()
    print(f"HARBOR - defensive basket  QQQ under SMA50 (storm): {bool(storm)}")
    rows = []
    for sym in BASKET:
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        d = ta.analyze(candles)
        rows.append((d["rsi14"] if d["rsi14"] is not None else 999, sym,
                     candles[-1]["close"], candles))
    if not storm:
        for _r, sym, last, _c in rows:
            if sym in op:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (storm passed, QQQ reclaimed SMA50)")
                if log: log(BOT, sym, "exit", last, "HARBOR exit: QQQ back over SMA50")
        print("  no storm, harbor empty")
        return 0
    rows.sort()
    for rsi, sym, last, candles in rows:
        if sym in op:
            if scanner.pct(last, op[sym]["entry_price"]) <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (-8% rule)")
                if log: log(BOT, sym, "exit", last, "HARBOR exit: -8% rule")
    for rsi, sym, last, candles in rows:
        if sym not in op and 30 < rsi < 999 and last > candles[-1]["open"]:
            print(f"  CALL: BUY {sym} @ ${last:.2f} (cheapest sound shelter, RSI {rsi})")
            if log: log(BOT, sym, "buy", last, f"HARBOR: risk off shelter at RSI {rsi}")
            break
    else:
        print("  storm on but no sound shelter printing, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
