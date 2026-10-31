"""coil.py - COIL. TSLA range coil breakout craftsman.

TSLA compresses before it explodes. COIL measures the coil: the
last five sessions' high to low range under 1.2 times ATR(14)
(genuinely tight for TSLA). Entry on the first close over the
prior five day high. Exit on the -8% rule.

Run: python3 handcrafted/coil.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "COIL", "TSLA"


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
    prior5 = candles[-6:-1]
    coil_range = max(c["high"] for c in prior5) - min(c["low"] for c in prior5)
    hi5 = max(c["high"] for c in prior5)
    tight = d["atr14"] and coil_range < 1.2 * d["atr14"]
    setup = bool(tight and last > hi5)
    print(f"COIL - TSLA compression  last ${last:.2f}  five session range "
          f"${coil_range:.2f} vs 1.2 ATR ${1.2 * (d['atr14'] or 0):.2f}  "
          f"prior 5d high ${hi5:.2f}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT TSLA @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "COIL exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY TSLA @ ${last:.2f} (coil released upward)")
        if log: log(BOT, SYM, "buy", last, "COIL: tight range, break of the 5d high")
    else:
        print("  still coiled or no break, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
