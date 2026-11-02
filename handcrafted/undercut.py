"""undercut.py - UNDERCUT. Breakdown continuation short, whole universe.

A level that held for a month stops holding: the close loses the
prior 20 session low on a red day with relative volume over 1.2,
already under the 50 day average so it is a weak name losing a
floor, not a strong name dipping. Short the continuation.
Cover at +4% against (the level reclaimed in spirit) or on a
close back above the 20 day average, which means the breakdown
failed. News unverified on every short; a human clears shorts
before anyone acts.

Run: python3 handcrafted/undercut.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "UNDERCUT"
FLAG = "news unverified: UNDERCUT cannot check for fresh fundamental news"
RVOL_MIN = 1.2
LOOKBACK = 20
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
    print("UNDERCUT - breakdown continuation shorts over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(candles) < 60:
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        d = ta.analyze(candles)
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or (d["sma20"] and last > d["sma20"]):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or breakdown failed)")
                if log: log(BOT, sym, "exit", last, "UNDERCUT cover")
            continue
        prior_low = min(c["low"] for c in candles[-LOOKBACK - 1:-1])
        if (last < prior_low and last < candles[-1]["open"]
                and (d["rel_volume"] or 0) >= RVOL_MIN
                and d["sma50"] and last < d["sma50"]):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (lost the {LOOKBACK}d low ${prior_low:.2f}, rel vol {d['rel_volume']})  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"UNDERCUT breakdown under lost level; {FLAG}")
    if not hits:
        print("  no breakdown today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
