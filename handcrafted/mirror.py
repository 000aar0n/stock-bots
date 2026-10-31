"""mirror.py - MIRROR. A handcrafted short side craftsman.

Peasant work, not a factory clone. MIRROR is the city's short
seller, and it only shorts THE FADE, the exact shape that made the
BRAI trade work:

  1. the name is up over 15 percent in 5 sessions (a vertical,
     stretched move)
  2. a bearish reversal candle prints on the last daily bar:
     bearish engulfing or shooting star
  3. volume is rising while it rolls over (daily relative
     volume 1.2 or more, hand tuned)

Plus one honest condition this code CANNOT check: the run must not
be backed by fresh fundamental news. Keyless news checking is
unreliable, so every MIRROR call is logged with the flag
"news unverified" and a human must clear the news before anyone
acts on it. If a name ran on real news, the fade is a bad short.

Exits for its own open shorts: the name rises 5 percent against
the short (stop), or two straight green closes (the fade is over).

Calls are logged with side "short"; leaderboard.py scores shorts
natively (its _ref_pnl handles side "short"). Paper only; calls
log only with --log-calls.

Run: python3 handcrafted/mirror.py [--log-calls]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scanner  # noqa: E402
import ta  # noqa: E402

BOT = "MIRROR"
RUN_MIN_PCT = 15.0
RVOL_MIN = 1.2
STOP_PCT = 5.0
FADE_PATTERNS = {"bearish_engulfing", "shooting_star"}
NEWS_FLAG = ("news unverified: MIRROR cannot check for fresh "
             "fundamental news; a human must clear it before acting")


def my_open_shorts():
    from leaderboard import load_calls
    opens = {}
    for c in load_calls():
        if c["bot"] != BOT:
            continue
        if c["side"] == "short":
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

    opens = my_open_shorts()
    tickers = []
    for group in scanner.UNIVERSE.values():
        for t in group:
            if t not in tickers:
                tickers.append(t)
    print(f"MIRROR - short side craftsman (fade pattern only: up "
          f"{RUN_MIN_PCT:.0f}%+ in 5 sessions, bearish engulfing or "
          f"shooting star, rel volume >= {RVOL_MIN})")
    print(f"  standing flag on every call: {NEWS_FLAG}")

    hits, checked, errors = [], 0, 0
    for sym in tickers:
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        checked += 1
        closes = [c["close"] for c in candles]
        last = closes[-1]
        d = ta.analyze(candles)

        if sym in opens:
            entry = opens[sym]["entry_price"]
            against = scanner.pct(last, entry)  # up = against a short
            two_green = (len(candles) >= 2
                         and all(c["close"] > c["open"]
                                 for c in candles[-2:]))
            if against is not None and against >= STOP_PCT:
                print(f"  {sym:<6} CALL: EXIT short @ ${last:.2f} "
                      f"(stop: +{against:.2f}% against the short)")
                if log:
                    log(BOT, sym, "exit", last,
                        "MIRROR stop: short moved 5% against")
            elif two_green:
                print(f"  {sym:<6} CALL: EXIT short @ ${last:.2f} "
                      "(two green closes, the fade is over)")
                if log:
                    log(BOT, sym, "exit", last,
                        "MIRROR exit: two green closes")
            else:
                print(f"  {sym:<6} short open @ ${entry:.2f}, "
                      f"now {against:+.2f}% vs the short")
            continue

        chg5 = scanner.pct(closes[-1], closes[-6])
        pats = FADE_PATTERNS & set(d["patterns"])
        if (chg5 is not None and chg5 >= RUN_MIN_PCT and pats
                and d["rel_volume"] is not None
                and d["rel_volume"] >= RVOL_MIN):
            hits.append(sym)
            print(f"  {sym:<6} CALL: SHORT @ ${last:.2f} "
                  f"(+{chg5:.2f}% in 5 sessions, "
                  f"{', '.join(sorted(pats))}, rel volume "
                  f"{d['rel_volume']}) [{NEWS_FLAG}]")
            if log:
                log(BOT, sym, "short", last,
                    f"MIRROR fade: +{chg5:.2f}% in 5 sessions, "
                    f"{', '.join(sorted(pats))}, rising volume. "
                    + NEWS_FLAG)
    print(f"  scanned {checked} names ({errors} fetch errors): "
          f"{len(hits)} fade setup(s)"
          + (": " + ", ".join(hits) if hits else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
