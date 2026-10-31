"""anchor.py - ANCHOR. SOFI dip in trend craftsman.

SOFI swings hard; ANCHOR only buys its dips when the medium trend
holds: RSI under 35, a bullish candle (engulfing, hammer or three
white soldiers), and price above the SMA50 (the anchor chain).
Exit at RSI over 58 or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/anchor.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "ANCHOR", "SOFI"


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
    bullish = bool(ta.BULLISH_PATTERNS & set(d["patterns"]))
    setup = (d["rsi14"] is not None and d["rsi14"] < 35 and bullish
             and d["sma50"] and last > d["sma50"])
    print(f"ANCHOR - SOFI dip  last ${last:.2f}  RSI {d['rsi14']}  bullish candle: "
          f"{bullish}  SMA50 ${d['sma50']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (d["rsi14"] and d["rsi14"] > 58) or move <= -8.0:
            why = f"RSI recovered to {d['rsi14']}" if d["rsi14"] and d["rsi14"] > 58 else "-8% rule"
            print(f"  CALL: EXIT SOFI @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"ANCHOR exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY SOFI @ ${last:.2f} (dip with the anchor chain holding)")
        if log: log(BOT, SYM, "buy", last, "ANCHOR: RSI under 35, bullish candle, above SMA50")
    else:
        print("  no anchored dip, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
