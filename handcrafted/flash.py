"""flash.py - FLASH. A handcrafted earnings reaction bot.

Peasant work, not a factory clone. FLASH does not predict prints and
never buys before one. It works the reaction, using SIREN's calendar
(earnings_bot.CALENDAR):

  - A name is IN THE WINDOW when its reaction session is today or
    was the prior session. (After close prints react the next
    session; before open prints react the same session.)
  - On the reaction session the name must GAP over 5 percent
    (reaction open vs the close before it).
  - The gap must HOLD: the latest price stays above the gap
    midpoint (halfway between the pre print close and the reaction
    open) and the last ~30 minutes of 5 minute volume is rising
    versus the prior ~30 minutes. Only then: a continuation entry.
  - If the gap fades below the midpoint: NO call. That is the trap
    (RDDT and RBLX gapped and died on weak guides, Thu Oct 29).
    Averaging into a faded gap is how this book bled.

On days with no print in the window FLASH prints its watch list and
the rule and stands down. Paper only; calls log only with
--log-calls.

Run: python3 handcrafted/flash.py [--log-calls] [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import earnings_bot  # noqa: E402
import scanner  # noqa: E402

BOT = "FLASH"
GAP_MIN_PCT = 5.0


def _next_weekday(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _prev_weekday(d):
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def reaction_session(info):
    d = date.fromisoformat(info["date"])
    return _next_weekday(d) if info["when"] == "after close" else d


def in_window(info, today):
    r = reaction_session(info)
    return r == today or r == _prev_weekday(today)


def judge_reaction(sym, info, today):
    """Returns a one line verdict for a name in the window."""
    try:
        candles = scanner.fetch_daily(sym)
    except Exception as e:  # noqa: BLE001
        return f"{sym}: data error ({e}), no call"
    rdate = reaction_session(info).isoformat()
    idx = next((i for i, c in enumerate(candles) if c["date"] >= rdate),
               None)
    if idx is None or idx == 0:
        return (f"{sym}: reaction session {rdate} not in the daily "
                "data yet, no call")
    rc, pc = candles[idx], candles[idx - 1]
    gap_pct = scanner.pct(rc["open"], pc["close"])
    midpoint = pc["close"] + (rc["open"] - pc["close"]) / 2.0
    last = candles[-1]["close"]
    if gap_pct is None or abs(gap_pct) <= GAP_MIN_PCT:
        return (f"{sym}: gap {gap_pct:+.2f}% on the reaction session, "
                f"under the {GAP_MIN_PCT:.0f}% bar, no call")
    direction = "up" if gap_pct > 0 else "down"
    if direction == "down":
        return (f"{sym}: gapped DOWN {gap_pct:+.2f}%, FLASH does not "
                "catch falling knives, no call")
    held = last >= midpoint
    rising_vol = None
    try:
        intra = scanner.fetch_intraday_candles(sym)
        vols = [c["volume"] for c in intra]
        if len(vols) >= 12:
            rising_vol = sum(vols[-6:]) > sum(vols[-12:-6])
    except Exception:  # noqa: BLE001
        rising_vol = None
    if held and rising_vol:
        return (f"{sym}: CALL BUY @ ${last:.2f} - gap {gap_pct:+.2f}% "
                f"held above midpoint ${midpoint:.2f} with rising "
                "volume, continuation")
    if not held:
        return (f"{sym}: gap {gap_pct:+.2f}% FADED below midpoint "
                f"${midpoint:.2f} (last ${last:.2f}) - trap, no call")
    return (f"{sym}: gap {gap_pct:+.2f}% held above midpoint "
            f"${midpoint:.2f} but late volume not rising "
            f"(rising_vol={rising_vol}), no call")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-calls", action="store_true")
    ap.add_argument("--date", default=None)
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()

    print(f"FLASH - earnings reaction craftsman (as of {today})")
    print("  rule: gap over 5% on the reaction session AND hold above "
          "the gap midpoint on rising volume, else no call. "
          "Faded gaps are traps.")
    print("  watch list (from SIREN's calendar):")
    any_window = False
    log = None
    if args.log_calls:
        from leaderboard import log_call
        log = log_call
    for sym, info in sorted(earnings_bot.CALENDAR.items(),
                            key=lambda kv: kv[1]["date"]):
        r = reaction_session(info)
        mark = ""
        if in_window(info, today):
            mark = "  <-- IN THE WINDOW"
            any_window = True
        print(f"    {sym:<5} prints {info['date']} {info['when']}, "
              f"reaction session {r.isoformat()}{mark}")
    if not any_window:
        print("  no names in the reaction window today; FLASH "
              "stands down")
        return 0
    for sym, info in earnings_bot.CALENDAR.items():
        if in_window(info, today):
            verdict = judge_reaction(sym, info, today)
            print("  " + verdict)
            if verdict.startswith(f"{sym}: CALL BUY") and log:
                price = scanner.fetch_daily(sym)[-1]["close"]
                log(BOT, sym, "buy", price,
                    "FLASH continuation: 5%+ gap held above midpoint "
                    "on rising volume")
    return 0


if __name__ == "__main__":
    sys.exit(main())
