"""blaze.py - BLAZE. MSTR ignition day craftsman (momentum).

MSTR moves in single day fires. BLAZE enters on the ignition day
itself: one session gain over +3% with daily relative volume over
1.5 (the crowd arrived). It does not wait for a five session trend.
Exit on a red close under the EMA20, or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/blaze.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "BLAZE", "MSTR"


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
    last, prev, d = closes[-1], closes[-2], ta.analyze(candles)
    chg1 = scanner.pct(last, prev)
    ignition = chg1 > 3 and (d["rel_volume"] or 0) > 1.5
    print(f"BLAZE - MSTR ignition  last ${last:.2f}  1d {chg1:+.2f}%  "
          f"rel vol {d['rel_volume']} (need over 1.5)")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        red_under = last < prev and d["ema20"] and last < d["ema20"]
        if red_under or move <= -8.0:
            why = "red close under EMA20" if red_under else "-8% rule"
            print(f"  CALL: EXIT MSTR @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"BLAZE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif ignition:
        print(f"  CALL: BUY MSTR @ ${last:.2f} (ignition day on volume)")
        if log: log(BOT, SYM, "buy", last, "BLAZE: +3% day on 1.5x volume")
    else:
        print("  no ignition, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
