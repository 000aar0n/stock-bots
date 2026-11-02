"""parabolic.py - PARABOLIC. Vertical run exhaustion short, whole universe.

A 25% or greater gain in 10 sessions is not a trend, it is a
crowd. The short is not the top tick: it is the first close
under the prior session's low after the vertical run, the first
lower low, when the last buyers are already in and the first
sellers finally get a print. Cover at +5% against (vertical
names can squeeze, so the stop is wider and respected) or on a
new 20 session closing high. News unverified on every short,
and parabolic names are squeeze risks first: a human clears
shorts before anyone acts.

Run: python3 handcrafted/parabolic.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "PARABOLIC"
FLAG = "news unverified: PARABOLIC cannot check for fresh fundamental news"
RUN_MIN = 25.0
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
    print("PARABOLIC - vertical run exhaustion shorts over the wide universe")
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
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or last > max(closes[-21:-1]):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or run resumed)")
                if log: log(BOT, sym, "exit", last, "PARABOLIC cover")
            continue
        run = scanner.pct(last, closes[-11])
        if (run >= RUN_MIN and last < candles[-2]["low"]
                and last < candles[-1]["open"]):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (up {run:.1f}% in 10 sessions, first lower low)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"PARABOLIC exhaustion short on the first lower low; {FLAG}")
    if not hits:
        print("  no parabola cracking today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
