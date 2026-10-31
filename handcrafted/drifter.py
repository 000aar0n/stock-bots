"""drifter.py - DRIFTER. Mature post gap drift, whole universe.

WAKE works gaps 2 to 4 sessions old; DRIFTER works the mature
drift: a 5%+ gap day 5 to 10 sessions back, price still over
that gap day's CLOSE (not just the midpoint), and the SMA20
rising underneath. That is a drift with a floor. Exit -8%.

Run: python3 handcrafted/drifter.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "DRIFTER"


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
    print("DRIFTER - mature post gap drift (gap day 5 to 10 sessions back)")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        if sym in op:
            if scanner.pct(last, op[sym]["entry_price"]) <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (-8% rule)")
                if log: log(BOT, sym, "exit", last, "DRIFTER exit: -8% rule")
            continue
        sma20_now, sma20_then = ta.sma(closes, 20), ta.sma(closes[:-5], 20)
        rising = sma20_now and sma20_then and sma20_now > sma20_then
        if not rising:
            continue
        for back in range(5, 11):
            i = len(candles) - 1 - back
            gap = scanner.pct(candles[i]["open"], candles[i - 1]["close"])
            if gap > 5 and last > candles[i]["close"]:
                hits += 1
                print(f"  CALL: BUY {sym} @ ${last:.2f} (gap {gap:+.2f}% from {back} "
                      f"sessions ago, drift floored by a rising SMA20)")
                if log: log(BOT, sym, "buy", last, f"DRIFTER: mature drift {back} sessions after a {gap:+.1f}% gap")
                break
    if not hits:
        print("  no mature drift today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
