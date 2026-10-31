"""paladin.py - PALADIN. AAPL trend cross craftsman (momentum).

Hand tuned, one job: ride AAPL's medium trend. Entry when the
EMA20 crosses ABOVE the SMA50 (the trend just turned up, not while
it is already extended). Exit when EMA20 crosses back below SMA50,
or the -8% rule. No cross, no trade: PALADIN does not chase.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/paladin.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "PALADIN", "AAPL"


def ema_series(values, period):
    out, k = [], 2.0 / (period + 1)
    e = None
    for v in values:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def my_open():
    from leaderboard import load_calls
    op = None
    for c in load_calls():
        if c["bot"] == BOT and c["ticker"] == SYM:
            if c["side"] == "buy":
                op = op or c
            elif c["side"] == "exit":
                op = None
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
    ema = ema_series(closes, 20)
    sma50_now = ta.sma(closes, 50)
    sma50_prev = ta.sma(closes[:-1], 50)
    cross_up = ema[-2] <= sma50_prev and ema[-1] > sma50_now
    cross_dn = ema[-2] >= sma50_prev and ema[-1] < sma50_now
    print(f"PALADIN - AAPL trend cross  last ${last:.2f}  EMA20 ${ema[-1]:.2f} "
          f"vs SMA50 ${sma50_now:.2f}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if cross_dn or move <= -8.0:
            why = "EMA20 crossed back below SMA50" if cross_dn else "-8% rule"
            print(f"  CALL: EXIT AAPL @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"PALADIN exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif cross_up:
        print(f"  CALL: BUY AAPL @ ${last:.2f} (EMA20 just crossed above SMA50)")
        if log: log(BOT, SYM, "buy", last, "PALADIN: EMA20/SMA50 cross up")
    else:
        print("  no cross today, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
