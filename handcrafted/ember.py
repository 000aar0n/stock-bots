"""ember.py - EMBER. INTC post shock reversal craftsman.

INTC guided down hard in Oct 2026 and the stock cratered. EMBER
watches the crater for the first ember of a turn: an 8%+ down
day inside the last five sessions, and TODAY the first green
close back over that shock day's HIGH (sellers from the shock
are finally underwater). Entry there. Exit on the -8% rule.
Before that cross, the crater is just a crater.

Run: python3 handcrafted/ember.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "EMBER", "INTC"


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
    shock = None
    for i in range(len(candles) - 5, len(candles) - 1):
        chg = scanner.pct(candles[i]["close"], candles[i - 1]["close"])
        if chg <= -8:
            shock = candles[i]
    green = last > candles[-1]["open"] and last > closes[-2]
    first_cross = bool(shock and green and last > shock["high"]
                       and closes[-2] <= shock["high"])
    print(f"EMBER - INTC shock reversal  last ${last:.2f}  shock day in window: "
          f"{shock is not None}  first green cross over the shock high: {first_cross}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT INTC @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "EMBER exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif first_cross:
        print(f"  CALL: BUY INTC @ ${last:.2f} (first ember over the shock high "
              f"${shock['high']:.2f})")
        if log: log(BOT, SYM, "buy", last, "EMBER: first green close over the shock day high")
    else:
        print("  crater still cold, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
