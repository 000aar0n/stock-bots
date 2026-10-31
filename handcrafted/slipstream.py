"""slipstream.py - SLIPSTREAM. RKLB momentum follower.

RKLB runs in slipstreams behind space news. Entry: five session
gain over +10% with relative volume over 1.2 (drafting behind a
real move). Exit on falling_knife or the -8% rule; SLIPSTREAM
never averages down a broken rocket.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/slipstream.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "SLIPSTREAM", "RKLB"


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
    chg5 = scanner.pct(closes[-1], closes[-6])
    setup = chg5 > 10 and (d["rel_volume"] or 0) > 1.2
    print(f"SLIPSTREAM - RKLB follower  last ${last:.2f}  5d {chg5:+.2f}%  "
          f"rel vol {d['rel_volume']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if d["falling_knife"] or move <= -8.0:
            why = "falling_knife" if d["falling_knife"] else "-8% rule"
            print(f"  CALL: EXIT RKLB @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"SLIPSTREAM exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY RKLB @ ${last:.2f} (slipstream draft confirmed)")
        if log: log(BOT, SYM, "buy", last, "SLIPSTREAM: 5d +10% on volume")
    else:
        print("  no draft, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
