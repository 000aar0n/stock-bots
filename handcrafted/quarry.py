"""quarry.py - QUARRY. Uranium trio, bellwether gated craftsman.

CCJ, UUUU, DNN. Uranium moves as a tribe, so QUARRY takes its
orders from the bellwether: UUUU must be turning_up (WICK's RSI
and MACD bounce) before ANY name is bought, and the bought name
must itself sit over its SMA20. Exit on falling_knife in the
held name, or the -8% rule.

Run: python3 handcrafted/quarry.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "QUARRY"
TRIO = ["CCJ", "UUUU", "DNN"]


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
        data[sym] = (candles, ta.analyze(candles))
    gate = data["UUUU"][1]["turning_up"]
    op = opens()
    print(f"QUARRY - uranium trio  bellwether UUUU turning_up: {gate}")
    for sym in TRIO:
        candles, d = data[sym]
        last = candles[-1]["close"]
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            if d["falling_knife"] or move <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (knife or -8% rule)")
                if log: log(BOT, sym, "exit", last, "QUARRY exit: falling_knife or -8% rule")
    if gate:
        for sym in TRIO:
            candles, d = data[sym]
            last = candles[-1]["close"]
            if sym not in op and d["sma20"] and last > d["sma20"]:
                print(f"  CALL: BUY {sym} @ ${last:.2f} (bellwether leads, name over SMA20)")
                if log: log(BOT, sym, "buy", last, "QUARRY: UUUU turning_up gate open")
                break
        else:
            print("  gate open but no name over its SMA20, no call")
    else:
        print("  bellwether quiet, the quarry is closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
