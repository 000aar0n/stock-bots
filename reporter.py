"""reporter.py - HERALD. End of day summary, score first.

HERALD announces the score. It reads the other bots' outputs
(scan-latest.json from FALCON, rules-latest.json from JUDGE,
warden-latest.json from BOUNCER, earnings and specialists outputs,
the factory thermometer file, and THE BOARD standings) and prints
one summary in plain words. Score first, always. No em dashes
anywhere in what HERALD prints, by Aaron's standing rule.

Run: python3 reporter.py
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")


def _load(name):
    try:
        with open(os.path.join(OUT, name)) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def build_summary():
    rules = _load("rules-latest.json")
    scan = _load("scan-latest.json")
    warden = _load("warden-latest.json")
    earnings = _load("earnings-latest.json")
    specialists = _load("specialists-latest.json")
    thermos = _load("thermometers.json")
    lines = ["HERALD - end of day summary"]
    if rules:
        lines.append(f"Score: start ${rules['start_value']:,.0f}, now "
                     f"${rules['portfolio_value']:,.2f}, "
                     f"change ${rules['current_gain']:+,.2f}.")
        lines.append(f"PROTECT mode is "
                     f"{'ON' if rules['protect_mode'] else 'off'}. "
                     f"Brake state: {rules.get('brake_state', 'unknown')}. "
                     f"Buying power floor: {rules['buying_power_floor']}")
        if rules["cap_violations"]:
            v = ", ".join(f"{x['symbol']} at "
                          f"{x['pct_of_portfolio']:.0f} percent of the book"
                          for x in rules["cap_violations"])
            lines.append(f"Over the single name cap: {v}.")
        if rules["exit_flags"]:
            lines.append("Exit flags from JUDGE: "
                         + ", ".join(e["symbol"]
                                     for e in rules["exit_flags"]) + ".")
        for sym, directive in (rules.get("directives") or {}).items():
            lines.append(f"Directive on {sym}: {directive}")
    else:
        lines.append("Score unavailable, JUDGE has not written a report yet.")
    if warden is not None:
        if warden.get("disagreements"):
            lines.append("BOUNCER disagrees with JUDGE: "
                         + "; ".join(warden["disagreements"]) + ".")
        else:
            lines.append("BOUNCER cross checked JUDGE and they agree.")
    if thermos and thermos.get("QQQ"):
        q = thermos["QQQ"]
        lines.append(f"Market regime (QQQ THERMOMETER): {q['regime']}. "
                     f"{q['detail']}")
    if scan:
        syms = scan.get("symbols", {})
        ranked = sorted(syms.items(),
                        key=lambda kv: -(kv[1]["chg_5d_pct"] or 0))
        if ranked:
            top = ", ".join(f"{s} {v['chg_5d_pct']:+.1f} percent"
                            for s, v in ranked[:3])
            lines.append(f"Strongest 5 session movers in the scan: {top}.")
        lat = scan.get("latency_candidates") or []
        if lat:
            lines.append("Latency candidates to verify against the sim "
                         "price before any order: "
                         + ", ".join(c["symbol"] for c in lat) + ".")
        flagged = [p for p in scan.get("pairs", []) if p.get("flagged")]
        if flagged:
            lines.append("Pair gaps at the arb threshold: "
                         + ", ".join(f"{p['pair']} {p['gap_points']:+.1f} pts"
                                     for p in flagged)
                         + ". News check still applies.")
    if earnings and earnings.get("rows"):
        nxt = earnings["rows"][0]
        lines.append(f"Next earnings print on the calendar: "
                     f"{nxt['ticker']} on {nxt['date']} ({nxt['when']}).")
        for r in earnings["rows"]:
            if r.get("flag"):
                lines.append(f"SIREN flag: {r['ticker']} is held and "
                             f"inside 2 sessions of its print.")
    if specialists:
        best = max(specialists.items(),
                   key=lambda kv: len(kv[1].get("turning_up", [])),
                   default=None)
        if best and best[1].get("turning_up"):
            lines.append(f"Specialist with the most names turning up: "
                         f"{best[0]} ({', '.join(best[1]['turning_up'])}).")
    try:
        import leaderboard
        live, _arena = leaderboard.split_sources(leaderboard.load_calls())
        if live:
            standings = leaderboard.compute_standings(live)
            proven = [(b, s) for b, s in leaderboard.ranked_bots(standings)
                      if s["calls"] >= leaderboard.MIN_PROVEN_CALLS]
            if proven:
                # EQUALITY PROTOCOL: a quoted bot carries its proven
                # record, never naked authority.
                lines.append("Bot leaderboard top 3 (live, proven): "
                             + ", ".join(
                                 f"{i + 1}. {b} "
                                 f"({leaderboard.bot_record(b, standings)})"
                                 for i, (b, s) in enumerate(proven[:3]))
                             + ".")
            else:
                lines.append("Bot leaderboard: calls on file but every "
                             "bot is still UNPROVEN (under 5 calls).")
            intra, swing = leaderboard.active_call_mix(live)
            lines.append(f"Active paper calls by hold style: {intra} "
                         f"intraday, {swing} swing. The city is day "
                         "trader first; swing is the earned exception.")
        else:
            lines.append("Bot leaderboard: no live calls yet, rankings "
                         "open Monday in shadow mode.")
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(lines)


def main():
    print(build_summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
