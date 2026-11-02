"""crossdown.py - CROSSDOWN. Fresh 50 day breakdown short, whole universe.

The 50 day average is the line institutions defend. A name that
was above it three sessions ago and closes under it now, with
the 20 day already under the 50 (short term momentum rolled
first) and a negative 5 session move, has slipped out of the
bid stream. Short the fresh cross, while it is fresh. Cover at
+4% against or on a close back above the 50 day average.
News unverified on every short; a human clears shorts before
anyone acts.

Run: python3 handcrafted/crossdown.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "CROSSDOWN"
FLAG = "news unverified: CROSSDOWN cannot check for fresh fundamental news"
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
    print("CROSSDOWN - fresh 50 day breakdown shorts over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(candles) < 70:
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        d = ta.analyze(candles)
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or (d["sma50"] and last > d["sma50"]):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or 50d reclaimed)")
                if log: log(BOT, sym, "exit", last, "CROSSDOWN cover")
            continue
        sma50_3ago = ta.sma(closes[:-3], 50)
        if (d["sma50"] and d["sma20"] and sma50_3ago
                and last < d["sma50"] and closes[-4] > sma50_3ago
                and d["sma20"] < d["sma50"]
                and scanner.pct(last, closes[-6]) < 0):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (fresh close under the 50d average ${d['sma50']:.2f}, 20d already beneath it)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"CROSSDOWN fresh 50d breakdown short; {FLAG}")
    if not hits:
        print("  no fresh 50d break today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
