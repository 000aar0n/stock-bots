"""mosaic.py - MOSAIC. A handcrafted NVDA only craftsman.

Peasant work, not a factory clone: MOSAIC trades one name and only
when three timeframes of evidence agree at once (multi timeframe
confluence):

  leg 1  daily trend:        NVDA close above its daily SMA50
  leg 2  5 minute timing:    turning_up on 5 minute candles (WICK)
  leg 3  participation:      daily relative volume over 1.5

All three or no trade. When a leg fails MOSAIC says which one,
because "confluence missing" without the reason is useless.

Exits for its own open paper call: 5 minute falling_knife, or the
Protected Momentum -8 percent rule from the entry price.

Paper only. Calls log to output/calls.jsonl only with --log-calls
(Monday shadow mode); test runs log nothing.

Run: python3 handcrafted/mosaic.py [--log-calls]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scanner  # noqa: E402
import ta  # noqa: E402

BOT = "MOSAIC"
TICKER = "NVDA"
EXIT_PCT = -8.0
RVOL_MIN = 1.5


def my_open_call():
    """MOSAIC's own open paper call on NVDA, or None."""
    from leaderboard import load_calls
    open_call = None
    for c in load_calls():
        if c["bot"] != BOT or c["ticker"] != TICKER:
            continue
        if c["side"] in ("buy", "short"):
            open_call = open_call or c
        elif c["side"] == "exit":
            open_call = None
    return open_call


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-calls", action="store_true",
                    help="log paper calls to output/calls.jsonl "
                         "(shadow mode; off for tests)")
    args = ap.parse_args(argv)

    daily = scanner.fetch_daily(TICKER)
    closes = [c["close"] for c in daily]
    last = closes[-1]
    dta = ta.analyze(daily)
    try:
        intra = scanner.fetch_intraday_candles(TICKER)
        ita = ta.analyze(intra)
    except Exception as e:  # noqa: BLE001
        print(f"MOSAIC - NVDA craftsman: intraday data unavailable ({e}); "
              "confluence cannot be judged, no trade")
        return 0

    leg_trend = dta["sma50"] is not None and last > dta["sma50"]
    leg_timing = bool(ita["turning_up"])
    leg_volume = dta["rel_volume"] is not None and dta["rel_volume"] > RVOL_MIN

    print(f"MOSAIC - NVDA craftsman  last ${last:.2f}  "
          f"({daily[-1]['date']} close, Yahoo data)")
    print(f"  leg 1 daily trend   : close ${last:.2f} vs SMA50 "
          f"${dta['sma50']} -> {'OK' if leg_trend else 'FAIL'}")
    print(f"  leg 2 5m timing     : turning_up on 5 minute candles "
          f"-> {'OK' if leg_timing else 'FAIL'} "
          f"(5m patterns: {', '.join(ita['patterns']) or 'none'})")
    print(f"  leg 3 volume        : daily relative volume "
          f"{dta['rel_volume']} vs {RVOL_MIN} needed "
          f"-> {'OK' if leg_volume else 'FAIL'}")

    open_call = my_open_call()
    if open_call:
        entry = open_call["entry_price"]
        move = scanner.pct(last, entry)
        knife = bool(ita["falling_knife"])
        print(f"  open call: buy @ ${entry:.2f} on {open_call['ts']}, "
              f"now {move:+.2f}%")
        if knife or (move is not None and move <= EXIT_PCT):
            why = ("5 minute falling_knife" if knife
                   else f"{EXIT_PCT:.0f}% rule from entry")
            print(f"  CALL: EXIT NVDA @ ${last:.2f} ({why})")
            if args.log_calls:
                from leaderboard import log_call
                log_call(BOT, TICKER, "exit", last,
                         f"MOSAIC exit: {why}")
        else:
            print("  no exit: neither the 5 minute knife nor the "
                  "-8% rule has tripped")
        return 0

    if leg_trend and leg_timing and leg_volume:
        print(f"  CALL: BUY NVDA @ ${last:.2f} (all three legs agree)")
        if args.log_calls:
            from leaderboard import log_call
            log_call(BOT, TICKER, "buy", last,
                     "MOSAIC confluence: daily close above SMA50, "
                     "5m turning_up, daily rel volume over 1.5")
    else:
        failed = [name for name, ok in
                  (("daily trend", leg_trend), ("5m timing", leg_timing),
                   ("volume", leg_volume)) if not ok]
        print("  no trade, confluence missing: "
              + ", ".join(failed) + " failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
