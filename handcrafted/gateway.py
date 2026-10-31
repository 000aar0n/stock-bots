"""gateway.py - GATEWAY. NOW recovery breakout craftsman.

NOW fell out of the sky in 2026 (down over 30% in stretches).
GATEWAY marks the door back in: the FIRST close over the prior
20 day high on relative volume over 1.2 after that drawdown.
Until that close prints, the recovery is a rumor and GATEWAY
stays shut. Exit on the -8% rule.

Paper only; calls log only with --log-calls.
Run: python3 handcrafted/gateway.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT, SYM = "GATEWAY", "NOW"


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
    drawdown = scanner.pct(last, max(closes[-120:]))
    setup = last > hi20 and (d["rel_volume"] or 0) > 1.2
    print(f"GATEWAY - NOW recovery door  last ${last:.2f}  prior 20d high "
          f"${hi20:.2f}  drawdown from 120d high {drawdown:+.2f}%  "
          f"rel vol {d['rel_volume']}")
    op = my_open()
    if op:
        move = scanner.pct(last, op["entry_price"])
        if move <= -8.0:
            print(f"  CALL: EXIT NOW @ ${last:.2f} (-8% rule)")
            if log: log(BOT, SYM, "exit", last, "GATEWAY exit: -8% rule")
        else:
            print(f"  holding open call @ ${op['entry_price']:.2f}, now {move:+.2f}%")
    elif setup:
        print(f"  CALL: BUY NOW @ ${last:.2f} (first close through the door)")
        if log: log(BOT, SYM, "buy", last, "GATEWAY: recovery breakout over 20d high")
    else:
        print("  door still shut, no trade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
