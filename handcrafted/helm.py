"""helm.py - HELM. Index gated core picker craftsman.

HELM steers by one star: SPY over its SMA50 or not. In a risk on
tape it calls the strongest turning_up name in the core 20 (top
five session gain among the turning_up set). Under the SMA50 it
calls NOTHING at all: the helm's whole job is refusing to steer
into the storm. Exit on the -8% rule or when SPY loses the
SMA50.

Run: python3 handcrafted/helm.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "HELM"


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
    spy = scanner.fetch_daily("SPY")
    sd = ta.analyze(spy)
    risk_on = bool(sd["sma50"] and spy[-1]["close"] > sd["sma50"])
    op = opens()
    print(f"HELM - index gated picker  SPY over SMA50 (risk on): {risk_on}")
    if not risk_on:
        for sym in list(op):
            candles = scanner.fetch_daily(sym)
            last = candles[-1]["close"]
            print(f"  CALL: EXIT {sym} @ ${last:.2f} (SPY lost the SMA50)")
            if log: log(BOT, sym, "exit", last, "HELM exit: SPY under SMA50")
        print("  storm course: no calls while SPY sits under its SMA50")
        return 0
    best = None
    for sym in scanner.CORE_INTRADAY:
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        if sym in op:
            if scanner.pct(last, op[sym]["entry_price"]) <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (-8% rule)")
                if log: log(BOT, sym, "exit", last, "HELM exit: -8% rule")
            continue
        d = ta.analyze(candles)
        if d["turning_up"]:
            chg5 = scanner.pct(closes[-1], closes[-6])
            if best is None or chg5 > best[0]:
                best = (chg5, sym, last)
    if best:
        print(f"  CALL: BUY {best[1]} @ ${best[2]:.2f} (strongest turning_up core "
              f"name, 5d {best[0]:+.2f}%)")
        if log: log(BOT, best[1], "buy", best[2], "HELM: SPY risk on, strongest core turning_up")
    else:
        print("  risk on but no core name turning up, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
