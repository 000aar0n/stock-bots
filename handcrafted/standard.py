"""standard.py - STANDARD. Banks relative strength vs XLF.

The bank standard: JPM and BAC only, five session moves measured
against the XLF fund. Buy whichever leads, only if it also beats
the fund outright (leading a falling sector is not strength).
Exit when the held bank's RS vs XLF goes negative, or -8%.

Run: python3 handcrafted/standard.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "STANDARD"
NAMES = ["JPM", "BAC"]


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
    bench5 = chg5(scanner.fetch_daily("XLF"))
    rows = []
    for sym in NAMES:
        candles = scanner.fetch_daily(sym)
        rows.append((chg5(candles) - bench5, sym, candles))
    rows.sort(reverse=True)
    op = opens()
    print(f"STANDARD - banks RS vs XLF (XLF 5d {bench5:+.2f}%): "
          + ", ".join(f"{s} {r:+.1f}" for r, s, _ in rows))
    for rs, sym, candles in rows:
        if sym in op:
            last = candles[-1]["close"]
            move = scanner.pct(last, op[sym]["entry_price"])
            if rs < 0 or move <= -8.0:
                print(f"  CALL: EXIT {sym} @ ${last:.2f} (RS discipline)")
                if log: log(BOT, sym, "exit", last, "STANDARD exit: RS under zero or -8% rule")
    top_rs, top_sym, top_c = rows[0]
    if top_sym not in op and top_rs > 0:
        last = top_c[-1]["close"]
        print(f"  CALL: BUY {top_sym} @ ${last:.2f} (sets the bank standard)")
        if log: log(BOT, top_sym, "buy", last, f"STANDARD: bank RS leader at {top_rs:+.1f} pts")
    elif top_sym not in op:
        print("  neither bank beats the fund, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
