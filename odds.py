"""odds.py - ODDS. The projector. Expected value ranking, never promises.

For every candidate the other bots surface (FALCON's scan,
specialists, factory bots), ODDS computes an expected value score
from data we actually have:

  expected move size: ATR as a percent of price, plus half the live
    move already in progress (today's change, or the latency window
    move for latency candidates)
  momentum strength: distance above SMA20 and SMA50, RSI zone
    (50 to 70 healthy, over 80 overextended), relative volume
  catalyst flags: a latency candidate counts FOR; earnings inside
    2 sessions counts AGAINST, unless SIREN marks the name a
    deliberate reaction play
  downside estimate: distance to the nearer of the -8 percent exit
    level and the 20 day low (the support proxy)

  Heuristic score = upside proxy minus downside proxy; not probability-weighted EV

HARD RULE: ODDS ranks, it never promises. Every number here is an
estimate built from volatility and recent price action, not a
prediction. Negative EV names get skipped by TREASURER no matter
how loud their bot is (see allocator.py).

Run: python3 odds.py
Writes output/odds-latest.json.
"""

from __future__ import annotations

import json
import os
import sys

import earnings_bot
import scanner

HERE = os.path.dirname(os.path.abspath(__file__))
EARNINGS_PENALTY = 2.0  # pct points against, inside the window


def _candidates(scan, specialists):
    """Deduped candidate map: ticker -> {sources, from scan row}."""
    out = {}
    syms = scan.get("symbols", {})
    latency_syms = {c["symbol"] for c in scan.get("latency_candidates", [])}
    for sym, s in syms.items():
        t = s.get("ta") or {}
        if t.get("turning_up") and not t.get("falling_knife"):
            out.setdefault(sym, {"sources": [], "scan": s})
            out[sym]["sources"].append("FALCON")
    for sym in latency_syms:
        if sym in syms:
            out.setdefault(sym, {"sources": [], "scan": syms[sym]})
            out[sym]["sources"].append("FALCON latency")
    for name, summ in (specialists or {}).items():
        for sym in summ.get("turning_up", []):
            if sym in syms:
                out.setdefault(sym, {"sources": [], "scan": syms[sym]})
                out[sym]["sources"].append(name)
    return out


def score_candidate(sym, sdata, earnings_rows):
    """Heuristic ranking for one candidate. This is not measured expected profit."""
    t = sdata.get("ta") or {}
    close = sdata["last_close"]
    atr_pct = (t["atr14"] / close * 100.0) if t.get("atr14") and close else 0.0
    lat = sdata.get("latency") or {}
    is_latency = bool(lat.get("candidate"))
    live_move = lat["move_pct"] if is_latency and lat.get("move_pct") \
        is not None else (sdata.get("chg_1d_pct") or 0.0)
    dist20 = ((close / t["sma20"] - 1.0) * 100.0) if t.get("sma20") else 0.0
    dist50 = ((close / t["sma50"] - 1.0) * 100.0) if t.get("sma50") else 0.0
    momentum = 0.5 * dist20 + 0.5 * dist50
    rsi = t.get("rsi14")
    if rsi is not None:
        if 50 <= rsi <= 70:
            momentum += 0.5
        elif rsi > 80:
            momentum -= 1.0
        elif rsi < 35:
            momentum -= 0.5
    rel_vol = t.get("rel_volume")
    if rel_vol is not None and rel_vol >= 1.5:
        momentum += 0.5
    expected_gain = atr_pct + max(0.0, momentum) + 0.5 * max(0.0, live_move)
    flags = []
    if is_latency:
        flags.append("latency candidate (counts for)")
    # Downside: nearer of the -8% exit and the 20 day low.
    low20 = sdata.get("low_20d")
    if low20:
        dist_low = (close - low20) / close * 100.0
        expected_loss = min(8.0, dist_low) if dist_low > 0 else 8.0
        if dist_low <= 0:
            flags.append("at or below its 20 day low")
    else:
        expected_loss = 8.0
        flags.append("no 20 day low on file, full stop distance used")
    earn = earnings_rows.get(sym)
    if earn and earn["sessions_until"] <= 2:
        if "reaction" in (earn.get("note") or ""):
            flags.append("earnings inside 2 sessions, deliberate "
                         "reaction play (no penalty)")
        else:
            expected_gain -= EARNINGS_PENALTY
            flags.append("earnings inside 2 sessions (counts against)")
    ev = expected_gain - expected_loss
    return {"ticker": sym, "close": close,
            "expected_gain_pct": round(expected_gain, 2),
            "expected_loss_pct": round(expected_loss, 2),
            "ev_score": round(ev, 2), "heuristic_score": round(ev, 2),
            "calibrated": False, "score_kind": "uncalibrated heuristic", "flags": flags}


def build_odds(scan, specialists=None):
    earnings_rows = {r["ticker"]: r for r in earnings_bot.evaluate()}
    cands = _candidates(scan, specialists)
    rows = []
    for sym, c in cands.items():
        sdata = dict(c["scan"])
        try:
            candles = scanner.fetch_daily(sym)
            sdata["low_20d"] = min(cd["low"] for cd in candles[-20:])
        except Exception:  # noqa: BLE001
            sdata["low_20d"] = None
        row = score_candidate(sym, sdata, earnings_rows)
        row["sources"] = c["sources"]
        rows.append(row)
    rows.sort(key=lambda r: -r["ev_score"])
    return rows


def build_report(rows):
    lines = ["ODDS - heuristic opportunity ranking (estimates from volatility, "
             "not predictions; uncalibrated heuristic, not statistical expected profit)"]
    lines.append(f"  {'ticker':<7} {'close':>9} {'exp gain':>9} "
                 f"{'exp loss':>9} {'EV':>7}  sources / flags")
    for r in rows:
        flags = "; ".join(r["flags"])
        src = ", ".join(r["sources"])
        lines.append(f"  {r['ticker']:<7} {r['close']:>9,.2f} "
                     f"{r['expected_gain_pct']:>8.2f}% "
                     f"{r['expected_loss_pct']:>8.2f}% "
                     f"{r['ev_score']:>+7.2f}  {src}"
                     + (f" | {flags}" if flags else ""))
    if not rows:
        lines.append("  no candidates from any bot in the latest outputs")
    return "\n".join(lines)


def main():
    scan_path = os.path.join(HERE, "output", "scan-latest.json")
    with open(scan_path) as f:
        scan = json.load(f)
    spec_path = os.path.join(HERE, "output", "specialists-latest.json")
    specialists = None
    if os.path.exists(spec_path):
        with open(spec_path) as f:
            specialists = json.load(f)
    rows = build_odds(scan, specialists)
    print(build_report(rows))
    out = os.path.join(HERE, "output", "odds-latest.json")
    with open(out, "w") as f:
        json.dump(rows, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
