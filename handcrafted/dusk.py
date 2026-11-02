"""dusk.py - DUSK. Closing weakness sequence short, whole universe.

Where a stock closes inside its own day range is who won the
day: three straight closes in the bottom quartile of the range
means sellers pressed into the bell three days running, while
price sits under its 20 day average. One weak close is noise;
three is a habit, and habits in the tape persist. Short the
habit. Cover at +4% against or on the first close in the top
quartile of its range, which means buyers finally held a
close. News unverified on every short; a human clears shorts
before anyone acts.

Run: python3 handcrafted/dusk.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "DUSK"
FLAG = "news unverified: DUSK cannot check for fresh fundamental news"
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


def range_pos(candle):
    rng = candle["high"] - candle["low"]
    if rng <= 0:
        return None
    return (candle["close"] - candle["low"]) / rng


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    op = opens()
    print("DUSK - closing weakness sequence shorts over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(candles) < 30:
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        d = ta.analyze(candles)
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            pos = range_pos(candles[-1])
            if against >= STOP_PCT or (pos is not None and pos >= 0.75):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or buyers held a close)")
                if log: log(BOT, sym, "exit", last, "DUSK cover")
            continue
        positions = [range_pos(c) for c in candles[-3:]]
        if (all(p is not None and p <= 0.25 for p in positions)
                and d["sma20"] and last < d["sma20"]
                and (d["rel_volume"] or 0) >= 1.0):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (three straight closes in the bottom quartile of the range, under the 20d average)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"DUSK closing weakness sequence short; {FLAG}")
    if not hits:
        print("  no dusk pattern today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
