"""kindling.py - KINDLING. Volume drought ignition, whole universe.

The setup nobody watches: three straight days of relative
volume under 0.6 (the name is forgotten), then a green day at
over 1.8 (someone remembered, loudly). KINDLING buys that first
loud day. Exit on the -8% rule.

Run: python3 handcrafted/kindling.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "KINDLING"


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
    print("KINDLING - drought ignition over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        vols = [c["volume"] for c in candles]
        last = closes[-1]
        if sym in op:
            if scanner.pct(last, op[sym]["entry_price"]) <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (-8% rule)")
                if log: log(BOT, sym, "exit", last, "KINDLING exit: -8% rule")
            continue
        avg20 = sum(vols[-21:-1]) / 20 if len(vols) > 21 else 0
        if not avg20:
            continue
        dry = all(v / avg20 < 0.6 for v in vols[-4:-1])
        loud = vols[-1] / avg20 > 1.8
        if dry and loud and last > candles[-1]["open"]:
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (three dry days, then "
                  f"{vols[-1] / avg20:.1f}x volume)")
            if log: log(BOT, sym, "buy", last, "KINDLING: drought then ignition volume")
    if not hits:
        print("  nothing caught fire today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
