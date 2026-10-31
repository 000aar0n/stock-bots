"""lance.py - LANCE. TSLA momentum thrust craftsman.

Entry only when TSLA is already charging: 5 session gain over +8%,
close above SMA20, daily relative volume over 1.3. LANCE does not
buy the start of a move, it buys proof of one. Exit on two straight
red closes or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/lance.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "LANCE", "TSLA"


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
    chg5 = scanner.pct(closes[-1], closes[-6])
    thrust = chg5 > 8 and last > d["sma20"] and (d["rel_volume"] or 0) > 1.3
    print(f"LANCE - TSLA momentum thrust  last ${last:.2f}  5d {chg5:+.2f}%  "
          f"SMA20 ${d['sma20']}  rel vol {d['rel_volume']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        two_red = closes[-1] < closes[-2] < closes[-3]
        if two_red or move <= -8.0:
            why = "two straight red closes" if two_red else "-8% rule"
            print(f"  CALL: EXIT TSLA @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"LANCE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif thrust:
        print(f"  CALL: BUY TSLA @ ${last:.2f} (thrust confirmed)")
        if log: log(BOT, SYM, "buy", last, "LANCE: 5d +8% thrust above SMA20 on volume")
    else:
        print("  no thrust, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
