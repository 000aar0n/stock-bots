"""ignite.py - IGNITE. SMCI breakout craftsman, MACD confirmed.

A new 20 day high alone is not enough for SMCI (it fakes them):
the MACD line must also sit above its signal line. Exit on the
MACD cross down, or the -8% rule. Confirmation over enthusiasm.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/ignite.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "IGNITE", "SMCI"


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
    hi20 = max(closes[-21:-1])
    confirmed = d["macd"] is not None and d["macd_signal"] is not None \
        and d["macd"] > d["macd_signal"]
    setup = last > hi20 and confirmed
    print(f"IGNITE - SMCI confirmed breakout  last ${last:.2f}  prior 20d high "
          f"${hi20:.2f}  MACD over signal: {confirmed}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if not confirmed or move <= -8.0:
            why = "MACD crossed down" if not confirmed else "-8% rule"
            print(f"  CALL: EXIT SMCI @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"IGNITE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY SMCI @ ${last:.2f} (breakout, MACD confirmed)")
        if log: log(BOT, SYM, "buy", last, "IGNITE: 20d high with MACD over signal")
    else:
        print("  unconfirmed or no breakout, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
