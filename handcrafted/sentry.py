"""sentry.py - SENTRY. The held book's exit watchman.

SENTRY never opens anything. It watches ONLY the ten names the
book actually holds (from rules.py's verified fixture) for the
style's own exit trips: two straight red closes, or a -8% fall
from the entries the fixture knows. Where a trip fires it prints
an ALERT and, behind --log-calls, logs the exit call so THE
BOARD can score the watchman's timing. Where the fixture has no
entry price it says so instead of inventing one.

Run: python3 handcrafted/sentry.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta
import rules

BOT = "SENTRY"
# Entry prices as recorded in rules.py's verified fixture (Fri Oct
# 30 account read). Names missing here have no entry on record.
KNOWN_ENTRIES = {"NVDA": 206.45, "AVGO": 327.70, "AMZN": 238.33,
                 "MSTR": 127.39, "GPN": 95.57}


def my_exits():
    """Tickers SENTRY has already called an exit on."""
    from leaderboard import load_calls
    done = set()
    for c in load_calls():
        if c["bot"] == BOT and c["side"] == "exit":
            done.add(c["ticker"])
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    done = my_exits()
    print("SENTRY - exit watch over the held book (never opens)")
    alerts = 0
    from leaderboard import PAPER_CONTEXT
    snapshot = PAPER_CONTEXT.get().get("account_snapshot")
    if not snapshot or snapshot.get("verified") is not True:
        print("  verified current account snapshot unavailable; no fixture fallback")
        return 0
    for sym, position in snapshot["positions"].items():
        shares = position["qty"]
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            print(f"  {sym}: no data, watch continues")
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        two_red = closes[-1] < closes[-2] < closes[-3]
        entry = position.get("entry")
        drop = scanner.pct(last, entry) if entry else None
        tripped = two_red or (drop is not None and drop <= -8.0)
        state = (f"two red closes" if two_red else
                 (f"{drop:+.2f}% vs entry" if drop is not None and drop <= -8
                  else "no trip"))
        if tripped and sym not in done:
            alerts += 1
            print(f"  ALERT: EXIT {sym} @ ${last:.2f} ({shares} shares held, {state})")
            if log: log(BOT, sym, "exit", last, f"SENTRY alert: {state}")
        elif entry is None:
            print(f"  {sym}: last ${last:.2f}, two red: {two_red}, no entry "
                  f"price on record so the -8% trip cannot be judged")
        else:
            print(f"  {sym}: last ${last:.2f}, {state}")
    if not alerts:
        print("  no new exit trips on the watch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
