"""breach.py - BREACH. MRVL clean breakout craftsman.

Entry on a new 20 day high with daily relative volume over 1.5
(a breach with an army behind it). Exit when price closes under
the prior 10 day low (the breach failed and the wall fell back),
or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/breach.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "BREACH", "MRVL"


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
    hi20, lo10 = max(closes[-21:-1]), min(closes[-11:-1])
    setup = last > hi20 and (d["rel_volume"] or 0) > 1.5
    print(f"BREACH - MRVL breakout  last ${last:.2f}  prior 20d high ${hi20:.2f}  "
          f"rel vol {d['rel_volume']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if last < lo10 or move <= -8.0:
            why = "closed under the prior 10d low, breach failed" if last < lo10 else "-8% rule"
            print(f"  CALL: EXIT MRVL @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"BREACH exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY MRVL @ ${last:.2f} (20d high on 1.5x volume)")
        if log: log(BOT, SYM, "buy", last, "BREACH: new 20d high on volume")
    else:
        print("  wall still standing, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
