"""lowertide.py - LOWERTIDE. Lower highs sequence short, whole universe.

No single day makes this call: three consecutive 10 session
windows each printing a lower high than the window before is a
tide going out, buyers bidding less every time. With the close
under its 20 day average and already 3% or more under the most
recent window's high, the structure says the next test fails
too. Short the sequence. Cover at +4% against or on a close
above the most recent window's high, the first higher high,
which breaks the sequence. News unverified on every short;
a human clears shorts before anyone acts.

Run: python3 handcrafted/lowertide.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "LOWERTIDE"
FLAG = "news unverified: LOWERTIDE cannot check for fresh fundamental news"
STOP_PCT = 4.0


def universe():
    out = []
    for names in scanner.UNIVERSE.values():
        for t in names:
            if t not in out:
                out.append(t)
    return out


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
    print("LOWERTIDE - lower highs sequence shorts over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(candles) < 40:
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        w1 = max(c["high"] for c in candles[-30:-20])
        w2 = max(c["high"] for c in candles[-20:-10])
        w3 = max(c["high"] for c in candles[-10:])
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or last > w3:
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or first higher high)")
                if log: log(BOT, sym, "exit", last, "LOWERTIDE cover")
            continue
        d = ta.analyze(candles)
        if (w1 > w2 > w3 and d["sma20"] and last < d["sma20"]
                and last <= w3 * 0.97):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (three lower highs in a row: {w1:.2f} then {w2:.2f} then {w3:.2f})  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"LOWERTIDE lower highs sequence short; {FLAG}")
    if not hits:
        print("  no lower tide today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
