"""outlier.py - OUTLIER. Whole universe relative strength vs SPY.

The widest RS net: every universe name's five session move
minus SPY's. OUTLIER calls the single top outperformer, but only
if it also sits above its SMA50 (an outperformer in a downtrend
is usually one lucky bounce). Exit when the name drops out of
the top five or the -8% rule hits.

Run: python3 handcrafted/outlier.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "OUTLIER"


def universe():
    out = []
    for names in scanner.UNIVERSE.values():
        for t in names:
            if t not in out:
                out.append(t)
    return out


def chg5(candles):
    closes = [c["close"] for c in candles]
    return scanner.pct(closes[-1], closes[-6])


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
    spy5 = chg5(scanner.fetch_daily("SPY"))
    rows = []
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        d = ta.analyze(candles)
        above = bool(d["sma50"] and candles[-1]["close"] > d["sma50"])
        rows.append((chg5(candles) - spy5, sym, candles, above))
    rows.sort(key=lambda r: r[0], reverse=True)
    op = opens()
    top5 = {r[1] for r in rows[:5]}
    print(f"OUTLIER - universe RS vs SPY (SPY 5d {spy5:+.2f}%): "
          + ", ".join(f"{s} {r:+.1f}" for r, s, _, _ in rows[:5]))
    for rs, sym, candles, _a in rows:
        if sym in op:
            last = candles[-1]["close"]
            move = scanner.pct(last, op[sym]["entry_price"])
            if sym not in top5 or move <= -8.0:
                why = "fell out of the top five" if sym not in top5 else "-8% rule"
                print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
                if log: log(BOT, sym, "exit", last, f"OUTLIER exit: {why}")
    top_rs, top_sym, top_c, top_above = rows[0]
    if top_sym not in op and top_above:
        last = top_c[-1]["close"]
        print(f"  CALL: BUY {top_sym} @ ${last:.2f} (the outlier, RS {top_rs:+.2f} pts)")
        if log: log(BOT, top_sym, "buy", last, f"OUTLIER: top RS vs SPY at {top_rs:+.1f} pts")
    elif top_sym not in op:
        print("  top outperformer fails the SMA50 gate, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
