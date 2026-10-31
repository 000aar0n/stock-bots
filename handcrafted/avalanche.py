"""avalanche.py - AVALANCHE. Volume climax short, whole universe.

CRESCENDO's dark twin: relative volume over 2.5, a RED day, and
the close in the BOTTOM QUARTILE of the day's range (the loudest
day ended at the lows: distribution, not a dip). Short entry.
Exit at +5% against or two green closes. News unverified on
every short; a human clears shorts before anyone acts.

Run: python3 handcrafted/avalanche.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "AVALANCHE"
FLAG = "news unverified: AVALANCHE cannot check for fresh fundamental news"


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
    print("AVALANCHE - volume climax shorts over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        today, last = candles[-1], closes[-1]
        d = ta.analyze(candles)
        rng = today["high"] - today["low"]
        bottom_quartile = rng > 0 and (last - today["low"]) / rng <= 0.25
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            two_green = closes[-1] > closes[-2] > closes[-3]
            if against >= 5.0 or two_green:
                print(f"  CALL: EXIT short {sym} @ ${last:.2f}")
                if log: log(BOT, sym, "exit", last, "AVALANCHE cover")
            continue
        if (d["rel_volume"] or 0) > 2.5 and last < today["open"] and bottom_quartile:
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (rel vol {d['rel_volume']}, closed at the lows)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"AVALANCHE climax short; {FLAG}")
    if not hits:
        print("  no avalanche today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
