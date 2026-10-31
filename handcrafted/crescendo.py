"""crescendo.py - CRESCENDO. Volume climax momentum, whole universe.

Entry: relative volume over 2.5, a green day, and the close in
the TOP QUARTILE of the day's range (the climax finished at the
highs, buyers won the loudest day). Exit on two red closes or
the -8% rule. AVALANCHE trades the same climax on red days.

Run: python3 handcrafted/crescendo.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "CRESCENDO"


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
    print("CRESCENDO - volume climax momentum over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        today, last = candles[-1], closes[-1]
        d = ta.analyze(candles)
        rng = today["high"] - today["low"]
        top_quartile = rng > 0 and (last - today["low"]) / rng >= 0.75
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            two_red = closes[-1] < closes[-2] < closes[-3]
            if two_red or move <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (climax spent)")
                if log: log(BOT, sym, "exit", last, "CRESCENDO exit: two red closes or -8% rule")
            continue
        if (d["rel_volume"] or 0) > 2.5 and last > today["open"] and top_quartile:
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (rel vol {d['rel_volume']}, closed at the highs)")
            if log: log(BOT, sym, "buy", last, f"CRESCENDO: volume climax at rel vol {d['rel_volume']}")
    if not hits:
        print("  no climax today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
