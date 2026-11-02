"""knifeback.py - KNIFEBACK. Knife catcher in reverse, whole universe.

Yesterday was a falling knife day: down 6% or more on one and a
half times normal volume. Today is the first bounce and it is
weak: green but small (3.5% or less) and closing in the bottom
half of its own range, which means sellers used the bounce as
an exit, not a bottom. Short the weak bounce. Cover at +4%
against or on a close under the knife day's low, the target,
where the bounce is proven dead. News unverified on every
short; a human clears shorts before anyone acts.

Run: python3 handcrafted/knifeback.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "KNIFEBACK"
FLAG = "news unverified: KNIFEBACK cannot check for fresh fundamental news"
KNIFE_MIN = -6.0
RVOL_MIN = 1.5
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
    print("KNIFEBACK - weak bounce shorts after falling knife days")
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
        knife = candles[-2]
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or last < knife["low"]:
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or knife low taken out)")
                if log: log(BOT, sym, "exit", last, "KNIFEBACK cover")
            continue
        knife_chg = scanner.pct(knife["close"], closes[-3])
        knife_ta = ta.analyze(candles[:-1])
        today = candles[-1]
        rng = today["high"] - today["low"]
        bounce = scanner.pct(last, knife["close"])
        weak_close = rng > 0 and (last - today["low"]) / rng <= 0.5
        if (knife_chg <= KNIFE_MIN and (knife_ta["rel_volume"] or 0) >= RVOL_MIN
                and 0 < bounce <= 3.5 and weak_close):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (knife day {knife_chg:.1f}% on {knife_ta['rel_volume']}x volume, bounce only {bounce:.1f}% and fading)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"KNIFEBACK short of the weak post knife bounce; {FLAG}")
    if not hits:
        print("  no weak bounce after a knife day, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
