"""aftershock.py - AFTERSHOCK. Post earnings gap down drift short, calendar names.

A name that gaps down 4% or more on its print and still closes
under the print day's close one to three sessions later is
usually not done falling: holders exit into every uptick while
estimates get cut. Short the drift, never the print itself.
Cover at +4% against or on a close back above the print day's
open, which means the gap is being reclaimed and the drift is
over. The earnings calendar is SIREN's; the gap is measured off
the actual candles. News unverified beyond the print itself;
a human clears shorts before anyone acts.

Run: python3 handcrafted/aftershock.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner
import earnings_bot

BOT = "AFTERSHOCK"
FLAG = "news unverified beyond the print: AFTERSHOCK cannot check for follow-up news"
GAP_MIN = -4.0
STOP_PCT = 4.0


def watchlist():
    return sorted(earnings_bot.CALENDAR)


def opens():
    from leaderboard import load_calls
    o = {}
    for c in load_calls():
        if c["bot"] != BOT:
            continue
        if c["side"] in ("buy", "short"):
            o.setdefault(c["ticker"], c)
        elif c["side"] == "exit":
            o.pop(c["ticker"], None)
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    op = opens()
    print("AFTERSHOCK - post earnings gap down drift shorts on calendar names")
    today = date.today()
    hits = 0
    for sym in watchlist():
        info = earnings_bot.CALENDAR[sym]
        report_date = info["date"]
        if isinstance(report_date, str):
            report_date = date.fromisoformat(report_date)
        days_since = (today - report_date).days
        if days_since < 0 or days_since > 5:
            # Only the drift window right after a print; covers for
            # open shorts are still evaluated below when in window.
            if sym not in op:
                continue
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(candles) < 10:
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        stamp = report_date.isoformat()
        idx = next((i for i, c in enumerate(candles) if c["date"] == stamp), None)
        if idx is None or idx == 0:
            continue
        print_day = candles[idx]
        gap = scanner.pct(print_day["open"], closes[idx - 1])
        sessions_since = len(candles) - 1 - idx
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or last > print_day["open"]:
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or gap reclaiming)")
                if log: log(BOT, sym, "exit", last, "AFTERSHOCK cover")
            continue
        if (1 <= sessions_since <= 3 and gap <= GAP_MIN
                and last < print_day["close"]):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (gapped {gap:.1f}% on its {stamp} print, still drifting {sessions_since} session(s) later)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"AFTERSHOCK post earnings drift short; {FLAG}")
    if not hits:
        print("  no aftershock drifting today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
