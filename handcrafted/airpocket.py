"""airpocket.py - AIRPOCKET. Gap down through the shelf short, whole universe.

Yesterday's close sat within 2.5% of the 20 session low: a shelf
everyone could see. Today gaps down 3% or more through it and
closes in the bottom third of the range on heavy volume, so the
shelf became a trap door and trapped longs are the fuel. Short
the air pocket under the shelf. Cover at +4% against or on a
close back above yesterday's close, which means the gap filled
and the trap failed. News unverified on every short, and gaps
are often news: a human clears shorts before anyone acts.

Run: python3 handcrafted/airpocket.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "AIRPOCKET"
FLAG = "news unverified: AIRPOCKET cannot check what caused the gap"
GAP_MIN = -3.0
RVOL_MIN = 1.3
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
    print("AIRPOCKET - gap down through the shelf shorts over the wide universe")
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
        today, yday = candles[-1], candles[-2]
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or last > yday["close"]:
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or gap filled)")
                if log: log(BOT, sym, "exit", last, "AIRPOCKET cover")
            continue
        d = ta.analyze(candles)
        shelf = min(c["low"] for c in candles[-22:-2])
        gap = scanner.pct(today["open"], yday["close"])
        rng = today["high"] - today["low"]
        bottom_third = rng > 0 and (last - today["low"]) / rng <= 1 / 3
        if (gap <= GAP_MIN and yday["close"] <= shelf * 1.025
                and bottom_third and (d["rel_volume"] or 0) >= RVOL_MIN):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (gapped {gap:.1f}% through the ${shelf:.2f} shelf, closed at the lows on {d['rel_volume']}x volume)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"AIRPOCKET gap through support short; {FLAG}")
    if not hits:
        print("  no air pocket today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
