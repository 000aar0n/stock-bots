"""scalpel.py - SCALPEL. NVDA intraday scalpel craftsman (5 minute).

A precise cut, gated twice: the DAILY trend must be up (close
over daily SMA50) and the 5 MINUTE tape must be turning_up
(WICK's bounce on intraday bars). Entry on that agreement. Exit
on a 5 minute falling_knife (the cut went wrong) or the close:
SCALPEL never holds overnight by design.

Run: python3 handcrafted/scalpel.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "SCALPEL", "NVDA"


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
    daily = scanner.fetch_daily(SYM)
    dd = ta.analyze(daily)
    gate = bool(dd["sma50"] and daily[-1]["close"] > dd["sma50"])
    bars = scanner.fetch_intraday(SYM)
    if len(bars) < 30:
        print("SCALPEL - not enough 5 minute bars, no read")
        return 0
    intra = ta.analyze(bars)
    last = bars[-1]["close"]
    print(f"SCALPEL - NVDA 5m  last ${last:.2f}  daily gate (over SMA50): {gate}  "
          f"5m turning_up: {intra['turning_up']}  5m patterns "
          f"{', '.join(intra['patterns']) or 'none'}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if intra["falling_knife"] or move <= -8.0:
            why = "5 minute falling_knife" if intra["falling_knife"] else "-8% rule"
            print(f"  CALL: EXIT NVDA @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"SCALPEL exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif gate and intra["turning_up"]:
        print(f"  CALL: BUY NVDA @ ${last:.2f} (daily gate open, 5m turning up)")
        if log: log(BOT, SYM, "buy", last, "SCALPEL: daily uptrend plus 5m turning_up")
    else:
        print("  gates disagree, no cut")
    return 0


if __name__ == "__main__":
    sys.exit(main())
