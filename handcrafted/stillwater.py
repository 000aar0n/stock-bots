"""stillwater.py - STILLWATER. Visa dead calm anticipation craftsman.

Most bots wait for the move. STILLWATER enters BEFORE it, in the
calm: Visa's ten session range compressed under two ATR, RSI in
the neutral 40 to 50 pocket, and a green day (the first ripple).
Exit at +5% (the move paid) or -5% (the calm was a trap, tighter
than the standard stop because the thesis was precision).

Run: python3 handcrafted/stillwater.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "STILLWATER", "V"


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
    range10 = max(c["high"] for c in candles[-10:]) - min(c["low"] for c in candles[-10:])
    calm = d["atr14"] and range10 < 2 * d["atr14"]
    pocket = d["rsi14"] is not None and 40 <= d["rsi14"] <= 50
    green = last > candles[-1]["open"]
    setup = bool(calm and pocket and green)
    print(f"STILLWATER - V dead calm  last ${last:.2f}  10d range ${range10:.2f} "
          f"vs 2 ATR ${2 * (d['atr14'] or 0):.2f}  RSI {d['rsi14']}  green: {green}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move >= 5.0 or move <= -5.0:
            why = "the move paid at +5%" if move >= 5 else "calm was a trap: -5% stop"
            print(f"  CALL: EXIT V @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"STILLWATER exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY V @ ${last:.2f} (first ripple in dead calm)")
        if log: log(BOT, SYM, "buy", last, "STILLWATER: compressed range, neutral RSI, green day")
    else:
        print("  water not still enough, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
