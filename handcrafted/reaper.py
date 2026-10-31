"""reaper.py - REAPER. UUUU exhaustion short craftsman.

Uranium names exhaust in prints, not angles: REAPER shorts when
RSI(14) pushes over 80 AND any bearish candle prints (engulfing,
shooting star or three black crows). Exit when RSI falls back
under 65 (exhaustion spent) or at +6% against.

Run: python3 handcrafted/reaper.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "REAPER", "UUUU"
NEWS_FLAG = "news unverified: REAPER cannot check for fresh fundamental news"


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
    bearish = bool(ta.BEARISH_PATTERNS & set(d["patterns"]))
    setup = d["rsi14"] is not None and d["rsi14"] > 80 and bearish
    print(f"REAPER - UUUU exhaustion short  last ${last:.2f}  RSI {d['rsi14']} "
          f"(need over 80)  bearish candle: {bearish}")
    op = my_short()
    if op:
        against = scanner.pct(last, op["entry_price"])
        spent = d["rsi14"] is not None and d["rsi14"] < 65
        if against >= 6.0 or spent:
            why = f"short {against:+.2f}% underwater" if against >= 6 else f"RSI spent at {d['rsi14']}"
            print(f"  CALL: EXIT short UUUU @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"REAPER cover: {why}")
        else:
            print(f"  holding open short @ ${op['entry_price']:.2f}, now {against:+.2f}%")
    elif setup:
        print(f"  CALL: SHORT UUUU @ ${last:.2f} (exhaustion print)  [{NEWS_FLAG}]")
        if log: log(BOT, SYM, "short", last, f"REAPER exhaustion short; {NEWS_FLAG}")
    else:
        print("  not exhausted, no short")
    return 0


if __name__ == "__main__":
    sys.exit(main())
