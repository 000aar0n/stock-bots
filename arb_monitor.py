"""arb_monitor.py - SCALES. Stat arb pair tracker.

SCALES weighs the pairs. For each Protected Momentum pair: the
5 session and 20 session relative performance gap in points,
whether the gap is stretched (10 points or more, the style's entry
threshold), and an eligibility field. Earnings or guidance shocks
disqualify a pair for 2 sessions; those windows are encoded below as
data from the Fri Oct 30 session findings. News checking cannot be
automated keyless reliably, so when the calendar bar is the only
thing standing in the way the field says so, and when a pair is
otherwise clear it still prints "gap qualifies, news check still
manual".

Run: python3 arb_monitor.py [--date YYYY-MM-DD] [--log-calls]
Writes output/arb-latest.json as well as printing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

import scanner

HERE = os.path.dirname(os.path.abspath(__file__))
STRETCH = 10.0

PAIRS = [("NVDA", "AVGO"), ("AMD", "INTC"), ("COIN", "MSTR"), ("SOFI", "HOOD"),
         ("XOM", "CVX"), ("JPM", "BAC"), ("KO", "PEP"), ("WMT", "COST")]

# Disqualifier windows from the Fri Oct 30, 2026 findings: both legs
# of these pairs moved on earnings, so the style bars them for
# 2 sessions from Oct 30 (Fri Oct 30 and Mon Nov 2), eligible again
# Tue Nov 3 if there is no fresh news.
DISQUALIFIERS = {
    "SOFI/HOOD": {"barred_through": "2026-11-02",
                  "reason": "both legs moved on earnings (barred through "
                            "Mon Nov 2, eligible Tue Nov 3 if no fresh news)"},
    "AMD/INTC": {"barred_through": "2026-11-02",
                 "reason": "earnings driven gap, INTC guided down "
                           "(2 sessions from Oct 30)"},
    "COIN/MSTR": {"barred_through": "2026-11-02",
                  "reason": "earnings driven gap, COIN printed soft "
                            "(2 sessions from Oct 30)"},
}


def _pct(closes, n):
    if len(closes) <= n:
        return None
    return (closes[-1] / closes[-1 - n] - 1.0) * 100.0


def pair_eligibility(pair_name, gap5, today):
    """One of: barred / gap qualifies, news check still manual /
    gap under threshold."""
    dq = DISQUALIFIERS.get(pair_name)
    if dq and today.isoformat() <= dq["barred_through"]:
        return f"BARRED through {dq['barred_through']}: {dq['reason']}"
    if gap5 is not None and abs(gap5) >= STRETCH:
        return "gap qualifies, news check still manual"
    return "gap under the 10 point threshold"


def evaluate(today=None):
    today = today or date.today()
    rows = []
    cache = {}
    for a, b in PAIRS:
        row = {"pair": f"{a}/{b}", "legs": [a, b]}
        try:
            for leg in (a, b):
                if leg not in cache:
                    cache[leg] = [c["close"]
                                  for c in scanner.fetch_daily(leg)]
            ga5, gb5 = _pct(cache[a], 5), _pct(cache[b], 5)
            ga20, gb20 = _pct(cache[a], 20), _pct(cache[b], 20)
            gap5 = None if ga5 is None or gb5 is None else round(ga5 - gb5, 2)
            gap20 = None if ga20 is None or gb20 is None else round(ga20 - gb20, 2)
            row.update({
                "gap_5d_points": gap5, "gap_20d_points": gap20,
                "stretched": gap5 is not None and abs(gap5) >= STRETCH,
                "long_leg": (a if (gap5 or 0) < 0 else b),
                "short_leg": (b if (gap5 or 0) < 0 else a),
                "eligibility": pair_eligibility(f"{a}/{b}", gap5, today),
                "last_a": cache[a][-1], "last_b": cache[b][-1],
            })
        except Exception as e:  # noqa: BLE001
            row.update({"gap_5d_points": None, "gap_20d_points": None,
                        "stretched": False, "eligibility": f"data error: {e}"})
        rows.append(row)
    rows.sort(key=lambda r: -(abs(r["gap_5d_points"])
                              if r["gap_5d_points"] is not None else 0))
    return rows


def build_report(rows, today):
    lines = [f"SCALES - stat arb pair tracker (as of {today.isoformat()})"]
    for r in rows:
        g5 = "n/a" if r["gap_5d_points"] is None else f"{r['gap_5d_points']:+.2f}"
        g20 = "n/a" if r["gap_20d_points"] is None else f"{r['gap_20d_points']:+.2f}"
        stretch = "STRETCHED" if r["stretched"] else "not stretched"
        lines.append(f"  {r['pair']:<10} 5d gap {g5:>7} pts   20d gap "
                     f"{g20:>7} pts   {stretch}")
        if r.get("long_leg"):
            lines.append(f"             long {r['long_leg']} / short "
                         f"{r['short_leg']} if entered")
        lines.append(f"             eligibility: {r['eligibility']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--log-calls", action="store_true",
                    help="log SCALES paper calls (both legs) for stretched "
                         "pairs whose eligibility allows it, PAPER ONLY "
                         "when the news check is still manual")
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()
    rows = evaluate(today)
    print(build_report(rows, today))
    out = os.path.join(HERE, "output", "arb-latest.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"as_of": today.isoformat(), "pairs": rows}, f, indent=1)
    if args.log_calls:
        from leaderboard import load_calls, log_call, open_positions
        opens = open_positions(load_calls())
        n = 0
        for r in rows:
            if not r["stretched"]:
                continue
            if r["eligibility"].startswith("BARRED"):
                continue
            a, b = r["legs"]
            note = ("PAPER ONLY, news unverified"
                    if "news check still manual" in r["eligibility"] else "")
            for leg, side in ((r["long_leg"], "buy"), (r["short_leg"], "short")):
                if ("SCALES", leg) in opens:
                    continue
                price = r["last_a"] if leg == a else r["last_b"]
                log_call("SCALES", leg, side, price,
                         f"pair {r['pair']} gap {r['gap_5d_points']:+.2f} pts. "
                         + note)
                n += 1
        print(f"[SCALES] logged {n} paper call(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
