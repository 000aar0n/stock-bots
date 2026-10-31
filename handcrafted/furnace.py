"""furnace.py - FURNACE. Nuclear basket heat craftsman.

Nine nuclear names (OKLO, SMR, NNE, CCJ, UUUU, DNN, CEG, VST,
BWXT). FURNACE measures the whole basket's heat: the share of
names above their SMA20 (breadth) and the median five session
move. When breadth is 60%+ and the median is positive, the
furnace is lit and FURNACE calls the two hottest names by five
session gain. Below 40% breadth it exits what it holds.

Run: python3 handcrafted/furnace.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
import statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "FURNACE"
BASKET = ["OKLO", "SMR", "NNE", "CCJ", "UUUU", "DNN", "CEG", "VST", "BWXT"]


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
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        d = ta.analyze(candles)
        rows.append({"sym": sym, "last": closes[-1],
                     "chg5": scanner.pct(closes[-1], closes[-6]),
                     "above": bool(d["sma20"] and closes[-1] > d["sma20"])})
    if not rows:
        print("FURNACE - no basket data"); return 0
    breadth = 100.0 * sum(r["above"] for r in rows) / len(rows)
    median5 = statistics.median(r["chg5"] for r in rows)
    rows.sort(key=lambda r: r["chg5"], reverse=True)
    op = opens()
    print(f"FURNACE - nuclear basket  breadth {breadth:.0f}% above SMA20  "
          f"median 5d {median5:+.2f}%")
    lit = breadth >= 60 and median5 > 0
    for r in rows:
        if r["sym"] in op and (breadth < 40
                               or scanner.pct(r["last"], op[r["sym"]]["entry_price"]) <= -8.0):
            print(f"  CALL: EXIT {r['sym']} @ ${r['last']:.2f} (furnace cooled)")
            if log: log(BOT, r["sym"], "exit", r["last"], "FURNACE exit: breadth under 40% or -8% rule")
    if lit:
        for r in rows[:2]:
            if r["sym"] not in op:
                print(f"  CALL: BUY {r['sym']} @ ${r['last']:.2f} (hottest in a lit furnace, 5d {r['chg5']:+.2f}%)")
                if log: log(BOT, r["sym"], "buy", r["last"], f"FURNACE: basket lit, 5d {r['chg5']:+.1f}%")
    else:
        print("  furnace not lit, no new calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
