"""rules.py - JUDGE. Protected Momentum rules engine for the HTMW book.

JUDGE runs Protected Momentum by the book. Loss side first: every
buy candidate it prints ships with its exit trigger and the current
brake state attached. Nothing is ever recommended naked - if PROTECT
mode or the daily brake blocks entries, the candidate prints as
BLOCKED with the reason.

Implements the risk rules from the trading style doc
(~/workspace/goals/howthemarketworks-stock-trading/hidden_files/trading-style.md):

  1. Buying power floor: keep about $15k free.
  2. Single name cap: no name above about 25% of portfolio value.
  3. Daily brake: day down ~4% = no new positions; ~6% = also sell weakest.
  4. Profit guard: giveback of ~40% of peak total gain = PROTECT mode
     (no new momentum entries until a green day; stat arb may continue).
  6. Momentum exit: a name down ~8% from entry, or red at two straight
     closes, is cut at the next check.
  Arb: pairs flagged at a 10+ point 5-session relative stretch are
     candidates only - the style also requires no fundamental news
     behind the stretch, which this engine cannot check.

The engine READS and RECOMMENDS. It never places orders.

Run: python3 rules.py [--day-change-pct -9.3]
Uses output/scan-latest.json for prices (run scanner.py first; if the
file is missing it runs a fresh scan in-process).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN_JSON = os.path.join(HERE, "output", "scan-latest.json")

START_VALUE = 100_000.0
PEAK_GAIN = 17_428.0          # Wed Oct 28 close $117,428.44
SINGLE_NAME_CAP = 0.25        # of portfolio value
BUYING_POWER_FLOOR = 15_000.0
TOTAL_ENVELOPE = 200_000.0    # Aaron, Sat Oct 31, 2026: total buying
                              # power is about $200k, that is the whole
                              # pie. Never fully invested (reserve floor
                              # survives every plan), never all in one
                              # name, and the book stays working.
BRAKE_NO_NEW = -4.0           # percent on the day
BRAKE_SELL_WEAKEST = -6.0     # percent on the day
PROTECT_GIVEBACK = 0.40       # of peak total gain
EXIT_FROM_ENTRY = -8.0        # percent
ARB_GAP_FLAG = 10.0           # points

# Standing directives from Aaron that the engine must always surface.
DIRECTIVES = {
    "CVNA": "FULL EXIT on Mon Nov 2 - Aaron's decision Sat Oct 31 "
            "(replaces any trim-to-cap idea).",
}


def load_scan():
    if os.path.exists(SCAN_JSON):
        with open(SCAN_JSON) as f:
            return json.load(f)
    import scanner  # local module, fresh scan as fallback
    return scanner.run_scan()


def evaluate(snapshot, scan, day_change_pct=None):
    syms = scan.get("symbols", {})
    value = snapshot["portfolio_value"]
    decisions = {
        "portfolio_value": value,
        "start_value": snapshot.get("start_value", START_VALUE),
    }

    # --- profit guard / PROTECT mode (rule 4)
    peak_gain = snapshot.get("peak_gain", PEAK_GAIN)
    gain = value - decisions["start_value"]
    decisions["current_gain"] = round(gain, 2)
    decisions["peak_gain"] = peak_gain
    if peak_gain > 0:
        giveback = (peak_gain - gain) / peak_gain
    else:
        giveback = 0.0
    decisions["giveback_pct_of_peak"] = round(giveback * 100, 1)
    decisions["protect_mode"] = giveback >= PROTECT_GIVEBACK
    decisions["protect_note"] = (
        "PROTECT: no new momentum entries until a green day; stat arb "
        "entries may continue; ordered rebalances still complete."
        if decisions["protect_mode"] else
        "Profit guard not tripped.")

    # --- daily brake (rule 3)
    if day_change_pct is None:
        brake_state = "unknown"
        decisions["daily_brake"] = "unknown - no day change supplied"
    elif day_change_pct <= BRAKE_SELL_WEAKEST:
        brake_state = "full"
        decisions["daily_brake"] = (
            f"FULL BRAKE at {day_change_pct:+.1f}%: sell weakest momentum "
            "name, hold proceeds, no new positions, no redeploy today.")
    elif day_change_pct <= BRAKE_NO_NEW:
        brake_state = "brake"
        decisions["daily_brake"] = (
            f"BRAKE at {day_change_pct:+.1f}%: no new positions, "
            "rotations into strength only.")
    else:
        brake_state = "none"
        decisions["daily_brake"] = f"no brake (day {day_change_pct:+.1f}%)"
    decisions["brake_state"] = brake_state

    # --- buying power floor (rule 1)
    bp = snapshot.get("buying_power")
    decisions["buying_power"] = bp
    if bp is None:
        decisions["buying_power_floor"] = "unknown - no buying power supplied"
        decisions["buying_power_shortfall"] = None
    else:
        shortfall = max(0.0, BUYING_POWER_FLOOR - bp)
        decisions["buying_power_shortfall"] = round(shortfall, 2)
        decisions["buying_power_floor"] = (
            f"BELOW FLOOR by ${shortfall:,.2f} (buying power ${bp:,.2f} "
            f"vs ${BUYING_POWER_FLOOR:,.0f} target)"
            if shortfall > 0 else
            f"ok (${bp:,.2f} free vs ${BUYING_POWER_FLOOR:,.0f} floor)")

    # --- per-position checks (rules 2 and 6)
    cap_dollars = SINGLE_NAME_CAP * value
    cap_violations, exit_flags, position_rows, unevaluated = [], [], [], []
    for sym, pos in snapshot["positions"].items():
        qty = pos["qty"]
        entry = pos.get("entry")
        sdata = syms.get(sym)
        last = sdata["last_close"] if sdata else None
        mval = qty * last if last is not None else None
        row = {"symbol": sym, "qty": qty, "entry": entry, "last": last,
               "market_value": None if mval is None else round(mval, 2),
               "pct_of_portfolio": None if mval is None else round(mval / value * 100, 1)}
        position_rows.append(row)
        if mval is not None and abs(mval) > cap_dollars:
            cap_violations.append({
                "symbol": sym, "market_value": round(mval, 2),
                "pct_of_portfolio": row["pct_of_portfolio"],
                "cap_dollars": round(cap_dollars, 2),
                "excess_dollars": round(abs(mval) - cap_dollars, 2)})
        reasons = []
        if entry is not None and last is not None:
            pct_entry = (last / entry - 1.0) * 100.0 * (1 if qty >= 0 else -1)
            row["pct_from_entry"] = round(pct_entry, 2)
            if pct_entry <= EXIT_FROM_ENTRY:
                reasons.append(f"down {pct_entry:.1f}% from entry "
                               f"(exit line {EXIT_FROM_ENTRY:.0f}%)")
        else:
            row["pct_from_entry"] = None
            if entry is None:
                unevaluated.append(f"{sym}: no entry price, "
                                   "cannot evaluate the -8% exit rule")
        if sdata:
            tail = sdata.get("closes_tail") or []
            if len(tail) >= 3 and ((qty >= 0 and tail[-1] < tail[-2] < tail[-3]) or (qty < 0 and tail[-1] > tail[-2] > tail[-3])):
                reasons.append("red at two straight closes")
            t = sdata.get("ta") or {}
            row["ta_trend"] = t.get("trend")
            row["falling_knife"] = t.get("falling_knife")
            row["turning_up"] = t.get("turning_up")
        if reasons:
            exit_flags.append({"symbol": sym, "reasons": reasons})
        if sym in DIRECTIVES:
            row["directive"] = DIRECTIVES[sym]
    decisions["positions"] = position_rows
    decisions["cap_violations"] = cap_violations
    decisions["exit_flags"] = exit_flags
    decisions["unevaluated"] = unevaluated
    decisions["directives"] = {s: DIRECTIVES[s] for s in snapshot["positions"]
                               if s in DIRECTIVES}

    # --- total envelope (Aaron, Sat Oct 31, 2026, voice call): the
    # whole pie is about $200k of buying power. Three lines JUDGE must
    # hold: never over the envelope, never effectively fully invested
    # (buying power under the reserve floor means no new buys until
    # room is freed), never all in one name (rule 2 cap above). The
    # other direction matters too: the book stays working, capital is
    # not parked in cash while approved calls exist.
    gross = sum(abs(r["market_value"]) for r in position_rows
                if r["market_value"] is not None)
    decisions["gross_exposure"] = round(gross, 2)
    decisions["total_envelope"] = TOTAL_ENVELOPE
    decisions["envelope_used_pct"] = round(gross / TOTAL_ENVELOPE * 100, 1)
    if gross > TOTAL_ENVELOPE:
        decisions["envelope"] = (
            f"OVER ENVELOPE: gross ${gross:,.2f} exceeds Aaron's "
            f"~$200,000 total buying power envelope. Trim before any "
            f"new buy.")
    elif bp is not None and bp < BUYING_POWER_FLOOR:
        decisions["envelope"] = (
            f"INSIDE envelope (gross ${gross:,.2f} of ~$200,000, "
            f"{decisions['envelope_used_pct']:.1f}%) but effectively "
            f"FULLY INVESTED: buying power ${bp:,.2f} is under the "
            f"$15,000 reserve floor, so no new buys until room is freed.")
    else:
        decisions["envelope"] = (
            f"ok: gross ${gross:,.2f} of the ~$200,000 envelope "
            f"({decisions['envelope_used_pct']:.1f}%), reserve intact, "
            f"spread enforced by the 25% single name cap.")

    # --- arb candidates (scanner gaps; news check NOT automated)
    arb = []
    for p in scan.get("pairs", []):
        if p.get("flagged"):
            arb_blocked = brake_state == "full"
            arb.append({"pair": p["pair"], "gap_points": p["gap_points"],
                        "long_leg": p["long_leg"], "short_leg": p["short_leg"],
                        "exit_trigger": "exit the pair when half the gap "
                                        "has closed, after 3 sessions, or "
                                        "if the gap widens 5 more points",
                        "brake_state": brake_state,
                        "blocked": arb_blocked,
                        "blocked_reason": ("daily brake is FULL: no "
                                           "redeploy today"
                                           if arb_blocked else None),
                        "caveat": "candidate only - style also requires no "
                                  "fundamental news behind the stretch and "
                                  "no earnings/guidance shock in the last "
                                  "2 sessions; verify before entering. "
                                  "PROTECT mode does not block stat arb."})
    decisions["arb_candidates"] = arb

    # --- buy candidates, each paired with its loss plan (Aaron's
    # steering: loss side first, entries second). A candidate is a
    # scanned name outside the book flagged turning_up and NOT
    # falling_knife. Falling knife names are never candidates.
    latency_syms = {c["symbol"] for c in scan.get("latency_candidates", [])}
    cands = []
    for sym, s in syms.items():
        if sym in snapshot["positions"]:
            continue
        t = s.get("ta") or {}
        if not t.get("turning_up") or t.get("falling_knife"):
            continue
        last = s["last_close"]
        blocked_reasons = []
        if brake_state == "unknown":
            blocked_reasons.append("day change unavailable: daily brake cannot be verified")
        if bp is None or bp < BUYING_POWER_FLOOR:
            blocked_reasons.append("buying power reserve unavailable or below floor")
        if gross >= TOTAL_ENVELOPE:
            blocked_reasons.append("gross envelope full")
        if decisions["protect_mode"]:
            blocked_reasons.append(
                "PROTECT mode: no new momentum entries until a green day")
        if brake_state == "full":
            blocked_reasons.append(
                "daily brake FULL: no new positions, no redeploy today")
        elif brake_state == "brake":
            blocked_reasons.append(
                "daily brake: no new positions, rotations into strength only")
        is_latency = sym in latency_syms
        cands.append({
            "symbol": sym, "last_close": last,
            "chg_5d_pct": s.get("chg_5d_pct"),
            "exit_price": round(last * 0.92, 2),
            "exit_trigger": (
                f"cut at the next check if down 8% from entry "
                f"(at or below ${last * 0.92:,.2f} on today's price) or "
                "red at two straight closes"),
            "brake_state": brake_state,
            "protect_mode": decisions["protect_mode"],
            "blocked": bool(blocked_reasons),
            "blocked_reasons": blocked_reasons,
            "latency_candidate": is_latency,
            "verification": (
                "latency candidate: verify against the price HTMW "
                "displays before any order" if is_latency else None),
        })
    cands.sort(key=lambda c: -(c["chg_5d_pct"] or 0))
    decisions["buy_candidates"] = cands[:8]
    decisions["falling_knife_names"] = sorted(
        sym for sym, s in syms.items()
        if sym not in snapshot["positions"]
        and (s.get("ta") or {}).get("falling_knife"))
    return decisions


def _thermometer_line():
    """QQQ THERMOMETER line from the bot factory run, if present."""
    path = os.path.join(HERE, "output", "thermometers.json")
    try:
        with open(path) as f:
            data = json.load(f)
        q = data.get("QQQ")
        if q:
            return (f"Market regime (QQQ THERMOMETER): {q['regime']} - "
                    f"{q['detail']}")
    except Exception:  # noqa: BLE001 - optional context only
        pass
    return None


def _call_mix_line():
    """Active bot paper calls by hold style (day trader doctrine:
    the mix stays visible in JUDGE's report)."""
    try:
        import leaderboard
        intra, swing = leaderboard.active_call_mix()
        return (f"Bot paper calls active now: {intra} intraday, "
                f"{swing} swing (city default is intraday; swing "
                "positions earned the exception)")
    except Exception:  # noqa: BLE001 - optional context only
        return None


def build_report(d):
    lines = []
    lines.append("JUDGE - PROTECTED MOMENTUM RULES ENGINE VERDICTS")
    tline = _thermometer_line()
    if tline:
        lines.append(tline)
    mline = _call_mix_line()
    if mline:
        lines.append(mline)
    lines.append(f"Portfolio ${d['portfolio_value']:,.2f}  "
                 f"gain ${d['current_gain']:+,.2f} vs ${d['start_value']:,.0f} start  "
                 f"(peak gain ${d['peak_gain']:,.0f}, giveback "
                 f"{d['giveback_pct_of_peak']:.1f}% of peak)")
    lines.append(f"PROTECT mode: {'ON' if d['protect_mode'] else 'off'} - {d['protect_note']}")
    lines.append(f"Daily brake: {d['daily_brake']}")
    lines.append(f"Buying power floor: {d['buying_power_floor']}")
    lines.append(f"Envelope: {d.get('envelope', 'unknown')}")
    lines.append("")
    lines.append("POSITIONS")
    for r in sorted(d["positions"], key=lambda r: -(r["market_value"] or 0)):
        bits = [f"  {r['symbol']:<6} x{r['qty']:<6}"]
        if r["last"] is not None:
            bits.append(f"last ${r['last']:,.2f}  MV ${r['market_value']:,.2f} "
                        f"({r['pct_of_portfolio']:.1f}% of book)")
        if r.get("pct_from_entry") is not None:
            bits.append(f"vs entry {r['pct_from_entry']:+.1f}%")
        if r.get("ta_trend"):
            bits.append(f"trend {r['ta_trend']}")
        if r.get("falling_knife"):
            bits.append("FALLING_KNIFE")
        if r.get("turning_up"):
            bits.append("TURNING_UP")
        lines.append("  ".join(bits))
        if r.get("directive"):
            lines.append(f"         DIRECTIVE: {r['directive']}")
    lines.append("")
    if d["cap_violations"]:
        lines.append("SINGLE NAME CAP VIOLATIONS (25% cap)")
        for v in d["cap_violations"]:
            lines.append(f"  {v['symbol']}: ${v['market_value']:,.2f} = "
                         f"{v['pct_of_portfolio']:.1f}% of book, "
                         f"${v['excess_dollars']:,.2f} over the "
                         f"${v['cap_dollars']:,.2f} cap")
    else:
        lines.append("Single name cap: no violations")
    lines.append("")
    if d["exit_flags"]:
        lines.append("MOMENTUM EXIT FLAGS (cut at next check per the style)")
        for e in d["exit_flags"]:
            lines.append(f"  {e['symbol']}: " + "; ".join(e["reasons"]))
    else:
        lines.append("Momentum exits: none flagged")
    lines.append("")
    if d["arb_candidates"]:
        lines.append("STAT ARB CANDIDATES (gap >= 10 pts, news check still required)")
        for a in d["arb_candidates"]:
            status = ("BLOCKED - " + a["blocked_reason"]) if a["blocked"] \
                else "actionable if the news check clears"
            lines.append(f"  {a['pair']}: gap {a['gap_points']:+.2f} pts - "
                         f"long {a['long_leg']} / short {a['short_leg']}")
            lines.append(f"    loss plan: {a['exit_trigger']} | "
                         f"brake state: {a['brake_state']} | {status}")
    else:
        lines.append("Stat arb candidates: no pair at the 10 point threshold")
    lines.append("")
    if d.get("buy_candidates"):
        lines.append("BUY CANDIDATES (turning up outside the book; every "
                     "one ships with its loss plan)")
        for c in d["buy_candidates"]:
            status = ("BLOCKED - " + "; ".join(c["blocked_reasons"])) \
                if c["blocked"] else "ACTIONABLE"
            lines.append(f"  {c['symbol']}: ${c['last_close']:,.2f}, "
                         f"5d {c['chg_5d_pct']:+.1f}%")
            lines.append(f"    loss plan: {c['exit_trigger']} | "
                         f"brake state: {c['brake_state']} | {status}")
            if c["verification"]:
                lines.append(f"    verify first: {c['verification']}")
    else:
        lines.append("Buy candidates: none flagged turning up outside "
                     "the book in this scan")
    if d.get("falling_knife_names"):
        lines.append("")
        lines.append("FALLING KNIFE BLOCK (never buy candidates): "
                     + ", ".join(d["falling_knife_names"]))
    if d["unevaluated"]:
        lines.append("")
        lines.append("COULD NOT EVALUATE:")
        for u in d["unevaluated"]:
            lines.append(f"  {u}")
    return "\n".join(lines)


# Fri Oct 30, 2026 close snapshot (verified HTMW close session figures).
FRI_SNAPSHOT = {
    "portfolio_value": 98_142.21,
    "start_value": 100_000.0,
    "peak_gain": PEAK_GAIN,
    "cash": 0.0,
    "loan": 86_783.14,
    "buying_power": 11_308.51,
    "positions": {
        "CVNA": {"qty": 809, "entry": 68.6},
        "SOFI": {"qty": 1610, "entry": None},
        "NVDA": {"qty": 96, "entry": 206.45},
        "AVGO": {"qty": 60, "entry": 327.70},
        "AMZN": {"qty": 65, "entry": 238.33},
        "MSTR": {"qty": 79, "entry": 127.39},
        "REGN": {"qty": 10, "entry": 911.27},
        "CPRI": {"qty": 500, "entry": 18.57},
        "LNG": {"qty": 28, "entry": 328.69},
        "GPN": {"qty": 100, "entry": 95.57},
    },
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day-change-pct", type=float, default=None,
                    help="portfolio change on the day in percent, "
                         "e.g. -9.3 for the Fri Oct 30 brake check")
    ap.add_argument("--snapshot", default=None,
                    help="path to a snapshot JSON (default: Fri fixture)")
    ap.add_argument("--log-calls", action="store_true",
                    help="also log JUDGE paper calls to output/calls.jsonl: "
                         "ACTIONABLE buy candidates as buys, momentum exit "
                         "flags as exits (Monday shadow mode; off for tests)")
    args = ap.parse_args(argv)

    snapshot = FRI_SNAPSHOT
    if args.snapshot:
        with open(args.snapshot) as f:
            snapshot = json.load(f)
    scan = load_scan()
    decisions = evaluate(snapshot, scan, day_change_pct=args.day_change_pct)
    report = build_report(decisions)
    print(report)
    if args.log_calls:
        from leaderboard import log_call
        syms = scan.get("symbols", {})
        n = 0
        for c in decisions["buy_candidates"]:
            if not c["blocked"]:
                log_call("JUDGE", c["symbol"], "buy", c["last_close"],
                         "JUDGE buy candidate, loss plan: " + c["exit_trigger"])
                n += 1
        for e in decisions["exit_flags"]:
            s = syms.get(e["symbol"]) or {}
            if s.get("last_close"):
                log_call("JUDGE", e["symbol"], "exit", s["last_close"],
                         "JUDGE exit flag: " + "; ".join(e["reasons"]))
                n += 1
        print(f"[JUDGE] logged {n} paper call(s) to output/calls.jsonl",
              file=sys.stderr)
    out = os.path.join(HERE, "output", "rules-latest.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(decisions, f, indent=1)
    with open(os.path.join(HERE, "output", "rules-latest.txt"), "w") as f:
        f.write(report + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
