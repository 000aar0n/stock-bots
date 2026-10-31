"""foundry.py - FOUNDRY. AI infra laggard rotation craftsman.

SILICON buys the infra name the crowd is rotating INTO; FOUNDRY
buys the one they left behind, on a strict condition: basket
breadth over 50% (most of MU, SMCI, MRVL, AVGO over their
SMA20s, so the theme is healthy) and the laggard itself still
holds its SMA200. Rotation into the laggard of a healthy theme.
Exit at +6% (caught up) or the -8% rule.

Run: python3 handcrafted/foundry.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "FOUNDRY"
BASKET = ["MU", "SMCI", "MRVL", "AVGO"]


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
    rows = []
    for sym in BASKET:
        candles = scanner.fetch_daily(sym)
        closes = [c["close"] for c in candles]
        d = ta.analyze(candles)
        rows.append({"sym": sym, "last": closes[-1],
                     "chg5": scanner.pct(closes[-1], closes[-6]),
                     "over20": bool(d["sma20"] and closes[-1] > d["sma20"]),
                     "over200": bool(d["sma200"] and closes[-1] > d["sma200"])})
    breadth = 100.0 * sum(r["over20"] for r in rows) / len(rows)
    rows.sort(key=lambda r: r["chg5"])
    op = opens()
    print(f"FOUNDRY - infra laggard rotation  breadth {breadth:.0f}% over SMA20 "
          f"(need over 50)  laggard: {rows[0]['sym']} at {rows[0]['chg5']:+.2f}%")
    for r in rows:
        if r["sym"] in op:
            move = scanner.pct(r["last"], op[r["sym"]]["entry_price"])
            if move >= 6.0 or move <= -8.0:
                why = "caught up at +6%" if move >= 6 else "-8% rule"
                print(f"  CALL: EXIT {r['sym']} @ ${r['last']:.2f} ({why})")
                if log: log(BOT, r["sym"], "exit", r["last"], f"FOUNDRY exit: {why}")
    lag = rows[0]
    if breadth > 50 and lag["over200"] and lag["sym"] not in op:
        print(f"  CALL: BUY {lag['sym']} @ ${lag['last']:.2f} (laggard of a healthy theme)")
        if log: log(BOT, lag["sym"], "buy", lag["last"], "FOUNDRY: laggard rotation, theme breadth healthy")
    elif lag["sym"] not in op:
        print("  theme unhealthy or laggard broken, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
