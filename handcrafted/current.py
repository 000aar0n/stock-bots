"""current.py - CURRENT. TSLA intraday session current craftsman (5m).

CURRENT reads the day's own flow: today's first 5 minute bar is
the session open line. Entry when the latest close sits OVER
that line with intraday relative volume over 1.5 (the current is
flowing up and getting stronger). Exit the moment price falls
back under the session open (current reversed). Pure intraday.

Run: python3 handcrafted/current.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "CURRENT", "TSLA"


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
    if len(bars) < 20:
        print("CURRENT - not enough 5 minute bars, no read")
        return 0
    today = bars[-1]["date"][:10]
    session = [b for b in bars if b["date"].startswith(today)]
    if len(session) < 3:
        session = bars[-20:]
    open_line = session[0]["open"]
    last = bars[-1]["close"]
    intra = ta.analyze(bars)
    flowing = last > open_line and (intra["rel_volume"] or 0) > 1.5
    print(f"CURRENT - TSLA session flow  last ${last:.2f}  session open line "
          f"${open_line:.2f}  5m rel vol {intra['rel_volume']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if last < open_line or move <= -8.0:
            why = "back under the session open" if last < open_line else "-8% rule"
            print(f"  CALL: EXIT TSLA @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"CURRENT exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif flowing:
        print(f"  CALL: BUY TSLA @ ${last:.2f} (current flowing up on volume)")
        if log: log(BOT, SYM, "buy", last, "CURRENT: over the session open on 1.5x intraday volume")
    else:
        print("  current slack, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
