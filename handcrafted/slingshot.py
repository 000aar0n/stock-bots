"""slingshot.py - SLINGSHOT. Same day gap continuation, whole universe.

Where FLASH waits a session for proof, SLINGSHOT takes the gap
day itself: any universe name that OPENS gapped up over 4% and
CLOSES over its open (buyers defended the gap all day) gets a
continuation call at the close. Exit on the -8% rule. One call
per name, widest net in the gap family.

Run: python3 handcrafted/slingshot.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "SLINGSHOT"


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
    print("SLINGSHOT - same day gap continuation over the wide universe")
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
            if scanner.pct(last, op[sym]["entry_price"]) <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (-8% rule)")
                if log: log(BOT, sym, "exit", last, "SLINGSHOT exit: -8% rule")
            continue
        if gap > 4 and last > today["open"]:
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (opened {gap:+.2f}% and held)")
            if log: log(BOT, sym, "buy", last, f"SLINGSHOT: gap {gap:+.1f}% held into close")
    if not hits:
        print("  no gap held today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
