"""twinsmith.py - TWINSMITH. A handcrafted pairs craftsman.

Peasant work, not a factory clone. Where SCALES (arb_monitor.py)
watches all eight pairs at a 10 point threshold, TWINSMITH forges
only two pairs and demands more before it swings:

  pairs:  SOFI/HOOD and COIN/MSTR, nothing else
  gap:    over 15 points of 5 session relative performance
          (stricter than SCALES' 10)
  timing: the stretched (rich) leg must ALSO print a reversal
          candle on the last daily bar: bearish engulfing,
          shooting star or three black crows. A gap alone is a
          stretched rubber band that can keep stretching; the
          reversal candle is the band starting to snap back.
  bars:   the same earnings disqualifier windows as SCALES
          (arb_monitor.DISQUALIFIERS): both of TWINSMITH's pairs
          are barred through Mon Nov 2, 2026.

Entry logs both legs (buy the cheap leg, short the rich leg) at
the $10k reference size, PAPER ONLY with the news check still
manual, exactly like SCALES. Exits, when the style says so (half
the gap closed, 3 sessions, or 5 points more widening), are a
session decision; TWINSMITH prints the live gap against its open
calls so the human can see it.

Run: python3 handcrafted/twinsmith.py [--log-calls] [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import arb_monitor  # noqa: E402
import scanner  # noqa: E402
import ta  # noqa: E402

BOT = "TWINSMITH"
GAP_MIN = 15.0
MY_PAIRS = [("SOFI", "HOOD"), ("COIN", "MSTR")]
REVERSAL_PATTERNS = {"bearish_engulfing", "shooting_star",
                     "three_black_crows"}


def pct5(closes):
    return scanner.pct(closes[-1], closes[-6])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-calls", action="store_true")
    ap.add_argument("--date", default=None)
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()
    log = None
    if args.log_calls:
        from leaderboard import log_call
        log = log_call

    print(f"TWINSMITH - pairs craftsman (SOFI/HOOD, COIN/MSTR only; "
          f"gap over {GAP_MIN:.0f} pts plus a reversal candle on the "
          f"stretched leg; as of {today})")
    for a, b in MY_PAIRS:
        name = f"{a}/{b}"
        try:
            ca, cb = scanner.fetch_daily(a), scanner.fetch_daily(b)
        except Exception as e:  # noqa: BLE001
            print(f"  {name:<10} data error: {e}")
            continue
        cla = [c["close"] for c in ca]
        clb = [c["close"] for c in cb]
        gap = round(pct5(cla) - pct5(clb), 2)
        rich, cheap = (a, b) if gap > 0 else (b, a)
        rich_candles = ca if rich == a else cb
        pats = REVERSAL_PATTERNS & set(ta.detect_patterns(rich_candles))
        elig = arb_monitor.pair_eligibility(name, gap, today)
        barred = elig.startswith("BARRED")
        print(f"  {name:<10} gap {gap:+.2f} pts  rich leg {rich} "
              f"(reversal candle: {', '.join(sorted(pats)) or 'none'})")
        print(f"             eligibility: {elig}")
        if barred:
            print("             no call: pair is barred")
        elif abs(gap) <= GAP_MIN:
            print(f"             no call: gap under TWINSMITH's "
                  f"{GAP_MIN:.0f} point bar (SCALES flags at 10)")
        elif not pats:
            print("             no call: stretched leg has not printed "
                  "a reversal candle yet")
        else:
            cheap_price = cla[-1] if cheap == a else clb[-1]
            rich_price = cla[-1] if rich == a else clb[-1]
            print(f"             CALL: buy {cheap} @ ${cheap_price:.2f} "
                  f"/ short {rich} @ ${rich_price:.2f} "
                  "(PAPER ONLY, news check still manual)")
            if log:
                note = (f"TWINSMITH pair {name} gap {gap:+.2f} pts, "
                        f"reversal candle on {rich}. PAPER ONLY, "
                        "news unverified")
                log(BOT, cheap, "buy", cheap_price, note)
                log(BOT, rich, "short", rich_price, note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
