"""earnings_bot.py - SIREN. Earnings calendar warnings for the book.

SIREN warns before prints. The calendar is hardcoded data (add a
name = add one dict entry) because keyless earnings calendars are
unreliable. For each name: days and sessions until the print, what
we hold, position exposure versus the $15k earnings cap from the
Protected Momentum style, and a flag when a HELD name is inside
2 sessions of its print.

Run: python3 earnings_bot.py [--date YYYY-MM-DD]
Writes output/earnings-latest.json as well as printing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
EARNINGS_CAP = 15_000.0

# Add a name = add one entry. held_qty / entry describe the book.
CALENDAR = {
    "PLTR": {"date": "2026-11-02", "when": "after close", "held_qty": 0,
             "entry": None,
             "bar": "revenue about $2.18B, EPS about $0.41 to $0.42",
             "note": "not held; reaction play only, no pre print buy"},
    "RIOT": {"date": "2026-11-04", "when": "time not specified",
             "held_qty": 0, "entry": None,
             "bar": "consensus EPS about -$0.24 to -$0.34, revenue about $160M",
             "note": "not held; the $15k earnings cap applies if bought"},
    "GPN": {"date": "2026-11-05", "when": "before open", "held_qty": 100,
            "entry": 95.57,
            "bar": "EPS about $3.57 to $3.58, revenue about $3.18B",
            "note": "HELD 100 shares at $95.57, about $9.6k, under the cap"},
}


def sessions_until(today, target):
    """Trading sessions between today (exclusive) and target
    (inclusive), approximated as weekdays."""
    if target <= today:
        return 0
    n, d = 0, today
    while d < target:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def print_status(symbol, as_of):
    """Compatibility read for reaction bots, with signed session distance.
    Calendar entries are manually maintained; no new event is inferred.
    """
    event = CALENDAR.get(symbol)
    if not event:
        return {"sessions_until": None, "verified": False}
    today = date.fromisoformat(as_of)
    target = date.fromisoformat(event["date"])
    distance = sessions_until(today,target) if target >= today else -sessions_until(target,today)
    return {"sessions_until": distance, "date": event["date"],
            "verified": bool(event.get("verified", False))}


def load_prices():
    path = os.path.join(HERE, "output", "scan-latest.json")
    try:
        with open(path) as f:
            scan = json.load(f)
        return {s: v["last_close"] for s, v in scan.get("symbols", {}).items()}
    except Exception:  # noqa: BLE001
        return {}


def evaluate(today=None):
    today = today or date.today()
    prices = load_prices()
    rows = []
    for sym, info in sorted(CALENDAR.items(), key=lambda kv: kv[1]["date"]):
        d = date.fromisoformat(info["date"])
        qty = info["held_qty"]
        price = prices.get(sym, info["entry"])
        exposure = round(qty * price, 2) if qty and price else 0.0
        sess = sessions_until(today, d)
        rows.append({
            "ticker": sym, "date": info["date"], "when": info["when"],
            "days_until": (d - today).days, "sessions_until": sess,
            "held_qty": qty, "entry": info["entry"], "price_used": price,
            "exposure": exposure, "cap": EARNINGS_CAP,
            "over_cap": exposure > EARNINGS_CAP,
            "bar": info["bar"], "note": info["note"],
            "flag": bool(qty and sess <= 2),
        })
    return rows


def build_report(rows, today):
    lines = [f"SIREN - earnings warnings (as of {today.isoformat()})"]
    for r in rows:
        held = (f"HELD {r['held_qty']} shares, exposure ${r['exposure']:,.0f} "
                f"of the ${r['cap']:,.0f} cap" if r["held_qty"]
                else "not held")
        lines.append(f"  {r['ticker']:<5} {r['date']} {r['when']}: "
                     f"{r['days_until']} day(s), {r['sessions_until']} "
                     f"session(s) away - {held}")
        lines.append(f"        bar: {r['bar']}. {r['note']}")
        if r["over_cap"]:
            lines.append(f"        WARNING: exposure is OVER the "
                         f"${r['cap']:,.0f} earnings cap")
        if r["flag"]:
            lines.append("        FLAG: held name inside 2 sessions of "
                         "its print - deliberate choice or trim, per the style")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None,
                    help="evaluate as of YYYY-MM-DD (default today)")
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()
    rows = evaluate(today)
    print(build_report(rows, today))
    out = os.path.join(HERE, "output", "earnings-latest.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"as_of": today.isoformat(), "rows": rows}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
