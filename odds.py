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

SHORT SIDE (Tue Nov 3, 2026): ODDS also scores the short side.
Names with an open live short paper call (the short squad's logged
calls in output/calls.jsonl) get a side "short" row computed with
the mirrored math (strength below the averages counts FOR the
short; the cover stop and the 20 day high bound the loss). Before
this, ODDS only ever saw turning_up longs, so a short call could
never carry a positive EV into the allocator and the winning side
of the city could not trade.

SCOREBOARD WEIGHTING (Tue Nov 3, 2026): a candidate's ev_score is
adjusted by the completed live record of the bot(s) behind it
(bot_records / record_for_sources below). Proven winners (3+
completed live trades, positive aggregate paper P&L) lift their
names; proven losers sink theirs below unproven names; unproven
sources adjust nothing. The adjustment is capped at
RECORD_EV_CAP points, it only re-ranks - it never blocks a name
and never touches BOUNCER or the caps - and the raw heuristic
stays on the row as heuristic_score.

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


def score_candidate(sym, sdata, earnings_rows, side="long"):
    """Heuristic ranking for one candidate. This is not measured expected profit.

    side "short" mirrors the math: trading below the averages is
    the short's momentum, a falling live move counts for it, and
    its loss is bounded by the nearer of the +8% cover stop and
    the 20 day high (the squeeze proxy)."""
    t = sdata.get("ta") or {}
    close = sdata["last_close"]
    atr_pct = (t["atr14"] / close * 100.0) if t.get("atr14") and close else 0.0
    lat = sdata.get("latency") or {}
    is_latency = bool(lat.get("candidate"))
    live_move = lat["move_pct"] if is_latency and lat.get("move_pct") \
        is not None else (sdata.get("chg_1d_pct") or 0.0)
    dist20 = ((close / t["sma20"] - 1.0) * 100.0) if t.get("sma20") else 0.0
    dist50 = ((close / t["sma50"] - 1.0) * 100.0) if t.get("sma50") else 0.0
    rsi = t.get("rsi14")
    flags = []
    if side == "short":
        momentum = -(0.5 * dist20 + 0.5 * dist50)
        if rsi is not None:
            if 30 <= rsi <= 50:
                momentum += 0.5
            elif rsi < 25:
                momentum -= 1.0  # capitulation: bounce risk
                flags.append("deeply oversold, bounce risk for a short")
            elif rsi > 80:
                momentum -= 0.5
        rel_vol = t.get("rel_volume")
        if rel_vol is not None and rel_vol >= 1.5:
            momentum += 0.5
        expected_gain = atr_pct + max(0.0, momentum) \
            + 0.5 * max(0.0, -live_move)
        # Loss side for a short: nearer of the +8% cover stop and
        # the 20 day high.
        high20 = sdata.get("high_20d")
        if high20:
            dist_high = (high20 - close) / close * 100.0
            expected_loss = min(8.0, dist_high) if dist_high > 0 else 8.0
            if dist_high <= 0:
                flags.append("at or above its 20 day high")
        else:
            expected_loss = 8.0
            flags.append("no 20 day high on file, full stop distance used")
    else:
        momentum = 0.5 * dist20 + 0.5 * dist50
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
    return {"ticker": sym, "close": close, "side": side,
            "expected_gain_pct": round(expected_gain, 2),
            "expected_loss_pct": round(expected_loss, 2),
            "ev_score": round(ev, 2), "heuristic_score": round(ev, 2),
            "calibrated": False, "score_kind": "uncalibrated heuristic", "flags": flags}


# ------------------------------------------------------- scoreboard records

RECORD_MIN_CALLS = 3      # completed live trades before a record counts
RECORD_EV_CAP = 1.5       # max EV points the record may add or remove
RECORD_EV_SCALE = 50.0    # $ of paper P&L per call per EV point


def bot_records(price_fn=None):
    """Completed live records per bot from THE BOARD's standings:
    {bot: {"tier": 1|0|-1, "ev_adj": float, "calls": n, "pnl": $}}.
    Only bots with RECORD_MIN_CALLS or more completed live trades
    appear; everyone else is unproven and adjusts nothing. Never
    raises: a missing or unreadable call log means no records."""
    try:
        import leaderboard
        calls = leaderboard.load_calls(source="live")
        if price_fn is None:
            def price_fn(ticker, _cache={}):
                if ticker not in _cache:
                    try:
                        _cache[ticker] = scanner.fetch_daily(
                            ticker)[-1]["close"]
                    except Exception:  # noqa: BLE001
                        _cache[ticker] = None
                return _cache[ticker]
        standings = leaderboard.compute_standings(calls, price_fn=price_fn)
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for bot, s in standings.items():
        n = s.get("calls", 0)
        if n < RECORD_MIN_CALLS:
            continue
        pnl = s.get("pnl", 0.0)
        tier = 1 if pnl > 0 else (-1 if pnl < 0 else 0)
        adj = max(-RECORD_EV_CAP,
                  min(RECORD_EV_CAP, (pnl / n) / RECORD_EV_SCALE))
        out[bot] = {"tier": tier, "ev_adj": round(adj, 2),
                    "calls": n, "pnl": round(pnl, 2)}
    return out


