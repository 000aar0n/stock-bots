"""leaderboard.py - THE BOARD. Paper leaderboard for the bot city.

Decision bots log paper calls to output/calls.jsonl, one JSON object
per line: {bot, ts, ticker, side, qty_ref, entry_price, reason,
cause, source}. qty_ref is a fixed $10,000 reference size per call
so every bot is scored on the same basis (equal birth: same size,
same data, no starting rank). "cause" is the specific signal and
readings that fired (AETIOMORALISM: actions are judged by their
causes); until a bot passes structured readings separately, its
stated reason serves as its cause and log_call copies it over.
"source" is "live" (shadow/live session calls) or "backtest"
(arena calls, see arena.py). THE BOARD's official standings use
LIVE calls only; arena standings print separately, labeled. For an "exit" call, entry_price is the
price at the moment the exit was logged: it closes that bot's open
call on the ticker, or, if the bot has no open call there, the alert earns no trading P&L.
Repeated observations never count as completed trades.

THE BOARD marks open calls to the latest live close from the data
layer and prints the ranked table. It never places orders; it is a
scoreboard. Rankings start from Monday shadow mode: a bot earns its
rank, it is not assigned one.

Run: python3 leaderboard.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from contextvars import ContextVar
from contextlib import contextmanager
import math
import uuid
from storage import locked

HERE = os.path.dirname(os.path.abspath(__file__))
CALLS_PATH = os.path.join(HERE, "output", "calls.jsonl")

REF_SIZE = 10_000.0
STAFF = ["WICK", "HANDS", "REWIND", "COURIER", "HERALD", "SIREN",
         "TREASURER", "LEDGER", "ODDS", "TRIPWIRE", "THE BOARD"]
RANKED_KINDS_NOTE = "ranked: traders, specialists, snipers, strategists, pairs"


# ---------------------------------------------------------------- logging

PAPER_CONTEXT = ContextVar("paper_context", default={})
COMMISSION = 10.0
SLIPPAGE_BPS = 5.0  # explicit simulation assumption, not a measured fill cost


@contextmanager
def paper_context(**values):
    token = PAPER_CONTEXT.set({**PAPER_CONTEXT.get(), **values})
    try:
        yield
    finally:
        PAPER_CONTEXT.reset(token)


def log_call(bot, ticker, side, entry_price, reason, cause="",
             source=None, path=None, ts=None, bar_id=None):
    """Append a paper transition once. Never creates an HTMW execution.

    Duplicate entries while open and exits while flat are no-ops.
    A supplied bar_id also prevents close/reopen churn on one signal bar.
    """
    context = PAPER_CONTEXT.get()
    source = source or context.get("source", "live")
    path = path or context.get("path", CALLS_PATH)
    ts = ts or context.get("ts") or datetime.now(timezone.utc).isoformat()
    bar_id = bar_id or context.get("bar_id")
    price = float(entry_price)
    if source not in ("live", "backtest") or side not in ("buy", "short", "exit"):
        raise ValueError("invalid paper source or side")
    if not math.isfinite(price) or price <= 0:
        raise ValueError("paper price must be finite and positive")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with locked(path):
        calls = load_calls(path=path, source=source)
        own = [c for c in calls if c["bot"] == bot and c["ticker"] == ticker]
        key = (bot, ticker)
        if (side in ("buy", "short")) == (key in open_positions(own)):
            return None
        if bar_id and any(c.get("bar_id") == bar_id and c["side"] == side for c in own):
            return None
        rec = {"id": str(uuid.uuid4()), "bot": bot, "ts": ts,
               "ticker": ticker, "side": side, "qty_ref": REF_SIZE,
               "entry_price": price, "reason": reason, "cause": cause or reason,
               "source": source, "bar_id": bar_id}
        with open(path, "a") as handle:
            handle.write(json.dumps(rec, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return rec


def load_calls(path=None, source="context"):
    """Default reads are source-isolated; source=None explicitly reads all."""
    context = PAPER_CONTEXT.get()
    path = path or context.get("path", CALLS_PATH)
    if source == "context":
        source = context.get("source", "live")
    calls = []
    if not os.path.exists(path):
        return calls
    with open(path) as handle:
        for line in handle:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            # Fail visibly on corruption, rather than silently erasing evidence.
            row = json.loads(line)
            if source is None or row.get("source", "live") == source:
                calls.append(row)
    calls.sort(key=lambda c: c.get("ts", ""))
    return calls


def open_positions(calls):
    """Set of (bot, ticker) with an open long/short paper call."""
    opens = set()
    for c in calls:
        key = (c["bot"], c["ticker"])
        if c["side"] in ("buy", "short"):
            opens.add(key)
        elif c["side"] == "exit":
            opens.discard(key)
    return opens


# ---------------------------------------------------------------- scoring

def _ref_pnl(open_call, exit_price, closed=True):
    entry = open_call["entry_price"]
    if not entry or not math.isfinite(entry) or entry <= 0:
        return None
    shares = REF_SIZE / entry
    gross = shares * (entry - exit_price if open_call["side"] == "short"
                      else exit_price - entry)
    # Both sides incur modeled spread/slippage; open marks charge entry only.
    costs = COMMISSION + REF_SIZE * SLIPPAGE_BPS / 10_000
    if closed:
        costs += COMMISSION + shares * exit_price * SLIPPAGE_BPS / 10_000
    return gross - costs


def compute_standings(calls, price_fn=None):
    """Rank completed round trips, keeping unrealized marks separate.

    `calls` retains its API name but counts completed trades, not alerts.
    Orphan exits and repeated entries carry no profit or eligibility credit.
    """
    if price_fn is None:
        import scanner
        cache = {}
        def price_fn(ticker):
            if ticker not in cache:
                try:
                    cache[ticker] = scanner.fetch_daily(ticker)[-1]["close"]
                except Exception:
                    cache[ticker] = None
            return cache[ticker]
    opens, out, seen = {}, {}, set()
    for c in calls:
        bot = c["bot"]
        s = out.setdefault(bot, {"calls": 0, "alerts": 0, "scored": [],
                                "pnl": 0.0, "open_pnl": 0.0, "wins": 0,
                                "sessions": 0})
        identity = c.get("id") or (bot, c["ticker"], c["side"],
                                    c.get("ts"), c["entry_price"], c.get("source", "live"))
        if identity in seen:
            continue
        seen.add(identity)
        s["alerts"] += 1
        key = (bot, c["ticker"], c.get("source", "live"))
        if c["side"] in ("buy", "short"):
            opens.setdefault(key, c)
        elif c["side"] == "exit":
            op = opens.pop(key, None)
            if op is None:
                continue  # defensive alerts are observations, not imaginary trades
            pnl = _ref_pnl(op, c["entry_price"])
            if pnl is not None:
                s["scored"].append({"ticker": c["ticker"], "pnl": pnl,
                                    "kind": "closed", "entry_at": op.get("ts"),
                                    "exit_at": c.get("ts"), "source": key[2]})
    for (bot, ticker, _), op in opens.items():
        mark = price_fn(ticker)
        if mark is not None and math.isfinite(mark) and mark > 0:
            pnl = _ref_pnl(op, mark, closed=False)
            if pnl is not None:
                out[bot]["open_pnl"] += pnl
    for s in out.values():
        s["calls"] = len(s["scored"])
        s["pnl"] = sum(r["pnl"] for r in s["scored"])
        s["wins"] = sum(r["pnl"] > 0 for r in s["scored"])
        s["sessions"] = len({(r["exit_at"] or "")[:10] for r in s["scored"]})
    return out


def ranked_bots(standings):
    """Bots with standings, best paper P&L first, staff excluded."""
    rows = [(b, s) for b, s in standings.items() if b not in STAFF]
    rows.sort(key=lambda kv: -kv[1]["pnl"])
    return rows


MIN_PROVEN_CALLS = 20
MIN_PROVEN_SESSIONS = 5  # research eligibility, never proof of profitability


def split_sources(calls):
    """(live calls, backtest calls). Pre doctrine calls with no
    source field count as live."""
    live = [c for c in calls if c.get("source", "live") == "live"]
    arena = [c for c in calls if c.get("source") == "backtest"]
    return live, arena


def load_registry():
    path = os.path.join(HERE, "output", "bots.json")
    if not os.path.exists(path):
        return {"bots": []}
    with open(path) as f:
        return json.load(f)


def bot_record(bot, standings=None):
    """A bot's proven record in one phrase, for any quote of its
    signals (HERALD, JUDGE): its call count and paper P&L per
    call, or the word UNPROVEN. No naked authority."""
    if standings is None:
        live, _ = split_sources(load_calls())
        standings = compute_standings(live) if live else {}
    s = standings.get(bot)
    if not s or (s["calls"] < MIN_PROVEN_CALLS or s.get("sessions", 0) < MIN_PROVEN_SESSIONS):
        return "UNPROVEN"
    return (f"{s['calls']} calls, ${s['pnl'] / s['calls']:+,.2f} "
            f"paper P&L per call")


def active_call_mix(calls=None):
    """Open live paper calls split by the calling bot's registry
    hold_style: (intraday count, swing count). The city is day
    trader first; this keeps the mix visible."""
    if calls is None:
        calls, _ = split_sources(load_calls())
    hold = {b["name"]: b.get("hold_style", "intraday")
            for b in load_registry().get("bots", [])}
    intra = swing = 0
    for bot, _ticker in open_positions(calls):
        if hold.get(bot, "intraday") == "swing":
            swing += 1
        else:
            intra += 1
    return intra, swing


def _table(lines, standings, only_proven):
    rows_all = ranked_bots(standings)
    rows = [(b, s) for b, s in rows_all
            if (s["calls"] >= MIN_PROVEN_CALLS and s.get("sessions", 0) >= MIN_PROVEN_SESSIONS) == only_proven]
    if not rows:
        lines.append("  (none yet)")
        return lines
    lines.append(f"{'#':<3} {'bot':<22} {'calls':>5} {'scored':>6} "
                 f"{'win rate':>8} {'paper P&L':>11}  best / worst call")
    for i, (bot, s) in enumerate(rows, 1):
        rows_s = s["scored"]
        wr = (f"{100.0 * s['wins'] / len(rows_s):.0f}%"
              if rows_s else "n/a")
        best = max(rows_s, key=lambda r: r["pnl"]) if rows_s else None
        worst = min(rows_s, key=lambda r: r["pnl"]) if rows_s else None
        bw = ""
        if best and worst:
            bw = (f"{best['ticker']} ${best['pnl']:+,.0f} / "
                  f"{worst['ticker']} ${worst['pnl']:+,.0f}")
        lines.append(f"{i:<3} {bot:<22} {s['calls']:>5} {len(rows_s):>6} "
                     f"{wr:>8} {s['pnl']:>+11,.0f}  {bw}")
    return lines


def build_report(calls, standings, arena_standings=None):
    lines = ["THE BOARD - bot leaderboard (paper only, $10k reference "
             "size per trade; $10/order + 5bps/side modeled costs; never places orders)",
             "Official standings: completed LIVE paper trades only; open marks excluded from rank. Nothing is born "
             "superior; everything is equal until proven better."]
    if not calls:
        lines.append("")
        lines.append("No live calls yet. Rankings open Monday in shadow mode.")
        lines.append("A bot earns its rank, it is not assigned one.")
    else:
        lines.append("")
        lines.append("PROVEN (20+ completed live paper trades across 5+ sessions):")
        lines = _table(lines, standings, only_proven=True)
        lines.append("")
        lines.append("UNPROVEN (insufficient completed trades or sessions: listed apart, never "
                     "interleaved, protected from benching and breeding; "
                     "insufficient evidence is not failure):")
        lines = _table(lines, standings, only_proven=False)
        silent = [b["name"] for b in load_registry().get("bots", [])
                  if b.get("ranked") and b["name"] not in standings]
        if silent:
            lines.append(f"  plus {len(silent)} ranked bots with no live "
                         "calls yet (all UNPROVEN).")
    if arena_standings:
        lines.append("")
        lines.append("ARENA STANDINGS (backtest results from arena.py: "
                     "labeled arena production, NOT live rank; an arena "
                     "champion is not a live champion):")
        lines = _table(lines, arena_standings, only_proven=True)
        lines = _table(lines, arena_standings, only_proven=False)
    lines.append("")
    lines.append("Staff (unranked by design, not by failure): "
                 + ", ".join(STAFF[:-1]) + " and THE BOARD itself.")
    lines.append("Ranked bots: FALCON, JUDGE, SCALES, BOUNCER (scored on "
                 "losses avoided), the sector specialists, snipers, "
                 "strategists, pair bots and the handcrafted hundred.")
    return "\n".join(lines)


def main():
    calls = load_calls(source=None)
    live, arena = split_sources(calls)
    standings = compute_standings(live) if live else {}
    arena_standings = compute_standings(arena) if arena else {}
    print(build_report(live, standings, arena_standings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
