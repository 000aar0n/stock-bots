"""tripwire.py - TRIPWIRE. The speed bot.

TRIPWIRE polls the fastest candle data available (Yahoo intraday
5 minute bars) for the CORE_INTRADAY 20 plus every name with an
open position, and fires loudly when a pattern hits:

  SQUEEZE: intraday move of 3% or more within 15 minutes on
    relative volume of 2x or more
  LATENCY: a fresh latency candidate appears on a watched name
    (scanner's rule: 2% or more over the last ~30 minutes, the sim
    feed is 15 minutes delayed)
  DEFENSIVE TRIP: a HELD name drops 3% or more within 15 minutes

Alerts print with a !!! prefix and append to output/tripwire.jsonl
with timestamps. TRIPWIRE only detects and shouts; it never trades.
The morning budget sheet is pre authorization (see allocator.py),
so when TRIPWIRE fires, JUDGE and HANDS only verify the account
state and the fill. Detection here is seconds to a minute;
execution speed is capped by the HTMW website itself.

Run: python3 tripwire.py --once
     python3 tripwire.py --loop --interval 60   (market hours)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

import rules
import scanner

HERE = os.path.dirname(os.path.abspath(__file__))
ALERTS_PATH = os.path.join(HERE, "output", "tripwire.jsonl")

MOVE_15M_PCT = 3.0
REL_VOL_MIN = 2.0
DEFENSIVE_DROP_PCT = 3.0


def _move_pct(candles, minutes):
    """Percent move over the last `minutes` of intraday candles."""
    if len(candles) < 2:
        return None
    last_ts, last_close = candles[-1]["ts"], candles[-1]["close"]
    target = last_ts - minutes * 60
    earlier = [c for c in candles if c["ts"] <= target]
    ref = earlier[-1]["close"] if earlier else candles[0]["close"]
    return (last_close / ref - 1.0) * 100.0


def _rel_vol_15m(candles):
    """Volume of the last 15 minutes vs the session's typical
    15 minute volume."""
    if len(candles) < 6:
        return None
    vols = [c["volume"] for c in candles]
    windows = [sum(vols[i:i + 3]) for i in range(len(vols) - 2)]
    typical = sum(windows) / len(windows)
    if typical <= 0:
        return None
    return windows[-1] / typical


def check_symbol(sym, held, candles=None):
    """Return a list of alert dicts for one watched name."""
    alerts = []
    try:
        if candles is None:
            candles = scanner.fetch_intraday_candles(sym)
    except Exception as e:  # noqa: BLE001
        return [{"ticker": sym, "kind": "data_error", "detail": str(e)}]
    move15 = _move_pct(candles, 15)
    rel_vol = _rel_vol_15m(candles)
    last = candles[-1]["close"]
    if move15 is not None and abs(move15) >= MOVE_15M_PCT \
            and rel_vol is not None and rel_vol >= REL_VOL_MIN:
        alerts.append({"ticker": sym, "kind": "SQUEEZE",
                       "detail": f"moved {move15:+.2f}% in 15 min on "
                                 f"{rel_vol:.1f}x relative volume, "
                                 f"last ${last:,.2f}"})
    if held and move15 is not None and move15 <= -DEFENSIVE_DROP_PCT:
        alerts.append({"ticker": sym, "kind": "DEFENSIVE_TRIP",
                       "detail": f"HELD name dropped {move15:+.2f}% in "
                                 f"15 min, last ${last:,.2f}"})
    lat = scanner.latency_check(sym, {"last_close": round(last, 2),
                                      "chg_1d_pct": None},
                                candles=candles)
    if lat["candidate"]:
        alerts.append({"ticker": sym, "kind": "LATENCY",
                       "detail": f"fresh latency candidate: "
                                 f"{lat['move_pct']:+.2f}% over "
                                 f"{lat['window']}. {lat['note']}"})
    return alerts


def run_once(watch):
    all_alerts = []
    for sym, held in watch.items():
        for a in check_symbol(sym, held):
            a["ts"] = datetime.now().isoformat(timespec="seconds")
            all_alerts.append(a)
            print(f"!!! TRIPWIRE ALERT [{a['kind']}] {a['ticker']}: "
                  f"{a['detail']}")
    if all_alerts:
        os.makedirs(os.path.dirname(ALERTS_PATH), exist_ok=True)
        with open(ALERTS_PATH, "a") as f:
            for a in all_alerts:
                f.write(json.dumps(a) + "\n")
    return all_alerts


def build_watch(snapshot):
    watch = {sym: False for sym in scanner.CORE_INTRADAY}
    for sym in snapshot["positions"]:
        watch[sym] = True
    return watch


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true",
                    help="check once and exit (testing)")
    ap.add_argument("--loop", action="store_true",
                    help="poll continuously (market hours)")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--snapshot", default=None)
    args = ap.parse_args(argv)
    snapshot = rules.FRI_SNAPSHOT
    if args.snapshot:
        with open(args.snapshot) as f:
            snapshot = json.load(f)
    watch = build_watch(snapshot)
    held = [s for s, h in watch.items() if h]
    print("TRIPWIRE - speed watch")
    print(f"Watching {len(watch)} names: the CORE_INTRADAY 20 plus "
          f"{len(held)} held names ({', '.join(sorted(held))})")
    print(f"Criteria: squeeze = move of {MOVE_15M_PCT:.0f}% or more in "
          f"15 min on relative volume of {REL_VOL_MIN:.0f}x or more; "
          f"latency = fresh latency candidate on a watched name; "
          f"defensive trip = held name down {DEFENSIVE_DROP_PCT:.0f}% "
          "or more in 15 min")
    print("Note: it evaluates the latest session in the data, which "
          "on a closed market is the last completed session.")
    if args.loop:
        print(f"Looping every {args.interval}s. Ctrl C to stop.")
        try:
            while True:
                run_once(watch)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("TRIPWIRE stopped.")
        return 0
    alerts = run_once(watch)
    print(f"TRIPWIRE check complete: {len(alerts)} alert(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
