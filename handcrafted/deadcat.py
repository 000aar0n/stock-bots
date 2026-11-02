"""deadcat.py - DEADCAT. Dead cat bounce fade, whole universe.

After a real fall (12% or more over 11 sessions) the first bounce
is usually rented, not owned: price pops at least 3% off the low
into the underside of a FALLING 20 day average and stalls. Short
the bounce into that resistance. Cover at +4% against, or into a
fresh 10 session low, which is the bounce fully failed and the
first target done. News unverified on every short; a human
clears shorts before anyone acts.

Run: python3 handcrafted/deadcat.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "DEADCAT"
FLAG = "news unverified: DEADCAT cannot check for fresh fundamental news"
DROP_MIN = -12.0
BOUNCE_MIN = 3.0
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
    print("DEADCAT - dead cat bounce fades over the wide universe")
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
            if against >= STOP_PCT or last < min(closes[-11:-1]):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or bounce failed to a new low)")
                if log: log(BOT, sym, "exit", last, "DEADCAT cover")
            continue
        # The fall: the lowest close of the last 11 sessions vs the
        # close 22 sessions back.
        fall = scanner.pct(min(closes[-11:]), closes[-22])
        bounce = scanner.pct(last, min(closes[-11:]))
        sma20_now = ta.sma(closes, 20)
        sma20_then = ta.sma(closes[:-5], 20)
        if (fall <= DROP_MIN and bounce >= BOUNCE_MIN
                and sma20_now and sma20_then and sma20_now < sma20_then
                and sma20_now * 0.94 <= last <= sma20_now * 1.01
                and last < closes[-22]):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (fell {fall:.1f}%, bounced {bounce:.1f}% into a falling 20d average)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"DEADCAT bounce fade at the falling 20d average; {FLAG}")
    if not hits:
        print("  no dead cat bouncing today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
