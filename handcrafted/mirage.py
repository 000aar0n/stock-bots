"""mirage.py - MIRAGE. SNDK failed gap short craftsman.

The mirage is a gap that was never real: SNDK opens gapped up
over 6% over the prior close and CLOSES RED the same day (the
buyers at the open are already trapped). MIRAGE shorts that
close. Exit at +5% against or two green closes.

Run: python3 handcrafted/mirage.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "MIRAGE", "SNDK"
NEWS_FLAG = "news unverified: MIRAGE cannot check for fresh fundamental news"


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
    today, last, d = candles[-1], closes[-1], ta.analyze(candles)
    gap = scanner.pct(today["open"], closes[-2])
    red = last < today["open"]
    setup = gap > 6 and red
    print(f"MIRAGE - SNDK failed gap  last ${last:.2f}  open gap {gap:+.2f}% "
          f"(need over +6)  closed red: {red}")
    op = my_short()
    if op:
        against = scanner.pct(last, op["entry_price"])
        two_green = closes[-1] > closes[-2] > closes[-3]
        if against >= 5.0 or two_green:
            why = f"short {against:+.2f}% underwater" if against >= 5 else "two green closes"
            print(f"  CALL: EXIT short SNDK @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"MIRAGE cover: {why}")
        else:
            print(f"  holding open short @ ${op['entry_price']:.2f}, now {against:+.2f}%")
    elif setup:
        print(f"  CALL: SHORT SNDK @ ${last:.2f} (the gap was a mirage)  [{NEWS_FLAG}]")
        if log: log(BOT, SYM, "short", last, f"MIRAGE failed gap short; {NEWS_FLAG}")
    else:
        print("  gap held or no gap, no short")
    return 0


if __name__ == "__main__":
    sys.exit(main())
