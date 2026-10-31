"""wake.py - WAKE. Fresh post gap drift, whole universe.

Post earnings drift, without needing the calendar: WAKE looks
for a gap day (open gapped over 5% either way, up gaps only for
entries) that happened 2 to 4 sessions ago, where price STILL
sits over that gap's midpoint today. The drift is alive; WAKE
rides it. Exit on the -8% rule. DRIFTER works the older window.

Run: python3 handcrafted/wake.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "WAKE"


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


def gap_day(candles, back):
    """(gap_pct, midpoint) if the candle `back` sessions ago gapped up."""
    i = len(candles) - 1 - back
    if i < 1:
        return None
    prev_close = candles[i - 1]["close"]
    gap = scanner.pct(candles[i]["open"], prev_close)
    if gap <= 5:
        return None
    return gap, (candles[i]["open"] + prev_close) / 2


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    op = opens()
    print("WAKE - fresh post gap drift (gap day 2 to 4 sessions back)")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        last = candles[-1]["close"]
        if sym in op:
            if scanner.pct(last, op[sym]["entry_price"]) <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (-8% rule)")
                if log: log(BOT, sym, "exit", last, "WAKE exit: -8% rule")
            continue
        for back in (2, 3, 4):
            g = gap_day(candles, back)
            if g and last > g[1]:
                hits += 1
                print(f"  CALL: BUY {sym} @ ${last:.2f} (gap {g[0]:+.2f}% from "
                      f"{back} sessions ago, still over its ${g[1]:.2f} midpoint)")
                if log: log(BOT, sym, "buy", last, f"WAKE: drift {back} sessions after a {g[0]:+.1f}% gap")
                break
    if not hits:
        print("  no live drift today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
