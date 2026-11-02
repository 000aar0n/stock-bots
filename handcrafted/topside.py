"""topside.py - TOPSIDE. Resistance rejection short, whole universe.

Price runs into the same ceiling twice: a high in the last 3
sessions within 1.5% of the best high of the prior 20 to 60
sessions, then a red day that closes under the prior session's
low on real volume. The ceiling held and the second test failed.
Short the rejection. Cover at +4% against or on a new 60
session closing high, which means the ceiling finally broke.
News unverified on every short; a human clears shorts before
anyone acts.

Run: python3 handcrafted/topside.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "TOPSIDE"
FLAG = "news unverified: TOPSIDE cannot check for fresh fundamental news"
RVOL_MIN = 1.1
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
    print("TOPSIDE - resistance rejection shorts over the wide universe")
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
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or last > max(closes[-61:-1]):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or ceiling broke)")
                if log: log(BOT, sym, "exit", last, "TOPSIDE cover")
            continue
        d = ta.analyze(candles)
        ceiling = max(c["high"] for c in candles[-61:-21])
        recent_high = max(c["high"] for c in candles[-3:])
        tested = recent_high >= ceiling * 0.985
        if (tested and last < candles[-1]["open"] and last < candles[-2]["low"]
                and (d["rel_volume"] or 0) >= RVOL_MIN):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (retested the ${ceiling:.2f} ceiling, rejected on {d['rel_volume']}x volume)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"TOPSIDE resistance rejection short; {FLAG}")
    if not hits:
        print("  no ceiling rejected today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
