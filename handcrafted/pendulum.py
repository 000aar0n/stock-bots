"""pendulum.py - PENDULUM. QQQ index mean reversion craftsman.

The index always swings back. Entry when QQQ's RSI(14) drops
under 30 AND a hammer prints (sellers exhausted at the swing's
edge). Exit when RSI recovers over 50 (the swing completed) or
the -8% rule. PENDULUM trades the index itself, on paper.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/pendulum.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "PENDULUM", "QQQ"


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
    setup = d["rsi14"] is not None and d["rsi14"] < 30 and "hammer" in d["patterns"]
    print(f"PENDULUM - QQQ swing  last ${last:.2f}  RSI {d['rsi14']} (need under 30)  "
          f"patterns {', '.join(d['patterns']) or 'none'}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["rsi14"] and d["rsi14"] > 50) or move <= -8.0:
            why = f"RSI recovered to {d['rsi14']}" if d["rsi14"] and d["rsi14"] > 50 else "-8% rule"
            print(f"  CALL: EXIT QQQ @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"PENDULUM exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY QQQ @ ${last:.2f} (oversold hammer at the swing edge)")
        if log: log(BOT, SYM, "buy", last, "PENDULUM: RSI under 30 plus hammer")
    else:
        print("  swing has not reached the edge, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
