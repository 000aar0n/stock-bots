"""laggard.py - LAGGARD. Sector relative weakness short, whole universe.

Money rotates inside a sector before it leaves it: the name
trailing its own group's median 5 session move by 6 points or
more, already under its 50 day average but not washed out
(RSI 35 or higher, so it is weakness, not a capitulation low),
is the one holders sell next. Short the laggard. Cover at +4%
against or when its relative move climbs back to the group
median, which means the rotation passed it by. News unverified
on every short; a human clears shorts before anyone acts.

Run: python3 handcrafted/laggard.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "LAGGARD"
FLAG = "news unverified: LAGGARD cannot check for fresh fundamental news"
GAP_MIN = -6.0
STOP_PCT = 4.0


def universe():
    out = []
    for names in scanner.UNIVERSE.values():
        for t in names:
            if t not in out:
                out.append(t)
    return out


def group_of(sym):
    for g, names in scanner.UNIVERSE.items():
        if sym in names:
            return g, names
    return None, []


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


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
    print("LAGGARD - sector relative weakness shorts over the wide universe")
    # One pass: every name's 5 session move and its group median.
    moves, cache = {}, {}
    for g, names in scanner.UNIVERSE.items():
        vals = []
        for sym in names:
            try:
                candles = scanner.fetch_daily(sym)
            except Exception:  # noqa: BLE001
                continue
            if len(candles) < 60:
                continue
            cache[sym] = candles
            moves[sym] = scanner.pct(candles[-1]["close"], candles[-6]["close"])
            vals.append(moves[sym])
        if vals:
            for sym in names:
                if sym in moves:
                    moves[(sym, "median")] = median(vals)
    hits = 0
    for sym in universe():
        candles = cache.get(sym)
        if candles is None or sym not in moves or (sym, "median") not in moves:
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        rel = moves[sym] - moves[(sym, "median")]
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or rel >= 0:
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or relative weakness healed)")
                if log: log(BOT, sym, "exit", last, "LAGGARD cover")
            continue
        d = ta.analyze(candles)
        if (rel <= GAP_MIN and d["sma50"] and last < d["sma50"]
                and d["rsi14"] is not None and d["rsi14"] >= 35
                and (d["rel_volume"] or 0) >= 0.9):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (trails its sector median by {abs(rel):.1f} pts over 5d, under the 50d average)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"LAGGARD sector relative weakness short; {FLAG}")
    if not hits:
        print("  no laggard today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
