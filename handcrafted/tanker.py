"""tanker.py - TANKER. LNG led energy trio craftsman.

LNG (the exporter) leads this trio; XOM and CVX follow the cargo.
TANKER buys a turning_up member only when LNG itself is up over
3% across five sessions (the cargo is moving). Exit on
falling_knife in the held name or the -8% rule. Similar water to
TAILWIND, different instrument: TANKER follows a leader stock,
TAILWIND follows the sector fund.

Run: python3 handcrafted/tanker.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "TANKER"
TRIO = ["LNG", "XOM", "CVX"]


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
    data = {}
    for sym in TRIO:
        candles = scanner.fetch_daily(sym)
        closes = [c["close"] for c in candles]
        data[sym] = (candles, ta.analyze(candles),
                     scanner.pct(closes[-1], closes[-6]))
    lead = data["LNG"][2]
    op = opens()
    print(f"TANKER - energy trio  LNG 5d {lead:+.2f}% (cargo moving: {lead > 3})")
    for sym in TRIO:
        candles, d, _c5 = data[sym]
        last = candles[-1]["close"]
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            if d["falling_knife"] or move <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (knife or -8% rule)")
                if log: log(BOT, sym, "exit", last, "TANKER exit: falling_knife or -8% rule")
    if lead > 3:
        for sym in TRIO:
            candles, d, _c5 = data[sym]
            last = candles[-1]["close"]
            if sym not in op and d["turning_up"]:
                print(f"  CALL: BUY {sym} @ ${last:.2f} (turning up behind a moving LNG)")
                if log: log(BOT, sym, "buy", last, "TANKER: LNG leading, name turning_up")
                break
        else:
            print("  cargo moving but nobody turning up, no call")
    else:
        print("  cargo still, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
