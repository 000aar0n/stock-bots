"""channel.py - CHANNEL. GPN band trade craftsman.

Instead of range walls, CHANNEL trades GPN between volatility
bands drawn fresh each run: buy at SMA20 minus one ATR, sell at
SMA20 plus one ATR. The channel moves with the stock's own
weather. Exit also on the -8% rule if the channel itself breaks.

Run: python3 handcrafted/channel.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "CHANNEL", "GPN"


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
    lower = d["sma20"] - d["atr14"] if d["sma20"] and d["atr14"] else None
    upper = d["sma20"] + d["atr14"] if d["sma20"] and d["atr14"] else None
    setup = lower and last <= lower
    print(f"CHANNEL - GPN bands  last ${last:.2f}  lower band ${lower}  "
          f"upper band ${upper}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if (upper and last >= upper) or move <= -8.0:
            why = "upper band reached" if upper and last >= upper else "-8% rule"
            print(f"  CALL: EXIT GPN @ ${last:.2f} ({why})")
            if log: log(BOT, SYM, "exit", last, f"CHANNEL exit: {why}")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY GPN @ ${last:.2f} (lower band touch)")
        if log: log(BOT, SYM, "buy", last, "CHANNEL: at SMA20 minus one ATR")
    else:
        print("  inside the channel, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
