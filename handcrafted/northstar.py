"""northstar.py - NORTHSTAR. Semis relative strength vs SMH.

The seven liquid semis ranked by five session RS against the
SMH sector fund; NORTHSTAR calls the leader when it beats the
sector by over 4 points. Exit when the held name's RS falls
under zero or the -8% rule. Narrower and sector pure where
COMPASS is broad tech.

Run: python3 handcrafted/northstar.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "NORTHSTAR"
SEMIS = ["NVDA", "AVGO", "AMD", "MU", "SMCI", "INTC", "MRVL"]


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
    bench5 = chg5(scanner.fetch_daily("SMH"))
    rows = []
    for sym in SEMIS:
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        rows.append((chg5(candles) - bench5, sym, candles))
    rows.sort(reverse=True)
    op = opens()
    print(f"NORTHSTAR - semis RS vs SMH (SMH 5d {bench5:+.2f}%): "
          + ", ".join(f"{s} {r:+.1f}" for r, s, _ in rows))
    for rs, sym, candles in rows:
        if sym in op:
            last = candles[-1]["close"]
            move = scanner.pct(last, op[sym]["entry_price"])
            if rs < 0 or move <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (RS discipline)")
                if log: log(BOT, sym, "exit", last, "NORTHSTAR exit: RS under zero or -8% rule")
    top_rs, top_sym, top_c = rows[0]
    if top_sym not in op and top_rs > 4:
        last = top_c[-1]["close"]
        print(f"  CALL: BUY {top_sym} @ ${last:.2f} (sector leader, RS {top_rs:+.2f} pts)")
        if log: log(BOT, top_sym, "buy", last, f"NORTHSTAR: semis RS leader at {top_rs:+.1f} pts")
    elif top_sym not in op:
        print("  no semi clears the sector by 4 points, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
