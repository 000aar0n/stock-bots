"""lantern.py - LANTERN. GPN earnings lantern craftsman.

The book HOLDS GPN into its Thu Nov 5 print, so LANTERN's first
job is a warning light: within 2 sessions of GPN's SIREN date it
prints the held exposure context and calls NOTHING (no adding
into a print). After the print, it buys the first GREEN day
(the result is out and buyers stayed). Exit on the -8% rule.

Run: python3 handcrafted/lantern.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta
import earnings_bot

BOT, SYM = "LANTERN", "GPN"


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
    near = status["sessions_until"] is not None and 0 <= status["sessions_until"] <= 2
    past = status["sessions_until"] is not None and status["sessions_until"] < 0
    green = last > closes[-2] and last > candles[-1]["open"]
    print(f"LANTERN - GPN earnings lantern  last ${last:.2f}  prints "
          f"{info['date']} ({info.get('when', 'time unverified')}), sessions until: "
          f"{status['sessions_until']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT GPN @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "LANTERN exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif near:
        print("  lantern lit: inside 2 sessions of the print, LANTERN calls "
              "nothing (the book already holds GPN, exposure is JUDGE's call)")
    elif past and green:
        print(f"  CALL: BUY GPN @ ${last:.2f} (first green day after the print)")
        if log: log(BOT, SYM, "buy", last, "LANTERN: first green day after the print")
    else:
        print("  print not near and not past, lantern dark, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
