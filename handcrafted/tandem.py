"""tandem.py - TANDEM. NVDA/AVGO SMA50 tandem craftsman.

The twin semis rarely diverge for long, but when exactly ONE of
NVDA and AVGO sits above its SMA50, TANDEM buys that one (the
twin still standing). Both above or both below: no trade, the
pair is in agreement and other bots work it. Exit when the held
twin loses its SMA50 too, or the -8% rule.

Run: python3 handcrafted/tandem.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "TANDEM"
PAIR = ("NVDA", "AVGO")


def my_open():
    from leaderboard import load_calls
    op = None
    for c in load_calls():
        if c["bot"] == BOT and c["ticker"] in PAIR:
            if c["side"] == "buy": op = op or c
            elif c["side"] == "exit": op = None
    return op


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    state = {}
    for s in PAIR:
        candles = scanner.fetch_daily(s)
        d = ta.analyze(candles)
        state[s] = (candles[-1]["close"], bool(d["sma50"] and candles[-1]["close"] > d["sma50"]))
    standing = [s for s in PAIR if state[s][1]]
    print(f"TANDEM - semi twins  NVDA above SMA50: {state['NVDA'][1]}  "
          f"AVGO above SMA50: {state['AVGO'][1]}")
    op = my_open()
    if op:
        held = op["ticker"]
        last, above = state[held]
        move = scanner.pct(last, op["entry_price"])
        if not above or move <= -8.0:
            why = "held twin lost its SMA50" if not above else "-8% rule"
            print(f"  CALL: EXIT {held} @ ${last:.2f} ({why})")
            if log: log(BOT, held, "exit", last, f"TANDEM exit: {why}")
        else:
            print(f"  holding {held} @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif len(standing) == 1:
        s = standing[0]
        print(f"  CALL: BUY {s} @ ${state[s][0]:.2f} (the twin still standing)")
        if log: log(BOT, s, "buy", state[s][0], "TANDEM: only twin above SMA50")
    else:
        print("  twins in agreement, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
