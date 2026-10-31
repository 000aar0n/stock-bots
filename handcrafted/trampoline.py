"""trampoline.py - TRAMPOLINE. Failed gap short, whole universe.

A name that gaps up over 6% at the open and closes RED has
bounced off the trampoline and is falling back through it.
TRAMPOLINE shorts that close anywhere in the universe (MIRAGE
works only SNDK, by hand; this is the wide net version). Exit at
+5% against or two green closes. News unverified on every short:
a human clears shorts before anyone acts.

Run: python3 handcrafted/trampoline.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "TRAMPOLINE"
FLAG = "news unverified: TRAMPOLINE cannot check for fresh fundamental news"


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
    print("TRAMPOLINE - failed gap shorts over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        last, today = closes[-1], candles[-1]
        gap = scanner.pct(today["open"], closes[-2])
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            two_green = closes[-1] > closes[-2] > closes[-3]
            if against >= 5.0 or two_green:
                print(f"  CALL: EXIT short {sym} @ ${last:.2f}")
                if log: log(BOT, sym, "exit", last, "TRAMPOLINE cover")
            continue
        if gap > 6 and last < today["open"]:
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (gap {gap:+.2f}% failed)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"TRAMPOLINE failed gap; {FLAG}")
    if not hits:
        print("  no failed gaps today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
