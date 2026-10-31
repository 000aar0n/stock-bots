"""echo.py - ECHO. RIOT spike echo short craftsman.

RIOT spikes on crypto headlines, then echoes back down. ECHO
needs the two day shape: yesterday up over +10%, today a red
day with a bearish engulfing (the echo starting). Short entry
on today's close. Exit at +5% against or two green closes.

Run: python3 handcrafted/echo.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "ECHO", "RIOT"
NEWS_FLAG = "news unverified: ECHO cannot check for fresh fundamental news"


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
    spike = scanner.pct(closes[-2], closes[-3]) > 10
    echoing = last < closes[-2] and "bearish_engulfing" in d["patterns"]
    setup = spike and echoing
    print(f"ECHO - RIOT spike echo  last ${last:.2f}  prior day spike over +10%: "
          f"{spike}  bearish engulfing today: {'bearish_engulfing' in d['patterns']}")
    op = my_short()
    if op:
        against = scanner.pct(last, op["entry_price"])
        two_green = closes[-1] > closes[-2] > closes[-3]
        if against >= 5.0 or two_green:
            why = f"short {against:+.2f}% underwater" if against >= 5 else "two green closes"
            print(f"  CALL: EXIT short RIOT @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"ECHO cover: {why}")
        else:
            print(f"  holding open short @ ${op['entry_price']:.2f}, now {against:+.2f}%")
    elif setup:
        print(f"  CALL: SHORT RIOT @ ${last:.2f} (echo starting)  [{NEWS_FLAG}]")
        if log: log(BOT, SYM, "short", last, f"ECHO spike echo short; {NEWS_FLAG}")
    else:
        print("  no echo shape, no short")
    return 0


if __name__ == "__main__":
    sys.exit(main())
