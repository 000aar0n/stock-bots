"""catapult.py - CATAPULT. Gap down reversal, whole universe.

The mirror of SLINGSHOT: a name that opens gapped DOWN over 5%,
prints a hammer, and closes back over the gap midpoint (half the
fall reclaimed intraday) has loaded the catapult. Entry at that
close. Exit at +6% (the launch) or the -8% rule.

Run: python3 handcrafted/catapult.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "CATAPULT"


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
    print("CATAPULT - gap down reversal over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        last, today = closes[-1], candles[-1]
        prev_close = closes[-2]
        gap = scanner.pct(today["open"], prev_close)
        mid = (today["open"] + prev_close) / 2
        d = ta.analyze(candles)
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            if move >= 6.0 or move <= -8.0:
                why = "launched at +6%" if move >= 6 else "-8% rule"
                print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
                if log: log(BOT, sym, "exit", last, f"CATAPULT exit: {why}")
            continue
        if gap < -5 and "hammer" in d["patterns"] and last > mid:
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (gapped {gap:+.2f}%, reclaimed "
                  f"the ${mid:.2f} midpoint with a hammer)")
            if log: log(BOT, sym, "buy", last, f"CATAPULT: gap {gap:+.1f}% reversal over midpoint")
    if not hits:
        print("  no loaded catapults today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
