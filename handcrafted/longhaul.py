"""longhaul.py - LONGHAUL. NVDA golden trend pullback craftsman. SWING.

The slowest NVDA bot in the city, declared swing. Entry only in
a golden trend (SMA50 over SMA200) on a real pullback (RSI under
45): buy the trend's rest stops, never its sprints. Exit if the
SMA20 crosses under the SMA50 (the haul is over) or the -8%
rule.

Run: python3 handcrafted/longhaul.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "LONGHAUL", "NVDA"


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
    golden = d["sma50"] and d["sma200"] and d["sma50"] > d["sma200"]
    setup = bool(golden and d["rsi14"] is not None and d["rsi14"] < 45)
    print(f"LONGHAUL - NVDA golden trend  last ${last:.2f}  SMA50 over SMA200: "
          f"{bool(golden)}  RSI {d['rsi14']} (pullback under 45) (hold_style: swing)")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        cross_dn = d["sma20"] and d["sma50"] and d["sma20"] < d["sma50"]
        if cross_dn or move <= -8.0:
            why = "SMA20 under SMA50, haul over" if cross_dn else "-8% rule"
            print(f"  CALL: EXIT NVDA @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"LONGHAUL exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY NVDA @ ${last:.2f} (golden trend rest stop)")
        if log: log(BOT, SYM, "buy", last, "LONGHAUL: golden trend, RSI pullback under 45")
    else:
        print("  no rest stop, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
