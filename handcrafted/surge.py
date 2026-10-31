"""surge.py - SURGE. AMD MACD flip craftsman (momentum).

One signal, hand tuned: the MACD histogram crossing from negative
to positive WHILE price sits above the SMA20 (a flip inside a
downtrend is noise; a flip in an uptrend is the surge). Exit when
the histogram flips back negative, or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/surge.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "SURGE", "AMD"


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
    _, _, hist_now = ta.macd(closes)
    _, _, hist_prev = ta.macd(closes[:-1])
    flip_up = hist_prev is not None and hist_now is not None and hist_prev <= 0 < hist_now
    flip_dn = hist_prev is not None and hist_now is not None and hist_prev >= 0 > hist_now
    above = d["sma20"] is not None and last > d["sma20"]
    print(f"SURGE - AMD MACD flip  last ${last:.2f}  hist {hist_prev} -> {hist_now}  "
          f"above SMA20: {above}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if flip_dn or move <= -8.0:
            why = "MACD histogram flipped negative" if flip_dn else "-8% rule"
            print(f"  CALL: EXIT AMD @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"SURGE exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif flip_up and above:
        print(f"  CALL: BUY AMD @ ${last:.2f} (histogram flipped up in an uptrend)")
        if log: log(BOT, SYM, "buy", last, "SURGE: MACD hist flip up above SMA20")
    else:
        print("  no flip in an uptrend, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
