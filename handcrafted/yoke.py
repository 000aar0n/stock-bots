"""yoke.py - YOKE. XOM/CVX momentum pair (the anti arb).

SCALES waits for the oil pair to stretch so it can fade it.
YOKE does the opposite trade on the same two names: buy the 20
session relative strength LEADER (strength persists in oil) and
exit only when leadership flips to the other name, or the -8%
rule. One position at a time, yoked to the stronger ox.

Run: python3 handcrafted/yoke.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "YOKE"
PAIR = ("XOM", "CVX")


def rs20(candles):
    closes = [c["close"] for c in candles]
    return scanner.pct(closes[-1], closes[-21])


def my_open():
    from leaderboard import load_calls
    op = None
    for c in load_calls():
        if c["bot"] == BOT and c["ticker"] in PAIR:
            if c["side"] == "buy": op = op or c
            elif c["side"] == "exit": op = None
    return op


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    data = {s: scanner.fetch_daily(s) for s in PAIR}
    rs = {s: rs20(c) for s, c in data.items()}
    leader = max(PAIR, key=lambda s: rs[s])
    print(f"YOKE - oil pair momentum  XOM 20d RS {rs['XOM']:+.2f}%  "
          f"CVX {rs['CVX']:+.2f}%  leader: {leader}")
    op = my_open()
    if op:
        held = op["ticker"]
        last = data[held][-1]["close"]
        move = scanner.pct(last, op["entry_price"])
        if held != leader or move <= -8.0:
            why = f"leadership flipped to {leader}" if held != leader else "-8% rule"
            print(f"  CALL: EXIT {held} @ ${last:.2f} ({why})")
            if log: log(BOT, held, "exit", last, f"YOKE exit: {why}")
        else:
            print(f"  holding the leader {held} @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    else:
        last = data[leader][-1]["close"]
        print(f"  CALL: BUY {leader} @ ${last:.2f} (stronger ox)")
        if log: log(BOT, leader, "buy", last, f"YOKE: 20d RS leader of the oil pair")
    return 0


if __name__ == "__main__":
    sys.exit(main())
