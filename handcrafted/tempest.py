"""tempest.py - TEMPEST. COIN high beta momentum craftsman.

COIN only moves in storms, so TEMPEST demands storm conditions:
ATR(14) over 4% of price (real volatility, not drift) AND WICK's
turning_up flag. Exit the moment falling_knife prints (storms
reverse fast), or the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/tempest.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "TEMPEST", "COIN"


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
    atr_pct = 100.0 * d["atr14"] / last if d["atr14"] else None
    storm = atr_pct is not None and atr_pct > 4.0 and d["turning_up"]
    print(f"TEMPEST - COIN storm momentum  last ${last:.2f}  ATR "
          f"{atr_pct:.2f}% of price (need over 4%)  turning_up: {d['turning_up']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if d["falling_knife"] or move <= -8.0:
            why = "falling_knife printed" if d["falling_knife"] else "-8% rule"
            print(f"  CALL: EXIT COIN @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"TEMPEST exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif storm:
        print(f"  CALL: BUY COIN @ ${last:.2f} (storm conditions, turning up)")
        if log: log(BOT, SYM, "buy", last, "TEMPEST: ATR over 4% plus turning_up")
    else:
        print("  no storm, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
