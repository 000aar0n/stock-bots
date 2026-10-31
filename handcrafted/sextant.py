"""sextant.py - SEXTANT. A handcrafted regime navigator.

Peasant work, not a factory clone. SEXTANT never trades, never logs
a call, and owns exactly one job: read the weather and say how the
book should be positioned. Each run it derives the regime from the
four index thermometers (SPY, QQQ, IWM, DIA: close vs their 50 day
averages) plus breadth (share of the core 20 above their own SMA50),
then prints ONE line of positioning advice:

  risk on   (at least 3 of 4 indexes above SMA50, breadth 60%+):
            full budget allowed
  risk off  (at most 1 of 4 above, breadth 40% or less):
            arb and defensive only, no new momentum size
  choppy    (everything else):
            half budget, only the highest conviction setups

The verdict is also written to output/sextant.json so JUDGE (and
HERALD) can quote it. JUDGE may quote it later; for now it is
advice, not a gate.

Run: python3 handcrafted/sextant.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scanner  # noqa: E402
import ta  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "output", "sextant.json")
INDEXES = ["SPY", "QQQ", "IWM", "DIA"]


def above_sma50(symbol):
    candles = scanner.fetch_daily(symbol)
    closes = [c["close"] for c in candles]
    s50 = ta.sma(closes, 50)
    return (closes[-1] > s50) if s50 else None


def main():
    thermos = {}
    for t in INDEXES:
        try:
            thermos[t] = above_sma50(t)
        except Exception:  # noqa: BLE001
            thermos[t] = None
    known = [v for v in thermos.values() if v is not None]
    above = sum(1 for v in known if v)

    core_above, core_known = 0, 0
    for t in scanner.CORE_INTRADAY:
        try:
            v = above_sma50(t)
        except Exception:  # noqa: BLE001
            v = None
        if v is not None:
            core_known += 1
            core_above += 1 if v else 0
    breadth = (100.0 * core_above / core_known) if core_known else None

    if known and above >= 3 and breadth is not None and breadth >= 60:
        regime, advice = "risk on", "full budget allowed"
    elif known and above <= 1 and breadth is not None and breadth <= 40:
        regime, advice = ("risk off",
                          "arb and defensive only, no new momentum size")
    else:
        regime, advice = ("choppy",
                          "half budget, highest conviction setups only")

    detail = (f"thermometers {above}/{len(known)} indexes above their "
              f"SMA50, core breadth "
              f"{breadth:.0f}% above theirs" if breadth is not None
              else "breadth unavailable")
    line = f"SEXTANT: {regime.upper()} - {advice} ({detail})"
    print(line)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"generated_at": datetime.now().isoformat(timespec="seconds"),
                   "regime": regime, "advice": advice,
                   "thermometers_above_sma50": thermos,
                   "core_breadth_pct": None if breadth is None
                   else round(breadth, 1),
                   "line": line}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
