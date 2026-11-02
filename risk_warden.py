"""risk_warden.py - BOUNCER. Independent risk watchdog.

BOUNCER watches the book and throws out losers. It re-checks the
Protected Momentum risk rules on its own code: cap violations,
momentum exit trips, brake state, PROTECT state, buying power
floor. It deliberately shares NO decision code with rules.py
(JUDGE) - only the snapshot format and the scanner data file - so
the two engines cross check each other. Where they disagree, the
report prints a DISAGREEMENT section instead of hiding it.

Run: python3 risk_warden.py [--day-change-pct -9.3] [--log-calls]
Writes output/warden-latest.json and .txt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Warden's own copies of the thresholds (independence is the point;
# if these ever drift from JUDGE's, the DISAGREEMENT section is how
# we find out).
CAP = 0.25
FLOOR = 15_000.0
EXIT_PCT = -8.0
GIVEBACK = 0.40
BRAKE_1 = -4.0
BRAKE_2 = -6.0

# Warden's own copy of the Fri Oct 30 close fixture (data, not code).
FRI_SNAPSHOT = {
    "portfolio_value": 98_142.21, "start_value": 100_000.0,
    "peak_gain": 17_428.0, "cash": 0.0, "loan": 86_783.14,
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


def load_scan():
    with open(os.path.join(HERE, "output", "scan-latest.json")) as f:
        return json.load(f)


def _two_straight_closes(sdata, qty, entry_date):
    """Date aware two close exit, BOUNCER's own implementation of
    the same rule JUDGE carries: only daily closes dated on or
    after the position's entry date may count, because closes from
    before the position existed cannot exit it (Mon Nov 2: MSFT,
    PLTR and VST were flagged on pre entry Thu and Fri closes).
    A missing entry date, or scan data without dated closes,
    suppresses this flag; the -8% exit is unaffected.
    """
    dated = (sdata or {}).get("closes_dated") or []
    if not entry_date or len(dated) < 3:
        return False
    eligible = [i for i, c in enumerate(dated)
                if str(c.get("date", "")) >= str(entry_date)]
    if len(eligible) < 2:
        return False
    i1, i2 = eligible[-2], eligible[-1]
    if i1 < 1 or i2 != i1 + 1:
        return False
    a = dated[i1 - 1]["close"]
    b = dated[i1]["close"]
    c = dated[i2]["close"]
    return c < b < a if qty >= 0 else c > b > a


def check(snapshot, scan, day_change_pct=None, protect_lift=False):
    syms = scan.get("symbols", {})
    value = snapshot["portfolio_value"]
    w = {}
    gain = value - snapshot.get("start_value", 100_000.0)
    peak = snapshot.get("peak_gain", 0.0)
    w["protect_mode"] = bool(peak > 0 and (peak - gain) / peak >= GIVEBACK)
    # Same lift plumbing as JUDGE, on BOUNCER's own code: the flag or
    # the snapshot field records that Aaron's documented lift is in
    # effect. BOUNCER still computes and reports the raw PROTECT
    # state above; the lift is cross checked against JUDGE's output
    # below so the two engines can never silently split on it.
    w["protect_lifted"] = bool(protect_lift
                               or snapshot.get("protect_lifted"))
    if day_change_pct is None:
        w["brake_state"] = "unknown"
    elif day_change_pct <= BRAKE_2:
        w["brake_state"] = "full"
    elif day_change_pct <= BRAKE_1:
        w["brake_state"] = "brake"
    else:
        w["brake_state"] = "none"
    bp = snapshot.get("buying_power")
    w["bp_shortfall"] = (None if bp is None
                         else round(max(0.0, FLOOR - bp), 2))
    caps, exits = [], []
    for sym, pos in snapshot["positions"].items():
        s = syms.get(sym)
        if not s:
            continue
        last = s["last_close"]
        if abs(pos["qty"] * last) > CAP * value:
            caps.append(sym)
        reasons = []
        entry = pos.get("entry")
        if entry and (last / entry - 1.0) * 100.0 * (1 if pos["qty"] >= 0 else -1) <= EXIT_PCT:
            reasons.append("-8% from entry")
        if _two_straight_closes(s, pos["qty"], pos.get("entry_date")):
            reasons.append("two straight red closes")
        if reasons:
            exits.append({"symbol": sym, "reasons": reasons})
    w["cap_violations"] = sorted(caps)
    w["exit_flags"] = exits
    return w


def compare(w, rules_path=None):
    """Cross check against JUDGE's last output. Returns a list of
    disagreement strings (empty when they agree or JUDGE has not run)."""
    rules_path = rules_path or os.path.join(HERE, "output", "rules-latest.json")
    if not os.path.exists(rules_path):
        return ["JUDGE has no output on file yet, nothing to cross check"]
    with open(rules_path) as f:
        j = json.load(f)
    out = []
    if bool(j.get("protect_mode")) != w["protect_mode"]:
        out.append(f"PROTECT: BOUNCER says {w['protect_mode']}, "
                   f"JUDGE says {j.get('protect_mode')}")
    if bool(j.get("protect_lifted")) != bool(w.get("protect_lifted")):
        out.append(f"PROTECT lift: BOUNCER says "
                   f"{bool(w.get('protect_lifted'))}, JUDGE says "
                   f"{bool(j.get('protect_lifted'))}")
    j_caps = sorted(v["symbol"] for v in j.get("cap_violations", []))
    if j_caps != w["cap_violations"]:
        out.append(f"cap violations: BOUNCER {w['cap_violations']} "
                   f"vs JUDGE {j_caps}")
    j_exits = sorted(e["symbol"] for e in j.get("exit_flags", []))
    w_exits = sorted(e["symbol"] for e in w["exit_flags"])
    if j_exits != w_exits:
        out.append(f"exit flags: BOUNCER {w_exits} vs JUDGE {j_exits}")
    if j.get("brake_state") not in (None, "unknown") \
            and w["brake_state"] != "unknown" \
            and j.get("brake_state") != w["brake_state"]:
        out.append(f"brake: BOUNCER {w['brake_state']} vs "
                   f"JUDGE {j.get('brake_state')}")
    j_short = j.get("buying_power_shortfall")
    if j_short is not None and w["bp_shortfall"] is not None \
            and abs(j_short - w["bp_shortfall"]) > 0.01:
        out.append(f"buying power shortfall: BOUNCER ${w['bp_shortfall']:,.2f} "
                   f"vs JUDGE ${j_short:,.2f}")
    return out


def build_report(w, disagreements):
    lines = ["BOUNCER - independent risk watchdog (shares no code with JUDGE)"]
    lines.append(f"PROTECT mode: {'ON' if w['protect_mode'] else 'off'}")
    if w.get("protect_lifted"):
        lines.append("PROTECT lift: in effect by documented session "
                     "order (state still reported above; matches JUDGE "
                     "when the cross check below is clean)")
    lines.append(f"Brake state: {w['brake_state']}")
    lines.append("Buying power floor: "
                 + (f"BELOW by ${w['bp_shortfall']:,.2f}"
                    if w["bp_shortfall"] else "ok or unknown"))
    lines.append("Cap violations: "
                 + (", ".join(w["cap_violations"]) or "none"))
    if w["exit_flags"]:
        lines.append("Exit trips (throw them out):")
        for e in w["exit_flags"]:
            lines.append(f"  {e['symbol']}: " + "; ".join(e["reasons"]))
    else:
        lines.append("Exit trips: none")
    lines.append("")
    if disagreements:
        lines.append("DISAGREEMENT (BOUNCER vs JUDGE):")
        for d in disagreements:
            lines.append(f"  {d}")
    else:
        lines.append("Cross check: BOUNCER and JUDGE agree on every check.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day-change-pct", type=float, default=None)
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--protect-lift", action="store_true",
                    help="record Aaron's documented PROTECT lift for "
                         "this run, matching JUDGE's --protect-lift; "
                         "the snapshot field \"protect_lifted\": true "
                         "does the same. PROTECT state is still "
                         "computed and reported either way")
    ap.add_argument("--log-calls", action="store_true",
                    help="log BOUNCER exit calls for THE BOARD (scored "
                         "on losses avoided)")
    args = ap.parse_args(argv)
    snapshot = FRI_SNAPSHOT
    if args.snapshot:
        with open(args.snapshot) as f:
            snapshot = json.load(f)
    scan = load_scan()
    w = check(snapshot, scan, day_change_pct=args.day_change_pct,
              protect_lift=args.protect_lift)
    disagreements = compare(w)
    w["disagreements"] = disagreements
    report = build_report(w, disagreements)
    print(report)
    out_dir = os.path.join(HERE, "output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "warden-latest.json"), "w") as f:
        json.dump(w, f, indent=1)
    with open(os.path.join(out_dir, "warden-latest.txt"), "w") as f:
        f.write(report + "\n")
    if args.log_calls:
        from leaderboard import log_call
        syms = scan.get("symbols", {})
        n = 0
        for e in w["exit_flags"]:
            s = syms.get(e["symbol"]) or {}
            if s.get("last_close"):
                log_call("BOUNCER", e["symbol"], "exit", s["last_close"],
                         "BOUNCER exit trip: " + "; ".join(e["reasons"]))
                n += 1
        print(f"[BOUNCER] logged {n} exit call(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
