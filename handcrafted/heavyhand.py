"""heavyhand.py - HEAVYHAND. Distribution short, whole universe.

Institutions cannot sell quietly in size: three or more down
days in the last five, every one of them on above average
volume, is a heavy hand distributing into the bid while price
is still under its 20 day average. The breakdown usually comes
after the distribution, not before. Short the distribution.
Cover at +4% against or on a close back above the 20 day
average, which means the supply was absorbed. News unverified
on every short; a human clears shorts before anyone acts.

Run: python3 handcrafted/heavyhand.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "HEAVYHAND"
FLAG = "news unverified: HEAVYHAND cannot check for fresh fundamental news"
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
    print("HEAVYHAND - distribution shorts over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(candles) < 40:
            continue
        closes = [c["close"] for c in candles]
        vols = [c["volume"] for c in candles]
        last = closes[-1]
        d = ta.analyze(candles)
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or (d["sma20"] and last > d["sma20"]):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or supply absorbed)")
                if log: log(BOT, sym, "exit", last, "HEAVYHAND cover")
            continue
        avg_vol = sum(vols[-25:-5]) / 20.0 if len(vols) >= 25 else 0
        heavy_downs = 0
        for i in range(-5, 0):
            if closes[i] < closes[i - 1] and avg_vol and vols[i] > avg_vol:
                heavy_downs += 1
        if heavy_downs >= 3 and d["sma20"] and last < d["sma20"]:
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} ({heavy_downs} heavy volume down days in the last 5, under the 20d average)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"HEAVYHAND distribution short; {FLAG}")
    if not hits:
        print("  no distribution today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
