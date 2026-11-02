"""anchorless.py - ANCHORLESS. Loss of the 200 day anchor short, whole universe.

The 200 day average is the last anchor: twenty sessions ago the
name lived above it, now it closes underneath on real volume,
with RSI still 55 or lower so this is a regime break, not a
one day crash print. Names that lose the 200 tend to stay lost
while long term holders re-underwrite the position. Short the
regime break. Cover at +5% against or on a close back above
the 200 day average. News unverified on every short; a human
clears shorts before anyone acts.

Run: python3 handcrafted/anchorless.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "ANCHORLESS"
FLAG = "news unverified: ANCHORLESS cannot check for fresh fundamental news"
RVOL_MIN = 1.1
STOP_PCT = 5.0


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
    print("ANCHORLESS - loss of the 200 day anchor shorts over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(candles) < 230:
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        d = ta.analyze(candles)
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or (d["sma200"] and last > d["sma200"]):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or anchor regained)")
                if log: log(BOT, sym, "exit", last, "ANCHORLESS cover")
            continue
        sma200_then = ta.sma(closes[:-20], 200)
        if (d["sma200"] and sma200_then and last < d["sma200"]
                and closes[-21] > sma200_then
                and (d["rel_volume"] or 0) >= RVOL_MIN
                and d["rsi14"] is not None and d["rsi14"] <= 55):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (lost the 200d average ${d['sma200']:.2f} it lived above 20 sessions ago)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"ANCHORLESS 200d regime break short; {FLAG}")
    if not hits:
        print("  no anchor lost today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
