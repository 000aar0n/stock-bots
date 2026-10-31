"""pressure.py - PRESSURE. NVDA intraday (5 minute) squeeze craftsman.

The only daily-free squeeze in the city: PRESSURE reads NVDA's
5 minute bars. When the last 12 bars (one hour) trade inside
0.6% total range, pressure is built; the entry fires on the
first close that breaks that hour's high. Exit when price falls
back inside the squeezed range (the break failed) or at -3%
intraday. On weekends it reads Friday's final bars and says so.

Run: python3 handcrafted/pressure.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "PRESSURE", "NVDA"


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
    if len(bars) < 14:
        print("PRESSURE - not enough 5 minute bars, no read")
        return 0
    window = bars[-13:-1]
    hi = max(b["high"] for b in window)
    lo = min(b["low"] for b in window)
    last_bar = bars[-1]
    last = last_bar["close"]
    width = scanner.pct(hi, lo)
    squeezed = width < 0.6
    broke = last > hi
    print(f"PRESSURE - NVDA 5m squeeze  last ${last:.2f}  prior hour range "
          f"${lo:.2f} to ${hi:.2f} ({width:.2f}%, squeezed: {squeezed})")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if last <= hi or move <= -3.0:
            why = "fell back inside the range" if last <= hi else "-3% intraday stop"
            print(f"  CALL: EXIT NVDA @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"PRESSURE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif squeezed and broke:
        print(f"  CALL: BUY NVDA @ ${last:.2f} (hour squeeze broke up)")
        if log: log(BOT, SYM, "buy", last, "PRESSURE: 12 bar squeeze break")
    else:
        print("  pressure building or no break, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