def record_for_sources(records, sources):
    """The (tier, ev_adj) a candidate inherits from the bot(s)
    behind it. A proven winner source lifts it, a proven loser
    source sinks it, a mix cancels to unproven, and sources with
    no record contribute nothing."""
    recs = [records[s] for s in (sources or []) if s in records]
    if not recs:
        return 0, 0.0
    winners = [r for r in recs if r["tier"] > 0]
    losers = [r for r in recs if r["tier"] < 0]
    if winners and not losers:
        tier = 1
    elif losers and not winners:
        tier = -1
    else:
        tier = 0
    adj = round(sum(r["ev_adj"] for r in recs) / len(recs), 2)
    return tier, adj


def _short_call_sources():
    """Open live short paper calls by ticker: {ticker: [bot, ...]}.
    This is the short squad's logged work; before Nov 3, 2026 no
    part of the gate ever read it. Never raises."""
    try:
        import leaderboard
        state = {}
        for c in leaderboard.load_calls(source="live"):
            key = (c["bot"], c["ticker"])
            if c["side"] in ("buy", "short"):
                state[key] = c["side"]
            elif c["side"] == "exit":
                state.pop(key, None)
        by_ticker = {}
        for (bot, ticker), side in state.items():
            if side == "short":
                by_ticker.setdefault(ticker, []).append(bot)
        return by_ticker
    except Exception:  # noqa: BLE001
        return {}


def build_odds(scan, specialists=None, records=None):
    earnings_rows = {r["ticker"]: r for r in earnings_bot.evaluate()}
    if records is None:
        syms0 = scan.get("symbols", {})
        records = bot_records(
            price_fn=lambda t: (syms0.get(t) or {}).get("last_close"))
    cands = _candidates(scan, specialists)
    rows = []
    for sym, c in cands.items():
        sdata = dict(c["scan"])
        try:
            candles = scanner.fetch_daily(sym)
            sdata["low_20d"] = min(cd["low"] for cd in candles[-20:])
            sdata["high_20d"] = max(cd["high"] for cd in candles[-20:])
        except Exception:  # noqa: BLE001
            sdata["low_20d"] = None
            sdata["high_20d"] = None
        row = score_candidate(sym, sdata, earnings_rows)
        row["sources"] = c["sources"]
        rows.append(row)
    # Short side: every name a bot is currently short on paper gets
    # a mirrored score, sourced by the bots holding the call.
    syms = scan.get("symbols", {})
    for sym, bots in sorted(_short_call_sources().items()):
        if sym not in syms:
            continue
        sdata = dict(syms[sym])
        try:
            candles = scanner.fetch_daily(sym)
            sdata["low_20d"] = min(cd["low"] for cd in candles[-20:])
            sdata["high_20d"] = max(cd["high"] for cd in candles[-20:])
        except Exception:  # noqa: BLE001
            sdata["low_20d"] = None
            sdata["high_20d"] = None
        row = score_candidate(sym, sdata, earnings_rows, side="short")
        row["sources"] = sorted(bots)
        rows.append(row)
    # Scoreboard weighting: the record of the source bot(s) moves
    # ev_score within the cap; heuristic_score keeps the raw value.
    for row in rows:
        tier, adj = record_for_sources(records, row.get("sources"))
        row["record_tier"] = tier
        row["record_ev_adj"] = adj
        if adj:
            row["ev_score"] = round(row["ev_score"] + adj, 2)
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
        side = " SHORT" if r.get("side") == "short" else ""
        rec = (f" | record tier {r['record_tier']:+d} "
               f"(EV adj {r['record_ev_adj']:+.2f})"
               if r.get("record_tier") or r.get("record_ev_adj") else "")
        lines.append(f"  {r['ticker']:<7} {r['close']:>9,.2f} "
                     f"{r['expected_gain_pct']:>8.2f}% "
                     f"{r['expected_loss_pct']:>8.2f}% "
                     f"{r['ev_score']:>+7.2f}  {src}{side}"
                     + (f" | {flags}" if flags else "") + rec)
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
