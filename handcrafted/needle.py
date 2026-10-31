"""needle.py - NEEDLE. SPY intraday mean reversion craftsman (5 minute).

Threads the needle inside the day: SPY's 5 minute RSI under 25
(intraday washout) plus a 5 minute hammer. Entry there, exit at
5 minute RSI over 55 (the thread pulled through) or a -2% tight
intraday stop. Index, intraday, in and out: NEEDLE is the city's
purest day trader.

Run: python3 handcrafted/needle.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "NEEDLE", "SPY"


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
    bars = scanner.fetch_intraday(SYM)
    if len(bars) < 30:
        print("NEEDLE - not enough 5 minute bars, no read")
        return 0
    intra = ta.analyze(bars)
    last = bars[-1]["close"]
    setup = (intra["rsi14"] is not None and intra["rsi14"] < 25
             and "hammer" in intra["patterns"])
    print(f"NEEDLE - SPY 5m thread  last ${last:.2f}  5m RSI {intra['rsi14']} "
          f"(need under 25)  5m patterns {', '.join(intra['patterns']) or 'none'}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (intra["rsi14"] and intra["rsi14"] > 55) or move <= -2.0:
            why = f"5m RSI threaded to {intra['rsi14']}" if intra["rsi14"] and intra["rsi14"] > 55 else "-2% intraday stop"
            print(f"  CALL: EXIT SPY @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"NEEDLE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY SPY @ ${last:.2f} (intraday washout hammer)")
        if log: log(BOT, SYM, "buy", last, "NEEDLE: 5m RSI under 25 plus hammer")
    else:
        print("  no washout to thread, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
