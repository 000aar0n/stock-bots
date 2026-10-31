"""vanguard.py - VANGUARD. Healthcare RS vs XLV craftsman.

Four healthcare names (REGN, LLY, UNH, MRNA) ranked by five
session RS against the XLV fund, with a quality gate the other
RS bots do not use: the leader must ALSO sit above its SMA50
(healthcare leadership in a broken chart is a head fake). Exit
on RS under zero or the -8% rule.

Run: python3 handcrafted/vanguard.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "VANGUARD"
NAMES = ["REGN", "LLY", "UNH", "MRNA"]


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
    bench5 = chg5(scanner.fetch_daily("XLV"))
    rows = []
    for sym in NAMES:
        candles = scanner.fetch_daily(sym)
        d = ta.analyze(candles)
        above = d["sma50"] and candles[-1]["close"] > d["sma50"]
        rows.append((chg5(candles) - bench5, sym, candles, bool(above)))
    rows.sort(key=lambda r: r[0], reverse=True)
    op = opens()
    print(f"VANGUARD - healthcare RS vs XLV (XLV 5d {bench5:+.2f}%): "
          + ", ".join(f"{s} {r:+.1f}" for r, s, _, _ in rows))
    for rs, sym, candles, _above in rows:
        if sym in op:
            last = candles[-1]["close"]
            move = scanner.pct(last, op[sym]["entry_price"])
            if rs < 0 or move <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (RS discipline)")
                if log: log(BOT, sym, "exit", last, "VANGUARD exit: RS under zero or -8% rule")
    top_rs, top_sym, top_c, top_above = rows[0]
    if top_sym not in op and top_rs > 2 and top_above:
        last = top_c[-1]["close"]
        print(f"  CALL: BUY {top_sym} @ ${last:.2f} (healthcare vanguard, RS "
              f"{top_rs:+.2f} pts, above SMA50)")
        if log: log(BOT, top_sym, "buy", last, f"VANGUARD: healthcare RS leader at {top_rs:+.1f} pts")
    elif top_sym not in op:
        print("  leader fails the margin or the SMA50 gate, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
