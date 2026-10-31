"""silicon.py - SILICON. AI infrastructure basket craftsman.

Six AI infra names (NVDA, AVGO, MU, SMCI, MRVL, AMD). Where
FURNACE reads breadth of price over SMA20, SILICON reads breadth
of TREND: at least four of six with a positive MACD histogram.
Then it calls the member with the highest relative volume that
is turning_up (the one the crowd is rotating into). Exit when
the held name's histogram flips negative, or the -8% rule.

Run: python3 handcrafted/silicon.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "SILICON"
BASKET = ["NVDA", "AVGO", "MU", "SMCI", "MRVL", "AMD"]


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
        d = ta.analyze(candles)
        rows.append({"sym": sym, "last": candles[-1]["close"], "d": d,
                     "hist_pos": (d["macd_hist"] or 0) > 0})
    trend_breadth = sum(r["hist_pos"] for r in rows)
    op = opens()
    print(f"SILICON - AI infra basket  MACD histogram positive in "
          f"{trend_breadth} of {len(rows)} (need 4)")
    for r in rows:
        if r["sym"] in op:
            move = scanner.pct(r["last"], op[r["sym"]]["entry_price"])
            if not r["hist_pos"] or move <= -8.0:
                print(f"  CALL: EXIT {r['sym']} @ ${r['last']:.2f} (trend flipped)")
                if log: log(BOT, r["sym"], "exit", r["last"], "SILICON exit: MACD hist negative or -8% rule")
    if trend_breadth >= 4:
        cands = [r for r in rows if r["d"]["turning_up"] and r["sym"] not in op]
        cands.sort(key=lambda r: r["d"]["rel_volume"] or 0, reverse=True)
        if cands:
            r = cands[0]
            print(f"  CALL: BUY {r['sym']} @ ${r['last']:.2f} (crowd rotating in, "
                  f"rel vol {r['d']['rel_volume']})")
            if log: log(BOT, r["sym"], "buy", r["last"], "SILICON: basket trend breadth plus rotation volume")
        else:
            print("  breadth fine but nobody turning up, no call")
    else:
        print("  basket trend not broad enough, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
