"""anvil.py - ANVIL. A handcrafted oversold mega cap mean reversion bot.

Peasant work, not a factory clone. ANVIL hammers only quality names
that have been beaten down too far, and it is picky on purpose. A dip
buy needs ALL THREE:

  1. RSI(14) under 32 (genuinely oversold, stricter than the
     factory DIP strategist's 35)
  2. a bullish reversal candle on the last daily bar: a hammer or a
     bullish engulfing (three white soldiers do NOT count here)
  3. price above the SMA200 (quality only: the long term trend is
     intact, so this is a dip in a good name, not a falling knife
     in a broken one)

Exits for its own open paper calls: RSI back over 55 (the bounce is
done), or the Protected Momentum -8 percent rule from entry.

Watches the core 20 only. Paper only; calls log only with
--log-calls. Near misses (two of three legs) are printed with the
failed leg named, so a human can see what ANVIL is waiting for.

Run: python3 handcrafted/anvil.py [--log-calls]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scanner  # noqa: E402
import ta  # noqa: E402

BOT = "ANVIL"
RSI_MAX = 32.0
RSI_EXIT = 55.0
EXIT_PCT = -8.0
REVERSAL_PATTERNS = {"hammer", "bullish_engulfing"}


def my_open_calls():
    from leaderboard import load_calls
    opens = {}
    for c in load_calls():
        if c["bot"] != BOT:
            continue
        if c["side"] in ("buy", "short"):
            opens.setdefault(c["ticker"], c)
        elif c["side"] == "exit":
            opens.pop(c["ticker"], None)
    return opens


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-calls", action="store_true")
    args = ap.parse_args(argv)
    log = None
    if args.log_calls:
        from leaderboard import log_call
        log = log_call

    opens = my_open_calls()
    print(f"ANVIL - oversold mega cap mean reversion "
          f"(core {len(scanner.CORE_INTRADAY)}; RSI < {RSI_MAX:.0f} + "
          "hammer/engulfing + above SMA200)")

    for sym in scanner.CORE_INTRADAY:
        try:
            candles = scanner.fetch_daily(sym)
        except Exception as e:  # noqa: BLE001
            print(f"  {sym:<6} data error: {e}")
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        d = ta.analyze(candles)

        if sym in opens:
            entry = opens[sym]["entry_price"]
            move = scanner.pct(last, entry)
            if d["rsi14"] is not None and d["rsi14"] > RSI_EXIT:
                print(f"  {sym:<6} CALL: EXIT @ ${last:.2f} "
                      f"(RSI {d['rsi14']} back over {RSI_EXIT:.0f})")
                if log:
                    log(BOT, sym, "exit", last,
                        "ANVIL exit: RSI back over 55, bounce done")
            elif move is not None and move <= EXIT_PCT:
                print(f"  {sym:<6} CALL: EXIT @ ${last:.2f} "
                      f"(-8% rule from ${entry:.2f})")
                if log:
                    log(BOT, sym, "exit", last,
                        "ANVIL exit: -8% rule from entry")
            else:
                print(f"  {sym:<6} holding open call @ ${entry:.2f}, "
                      f"now {move:+.2f}%, RSI {d['rsi14']}")
            continue

        legs = {
            "RSI under 32": d["rsi14"] is not None and d["rsi14"] < RSI_MAX,
            "reversal candle": bool(REVERSAL_PATTERNS & set(d["patterns"])),
            "above SMA200": d["sma200"] is not None and last > d["sma200"],
        }
        passed = sum(legs.values())
        if passed == 3:
            print(f"  {sym:<6} CALL: BUY @ ${last:.2f} "
                  f"(RSI {d['rsi14']}, "
                  f"{', '.join(REVERSAL_PATTERNS & set(d['patterns']))}, "
                  f"above SMA200 ${d['sma200']})")
            if log:
                log(BOT, sym, "buy", last,
                    "ANVIL dip: RSI under 32, hammer/engulfing "
                    "reversal, above SMA200")
        elif passed == 2:
            failed = [k for k, v in legs.items() if not v]
            print(f"  {sym:<6} near miss: waiting on {failed[0]} "
                  f"(RSI {d['rsi14']}, patterns "
                  f"{', '.join(d['patterns']) or 'none'})")
    print("  (names with fewer than two legs passing are not listed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
