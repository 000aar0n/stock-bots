"""allocator.py - TREASURER and LEDGER. The budget sheet, dual sign off.

TREASURER proposes the budget from the portfolio snapshot plus
JUDGE's candidate list: the reserve to hold back ($10k in buy mode,
$15k floor normally), the total deployable, and a per name split
across approved candidates weighted by signal strength, respecting
the 25 percent single name cap and the $15k earnings cap for names
inside their earnings window (SIREN's calendar).

LEDGER then verifies the sheet against the raw snapshot numbers
with its own arithmetic. If they agree, one BUDGET SHEET prints. If
they disagree, both numbers print, the sheet is flagged
DISAGREEMENT, and it fails closed: deployable is zeroed, no
exceptions.

TWO BOOK BUDGET (Aaron, Sat Oct 31, 2026): the deployable figure is
split 50/50 into two envelopes. The LONG HOLD envelope funds swing
positions (hold_style "swing"; stat arb pairs live here, they are
exempt from the same day flat rule). The DAY TRADING envelope funds
intraday positions (hold_style "intraday", the city default).
Neither envelope may exceed 50 percent of deployable, unspent
envelope money stays in reserve and does NOT spill into the other
envelope, and every budgeted line is labeled with its book (LONG or
DAY). The DAY TRADING book is fully liquid by end of day, every
day; flattening it is the close session's job, and the sheet prints
that standing rule on every run. TREASURER proposes the split and
LEDGER verifies it independently, inside the same fail closed
agreement as the totals.

JUDGE consumes this sheet format via output/budget.json
(fields: reserve, deployable, per_name, caps).

SPEED WIRING: the morning budget sheet is PRE AUTHORIZATION.
TREASURER and LEDGER settle the budget before the open, so when
TRIPWIRE fires during the day, JUDGE and HANDS do not wait on
budgeting - they only verify the account state and the fill.
Thorough on account numbers, fast on market detection.

EV WIRING: TREASURER funds single name candidates top down by
ODDS expected value score until the deployable runs out, and any
candidate with a negative EV score is skipped no matter how loud
its bot is. Pair candidates (no ODDS score) split what remains by
gap strength, as before.

Run: python3 allocator.py [--buy-mode] [--day-change-pct -9.3]
     [--sample-candidates]  (test mode: candidate pool built from
     scanner output instead of JUDGE's approved list)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import earnings_bot
import odds
import rules

HERE = os.path.dirname(os.path.abspath(__file__))
RESERVE_NORMAL = 15_000.0
RESERVE_BUY_MODE = 10_000.0
SINGLE_NAME_CAP = 0.25
EARNINGS_CAP = 15_000.0
EARNINGS_WINDOW_SESSIONS = 2


def book_for(kind, hold_style):
    """Which book a candidate belongs to. Pairs are swing by city
    convention (stat arb is exempt from the same day flat rule), and
    any candidate carrying hold_style "swing" is a long hold.
    Everything else is intraday by default, the city default."""
    if kind == "pair" or hold_style == "swing":
        return "LONG"
    return "DAY"


def envelope_caps(deployable):
    """The 50/50 split of deployable into the two book envelopes.
    The two caps always sum to exactly deployable."""
    long_cap = round(deployable / 2.0, 2)
    return {"LONG": long_cap, "DAY": round(deployable - long_cap, 2)}


def envelope_totals(per_name, caps):
    allocated = {"LONG": 0.0, "DAY": 0.0}
    for p in per_name.values():
        allocated[p["book"]] += p["budget"]
    return {"LONG": {"hold_style": "swing", "cap": caps["LONG"],
                     "allocated": round(allocated["LONG"], 2)},
            "DAY": {"hold_style": "intraday", "cap": caps["DAY"],
                    "allocated": round(allocated["DAY"], 2)}}


# ---------------------------------------------------------------- TREASURER

def treasurer_propose(snapshot, decisions, earnings_rows, buy_mode,
                      odds_rows=None, extra_candidates=None):
    reserve = RESERVE_BUY_MODE if buy_mode else RESERVE_NORMAL
    bp = snapshot.get("buying_power") or 0.0
    deployable = max(0.0, bp - reserve)
    value = snapshot["portfolio_value"]
    existing = {r["symbol"]: abs(r.get("market_value") or 0) for r in decisions.get("positions", [])}
    earn = {r["ticker"]: r for r in earnings_rows}
    ev_map = {r["ticker"]: r["ev_score"] for r in (odds_rows or [])}
    caps = envelope_caps(deployable)

    singles = []
    raw_cands = [c for c in decisions.get("buy_candidates", [])
                 if not c["blocked"]]
    if extra_candidates:
        raw_cands = extra_candidates
    for c in raw_cands:
        cap = SINGLE_NAME_CAP * value
        e = earn.get(c["symbol"])
        if e and e["sessions_until"] <= EARNINGS_WINDOW_SESSIONS:
            cap = min(cap, EARNINGS_CAP)
        hold = c.get("hold_style", "intraday")
        singles.append({"name": c["symbol"], "kind": "momentum",
                        "hold_style": hold,
                        "book": book_for("momentum", hold),
                        "cap": max(0.0, cap-existing.get(c["symbol"],0)), "ev": ev_map.get(c["symbol"])})
    pairs = []
    for a in decisions.get("arb_candidates", []):
        if a["blocked"] or not a.get("verified_eligibility", False):
            continue
        pairs.append({"name": a["pair"], "kind": "pair",
                      "hold_style": "swing", "book": "LONG",
                      "strength": abs(a["gap_points"]),
                      "cap": SINGLE_NAME_CAP * value})

    per_name = {}
    skipped = []
    remaining = dict(caps)
    # Singles first, top down by EV, each funded only from its own
    # book's envelope. Negative EV is skipped outright. An envelope
    # that runs dry does not borrow from the other book.
    for c in sorted(singles, key=lambda x: -(x["ev"] or 0.0)):
        if c["ev"] is None or c["ev"] <= 0:
            skipped.append(f"{c['name']}: negative EV score "
                           f"{c['ev']} (uncalibrated ODDS score), skipped")
            continue
        budget = min(c["cap"], remaining[c["book"]])
        per_name[c["name"]] = {"budget": round(budget, 2),
                               "cap": round(c["cap"], 2),
                               "kind": c["kind"], "ev": c["ev"],
                               "book": c["book"],
                               "hold_style": c["hold_style"]}
        remaining[c["book"]] -= budget
    # Pairs split what is left of the LONG envelope, weighted by
    # gap strength.
    total_strength = sum(c["strength"] for c in pairs)
    for c in pairs:
        raw = (remaining["LONG"] * c["strength"] / total_strength
               if total_strength > 0 else 0.0)
        per_name[c["name"]] = {"budget": round(min(raw, c["cap"]), 2),
                               "cap": round(c["cap"], 2), "kind": c["kind"],
                               "book": c["book"],
                               "hold_style": c["hold_style"]}
    return {"reserve": reserve, "deployable": round(deployable, 2),
            "per_name": per_name, "buy_mode": buy_mode, "skipped": skipped,
            "envelopes": envelope_totals(per_name, caps)}


# ---------------------------------------------------------------- LEDGER

def ledger_verify(snapshot, sheet, earnings_rows):
    """Independent recomputation from the raw snapshot. Returns
    (agree, ledger_deployable, problems)."""
    problems = []
    reserve = RESERVE_BUY_MODE if sheet["buy_mode"] else RESERVE_NORMAL
    if abs(reserve - sheet["reserve"]) > 0.01:
        problems.append(f"reserve: TREASURER ${sheet['reserve']:,.2f} "
                        f"vs LEDGER ${reserve:,.2f}")
    bp = snapshot.get("buying_power") or 0.0
    deployable = max(0.0, bp - reserve)
    if abs(deployable - sheet["deployable"]) > 0.01:
        problems.append(f"deployable: TREASURER ${sheet['deployable']:,.2f} "
                        f"vs LEDGER ${deployable:,.2f}")
    value = snapshot["portfolio_value"]
    earn = {r["ticker"]: r for r in earnings_rows}
    total = 0.0
    for name, p in sheet["per_name"].items():
        cap = SINGLE_NAME_CAP * value
        existing = snapshot.get("positions", {}).get(name, {})
        # If a proposed name is already held, independently require a verified
        # current market value rather than assuming its entry cost is exposure.
        exposure = existing.get("market_value")
        if existing and exposure is None:
            problems.append(f"{name}: existing exposure unavailable")
        if exposure is not None:
            cap = max(0.0, cap - abs(exposure))
        e = earn.get(name)
        if e and e["sessions_until"] <= EARNINGS_WINDOW_SESSIONS:
            cap = min(cap, EARNINGS_CAP)
        if p["budget"] > cap + 0.01:
            problems.append(f"{name}: budget ${p['budget']:,.2f} over "
                            f"LEDGER cap ${cap:,.2f}")
        total += p["budget"]
    if total > min(deployable, sheet["deployable"]) + 0.01:
        problems.append(f"per name budgets sum ${total:,.2f} over the "
                        "deployable figure")
    # Two book split, recomputed independently: envelope caps are
    # 50/50 of deployable, every line carries the book its kind and
    # hold_style demand, and no book's budgets exceed its envelope.
    caps = envelope_caps(min(deployable, sheet["deployable"]))
    env = sheet.get("envelopes")
    if env is None:
        problems.append("envelopes: TREASURER sheet has no two book split")
    else:
        for book in ("LONG", "DAY"):
            if abs(env[book]["cap"] - caps[book]) > 0.01:
                problems.append(
                    f"{book} envelope cap: TREASURER "
                    f"${env[book]['cap']:,.2f} vs LEDGER ${caps[book]:,.2f} "
                    "(50/50 of deployable)")
    book_totals = {"LONG": 0.0, "DAY": 0.0}
    for name, p in sheet["per_name"].items():
        expected = book_for(p["kind"], p.get("hold_style"))
        if p.get("book") != expected:
            problems.append(f"{name}: labeled book {p.get('book')} but "
                            f"kind {p['kind']} with hold_style "
                            f"{p.get('hold_style')} belongs to {expected}")
        book_totals[expected] += p["budget"]
    for book in ("LONG", "DAY"):
        if book_totals[book] > caps[book] + 0.01:
            problems.append(f"{book} book budgets sum "
                            f"${book_totals[book]:,.2f} over its 50% "
                            f"envelope ${caps[book]:,.2f}")
        if env is not None and \
                abs(env[book]["allocated"] - round(book_totals[book], 2)) > 0.01:
            problems.append(f"{book} envelope allocated: TREASURER "
                            f"${env[book]['allocated']:,.2f} vs LEDGER "
                            f"${book_totals[book]:,.2f}")
    return (not problems), round(deployable, 2), problems


def build_sheet(snapshot, decisions, earnings_rows, buy_mode,
                odds_rows=None, extra_candidates=None):
    sheet = treasurer_propose(snapshot, decisions, earnings_rows, buy_mode,
                              odds_rows=odds_rows,
                              extra_candidates=extra_candidates)
    agree, ledger_deployable, problems = ledger_verify(
        snapshot, sheet, earnings_rows)
    final_deployable = min(sheet["deployable"], ledger_deployable) if agree else 0.0
    per_name = dict(sheet["per_name"])
    total = sum(p["budget"] for p in per_name.values())
    if total > final_deployable and total > 0:
        scale = final_deployable / total
        for p in per_name.values():
            p["budget"] = round(p["budget"] * scale, 2)
    caps = envelope_caps(final_deployable)
    return {"reserve": sheet["reserve"], "deployable": final_deployable,
            "treasurer_deployable": sheet["deployable"],
            "ledger_deployable": ledger_deployable,
            "per_name": per_name, "agreement": agree,
            "problems": problems, "buy_mode": buy_mode,
            "skipped": sheet.get("skipped", []),
            "envelopes": envelope_totals(per_name, caps),
            "caps": {"single_name_cap_pct": SINGLE_NAME_CAP * 100,
                     "earnings_cap": EARNINGS_CAP}}


def print_sheet(sheet, snapshot):
    mode = "buy mode" if sheet["buy_mode"] else "normal"
    lines = [f"BUDGET SHEET - TREASURER proposes, LEDGER verifies ({mode})"]
    lines.append(f"Snapshot: portfolio ${snapshot['portfolio_value']:,.2f}, "
                 f"buying power ${snapshot.get('buying_power', 0):,.2f}, "
                 f"loan ${snapshot.get('loan', 0):,.2f}")
    lines.append(f"Reserve held back: ${sheet['reserve']:,.2f}")
    if sheet["agreement"]:
        lines.append(f"Deployable: ${sheet['deployable']:,.2f} "
                     "(TREASURER and LEDGER agree)")
    else:
        lines.append("DISAGREEMENT:")
        lines.append(f"  TREASURER deployable ${sheet['treasurer_deployable']:,.2f}")
        lines.append(f"  LEDGER deployable ${sheet['ledger_deployable']:,.2f}")
        for p in sheet["problems"]:
            lines.append(f"  {p}")
        lines.append("  Sheet fails closed on disagreement: deployable "
                     f"${sheet['deployable']:,.2f}")
    env = sheet["envelopes"]
    lines.append("Two book budget, 50/50 of deployable (unspent "
                 "envelope money stays in reserve, no spill between "
                 "books):")
    lines.append(f"  LONG HOLD envelope (swing): cap "
                 f"${env['LONG']['cap']:,.2f}, budgeted "
                 f"${env['LONG']['allocated']:,.2f}")
    lines.append(f"  DAY TRADING envelope (intraday): cap "
                 f"${env['DAY']['cap']:,.2f}, budgeted "
                 f"${env['DAY']['allocated']:,.2f}")
    lines.append("  DAY book rule: the DAY TRADING book is fully "
                 "liquid by end of day, every day. The close session "
                 "flattens it. LONG HOLD positions may ride.")
    if sheet["per_name"]:
        lines.append("Per name budgets (singles funded top down by ODDS "
                     "EV inside their own book's envelope, pairs split "
                     "what is left of the LONG envelope by gap strength, "
                     "all capped):")
        for name, p in sorted(sheet["per_name"].items(),
                              key=lambda kv: -kv[1]["budget"]):
            ev = f", EV {p['ev']:+.2f}" if p.get("ev") is not None else ""
            lines.append(f"  [{p['book']:<4}] {name:<10} "
                         f"${p['budget']:>10,.2f}  "
                         f"(cap ${p['cap']:,.2f}, {p['kind']}{ev})")
        spent = sum(p["budget"] for p in sheet["per_name"].values())
        lines.append(f"  Unallocated (stays in reserve): "
                     f"${sheet['deployable'] - spent:,.2f}")
    else:
        lines.append("Per name budgets: none. No approved candidates, "
                     "or no deployable cash over the reserve.")
    for s in sheet.get("skipped", []):
        lines.append(f"  SKIPPED: {s}")
    lines.append("This sheet is PRE AUTHORIZATION: settled before the "
                 "open, so an intraday TRIPWIRE fire needs only account "
                 "verification and the fill, not a new budget.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--buy-mode", action="store_true",
                    help="Aaron's buy mode: reserve is $10k, not $15k")
    ap.add_argument("--day-change-pct", type=float, default=None)
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--sample-candidates", action="store_true",
                    help="TEST MODE: candidate pool built from scanner "
                         "output (turning up and latency names) instead "
                         "of JUDGE's approved list")
    args = ap.parse_args(argv)
    snapshot = rules.FRI_SNAPSHOT
    if args.snapshot:
        with open(args.snapshot) as f:
            snapshot = json.load(f)
    scan = rules.load_scan()
    decisions = rules.evaluate(snapshot, scan,
                               day_change_pct=args.day_change_pct)
    earnings_rows = earnings_bot.evaluate()
    odds_rows = odds.build_odds(scan)
    extra = None
    if args.sample_candidates:
        latency_syms = {c["symbol"]
                        for c in scan.get("latency_candidates", [])}
        extra = []
        for sym, s in scan.get("symbols", {}).items():
            t = s.get("ta") or {}
            if (t.get("turning_up") and not t.get("falling_knife")) \
                    or sym in latency_syms:
                extra.append({"symbol": sym,
                              "chg_5d_pct": s.get("chg_5d_pct")})
        print("TEST MODE: sample candidate set built from scanner "
              "output, not JUDGE's approved list.")
    sheet = build_sheet(snapshot, decisions, earnings_rows, args.buy_mode,
                        odds_rows=odds_rows, extra_candidates=extra)
    print(print_sheet(sheet, snapshot))
    out = os.path.join(HERE, "output", "budget.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"reserve": sheet["reserve"],
                   "deployable": sheet["deployable"],
                   "per_name": {k: v["budget"]
                                for k, v in sheet["per_name"].items()},
                   "books": {k: v["book"]
                             for k, v in sheet["per_name"].items()},
                   "envelopes": sheet["envelopes"],
                   "caps": sheet["caps"], "agreement": sheet["agreement"],
                   "buy_mode": sheet["buy_mode"]}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
