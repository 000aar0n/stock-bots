"""metronome.py - METRONOME. KO range clock craftsman.

KO ticks between the same walls for months. METRONOME buys the
tick at the bottom wall: close within 2% of the 20 day low with
RSI under 45. It sells the tock: close within 2% of the 20 day
high or RSI over 65, whichever first, or the -8% rule.

Run: python3 handcrafted/metronome.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "METRONOME", "KO"


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
    lo20, hi20 = min(closes[-20:]), max(closes[-20:])
    at_floor = scanner.pct(last, lo20) <= 2
    at_top = scanner.pct(hi20, last) <= 2
    setup = at_floor and d["rsi14"] is not None and d["rsi14"] < 45
    print(f"METRONOME - KO range clock  last ${last:.2f}  20d range "
          f"${lo20:.2f} to ${hi20:.2f}  RSI {d['rsi14']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if at_top or (d["rsi14"] and d["rsi14"] > 65) or move <= -8.0:
            why = "top wall" if at_top else ("RSI over 65" if d["rsi14"] and d["rsi14"] > 65 else "-8% rule")
            print(f"  CALL: EXIT KO @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"METRONOME exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY KO @ ${last:.2f} (bottom wall tick)")
        if log: log(BOT, SYM, "buy", last, "METRONOME: within 2% of 20d low, RSI under 45")
    else:
        print("  mid range, the metronome waits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
