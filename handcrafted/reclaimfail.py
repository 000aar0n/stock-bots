"""reclaimfail.py - RECLAIMFAIL. Failed 20 day reclaim short, whole universe.

A weak name pokes above its 20 day average, cannot hold it, and
closes back underneath within 3 sessions while the average itself
is flat to falling: the reclaim was a head fake and the downtrend
is still in charge. Short the failure. Cover at +4% against or
on a close back above the 20 day average, which means the
reclaim finally stuck. News unverified on every short; a human
clears shorts before anyone acts.

Run: python3 handcrafted/reclaimfail.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "RECLAIMFAIL"
FLAG = "news unverified: RECLAIMFAIL cannot check for fresh fundamental news"
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
    print("RECLAIMFAIL - failed 20 day reclaim shorts over the wide universe")
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
        sma20 = ta.sma(closes, 20)
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or (sma20 and last > sma20):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or reclaim stuck)")
                if log: log(BOT, sym, "exit", last, "RECLAIMFAIL cover")
            continue
        if not sma20:
            continue
        sma20_5ago = ta.sma(closes[:-5], 20)
        poked = False
        for k in (3, 2, 1):
            s = ta.sma(closes[:-k], 20)
            if s and closes[-k] > s:
                poked = True
        if (poked and last < sma20 and last < candles[-1]["open"]
                and sma20_5ago and sma20 <= sma20_5ago * 1.002):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (reclaimed the 20d average, failed, closed back under it)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"RECLAIMFAIL short on the failed 20d reclaim; {FLAG}")
    if not hits:
        print("  no failed reclaim today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
