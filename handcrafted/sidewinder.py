"""sidewinder.py - SIDEWINDER. OKLO rollover short craftsman.

SIDEWINDER does not short the top; it shorts the ROLLOVER after
the top. Condition: five sessions ago OKLO was up over 15% on
its own prior five (the run already happened), and today price
crosses UNDER the SMA20 (the rollover confirming). Short entry
there. Exit on a close back over the SMA20 or +5% against.

Run: python3 handcrafted/sidewinder.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "SIDEWINDER", "OKLO"
NEWS_FLAG = "news unverified: SIDEWINDER cannot check for fresh fundamental news"


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
    old_run = scanner.pct(closes[-6], closes[-11]) > 15
    sma20_prev = ta.sma(closes[:-1], 20)
    crossing = (sma20_prev and closes[-2] >= sma20_prev
                and d["sma20"] and last < d["sma20"])
    setup = bool(old_run and crossing)
    print(f"SIDEWINDER - OKLO rollover  last ${last:.2f}  run five sessions ago "
          f"over +15%: {old_run}  crossing under SMA20 today: {bool(crossing)}")
    op = my_short()
    if op:
        against = scanner.pct(last, op["entry_price"])
        back_over = d["sma20"] and last > d["sma20"]
        if against >= 5.0 or back_over:
            why = f"short {against:+.2f}% underwater" if against >= 5 else "back over SMA20, rollover failed"
            print(f"  CALL: EXIT short OKLO @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"SIDEWINDER cover: {why}")
        else:
            print(f"  holding open short @ ${op['entry_price']:.2f}, now {against:+.2f}%")
    elif setup:
        print(f"  CALL: SHORT OKLO @ ${last:.2f} (rollover confirmed)  [{NEWS_FLAG}]")
        if log: log(BOT, SYM, "short", last, f"SIDEWINDER rollover short; {NEWS_FLAG}")
    else:
        print("  no rollover, no short")
    return 0


if __name__ == "__main__":
    sys.exit(main())
