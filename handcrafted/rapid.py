"""rapid.py - RAPID. COIN intraday rapids craftsman (5 minute).

SURGE works AMD's daily MACD; RAPID works COIN's 5 MINUTE MACD:
entry when the intraday histogram flips positive while price
holds over the intraday EMA20 (shooting the rapids, not the
waterfall). Exit on the histogram flip down. Intraday only.

Run: python3 handcrafted/rapid.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "RAPID", "COIN"


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
    if len(bars) < 40:
        print("RAPID - not enough 5 minute bars, no read")
        return 0
    closes = [b["close"] for b in bars]
    intra = ta.analyze(bars)
    _m, _s, hist_now = ta.macd(closes)
    _m, _s, hist_prev = ta.macd(closes[:-1])
    flip_up = hist_prev is not None and hist_now is not None and hist_prev <= 0 < hist_now
    flip_dn = hist_prev is not None and hist_now is not None and hist_prev >= 0 > hist_now
    last = closes[-1]
    over = intra["ema20"] and last > intra["ema20"]
    print(f"RAPID - COIN 5m rapids  last ${last:.2f}  hist {hist_prev} -> {hist_now}  "
          f"over 5m EMA20: {bool(over)}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if flip_dn or move <= -8.0:
            why = "5m histogram flipped down" if flip_dn else "-8% rule"
            print(f"  CALL: EXIT COIN @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"RAPID exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif flip_up and over:
        print(f"  CALL: BUY COIN @ ${last:.2f} (rapids flipping up)")
        if log: log(BOT, SYM, "buy", last, "RAPID: 5m MACD flip up over EMA20")
    else:
        print("  water not moving, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
