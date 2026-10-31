"""skyline.py - SKYLINE. Visa steady breakout craftsman.

Entry on a new 20 day high that closes green (Visa does not gap,
it strolls upward; the stroll reaching a new high is the signal).
Exit under the EMA20, or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/skyline.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "SKYLINE", "V"


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
    hi20 = max(closes[-21:-1])
    green = last > candles[-1]["open"]
    setup = last > hi20 and green
    print(f"SKYLINE - V breakout  last ${last:.2f}  prior 20d high ${hi20:.2f}  "
          f"green close: {green}  EMA20 ${d['ema20']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["ema20"] and last < d["ema20"]) or move <= -8.0:
            why = "under EMA20" if d["ema20"] and last < d["ema20"] else "-8% rule"
            print(f"  CALL: EXIT V @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"SKYLINE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY V @ ${last:.2f} (green close at a new high)")
        if log: log(BOT, SYM, "buy", last, "SKYLINE: green 20d high")
    else:
        print("  skyline unchanged, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
