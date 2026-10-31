"""beacon.py - BEACON. RIOT print reaction craftsman.

RIOT reports Wed Nov 4 (SIREN's calendar). BEACON ignores RIOT
until that date, then treats the first 6%+ green day on or after
it as the beacon: the print landed and the market blessed it.
Entry on that close. Exit on the -8% rule. Before the date, or
on red reactions, BEACON is dark.

Run: python3 handcrafted/beacon.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta
import earnings_bot

BOT, SYM = "BEACON", "RIOT"


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
    last = closes[-1]
    info = earnings_bot.CALENDAR[SYM]
    status = earnings_bot.print_status(SYM, date.today().isoformat())
    chg1 = scanner.pct(closes[-1], closes[-2])
    lit = (status["sessions_until"] is not None
           and status["sessions_until"] <= 0 and chg1 > 6
           and last > candles[-1]["open"])
    print(f"BEACON - RIOT print beacon  last ${last:.2f}  prints {info['date']}  "
          f"sessions until: {status['sessions_until']}  1d {chg1:+.2f}%")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT RIOT @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "BEACON exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif lit:
        print(f"  CALL: BUY RIOT @ ${last:.2f} (the beacon is lit)")
        if log: log(BOT, SYM, "buy", last, "BEACON: post print +6% green day")
    else:
        print("  beacon dark, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
