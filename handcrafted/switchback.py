"""switchback.py - SWITCHBACK. TSLA trend dip swing craftsman. SWING.

Declared swing: the ride back to the high takes days. Rule:
TSLA down 7% or more from its 10 day high while still over the
SMA50 (a switchback on the climb, not a cliff), with a hammer
printed at the turn. Exit back at the 10 day high or the -8%
rule.

Run: python3 handcrafted/switchback.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "SWITCHBACK", "TSLA"


def my_open():
    from leaderboard import load_calls
    op = None
    for c in load_calls():
        if c["bot"] == BOT and c["ticker"] == SYM:
            if c["side"] == "buy": op = op or c
            elif c["side"] == "exit": op = None
    return op


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    candles = scanner.fetch_daily(SYM)
    closes = [c["close"] for c in candles]
    last, d = closes[-1], ta.analyze(candles)
    hi10 = max(closes[-11:-1])
    dip = scanner.pct(last, hi10)
    setup = bool(dip <= -7 and d["sma50"] and last > d["sma50"]
                 and "hammer" in d["patterns"])
    print(f"SWITCHBACK - TSLA trend dip  last ${last:.2f}  off the 10d high: "
          f"{dip:+.2f}%  SMA50 ${d['sma50']}  hammer: {'hammer' in d['patterns']} "
          f"(hold_style: swing)")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if last >= hi10 or move <= -8.0:
            why = "back at the 10d high" if last >= hi10 else "-8% rule"
            print(f"  CALL: EXIT TSLA @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"SWITCHBACK exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY TSLA @ ${last:.2f} (hammer at the switchback turn)")
        if log: log(BOT, SYM, "buy", last, "SWITCHBACK: -7% trend dip with a hammer")
    else:
        print("  no switchback turn, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
