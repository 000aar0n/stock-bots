"""gravity.py - GRAVITY. SMR parabolic short craftsman.

SMR goes vertical on nuclear headlines and always comes back.
GRAVITY shorts the vertical itself: five session gain over +25%
with RSI over 78 (no candle required, the angle is the signal).
Exit when RSI cools under 60 (gravity did its work) or at +6%
against, a wider stop because vertical names thrash.

Run: python3 handcrafted/gravity.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "GRAVITY", "SMR"
NEWS_FLAG = "news unverified: GRAVITY cannot check for fresh fundamental news"


def my_short():
    from leaderboard import load_calls
    op = None
    for c in load_calls():
        if c["bot"] == BOT and c["ticker"] == SYM:
            if c["side"] == "short": op = op or c
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
    setup = chg5 > 25 and d["rsi14"] is not None and d["rsi14"] > 78
    print(f"GRAVITY - SMR parabolic short  last ${last:.2f}  5d {chg5:+.2f}% "
          f"(need +25)  RSI {d['rsi14']} (need over 78)")
    op = my_short()
    if op:
        against = scanner.pct(last, op["entry_price"])
        cooled = d["rsi14"] is not None and d["rsi14"] < 60
        if against >= 6.0 or cooled:
            why = f"short {against:+.2f}% underwater" if against >= 6 else f"RSI cooled to {d['rsi14']}"
            print(f"  CALL: EXIT short SMR @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"GRAVITY cover: {why}")
        else:
            print(f"  holding open short @ ${op['entry_price']:.2f}, now {against:+.2f}%")
    elif setup:
        print(f"  CALL: SHORT SMR @ ${last:.2f} (vertical top)  [{NEWS_FLAG}]")
        if log: log(BOT, SYM, "short", last, f"GRAVITY parabolic short; {NEWS_FLAG}")
    else:
        print("  not vertical yet, no short")
    return 0


if __name__ == "__main__":
    sys.exit(main())
