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
call on the ticker, or, if the bot has no open call there, the exit
is scored on its own as a defensive call (the move avoided versus
still holding, which counts negative if the name rises afterwards -
kept honest on purpose).

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
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CALLS_PATH = os.path.join(HERE, "output", "calls.jsonl")

REF_SIZE = 10_000.0
STAFF = ["WICK", "HANDS", "REWIND", "COURIER", "HERALD", "SIREN",
         "TREASURER", "LEDGER", "ODDS", "TRIPWIRE", "THE BOARD"]
RANKED_KINDS_NOTE = "ranked: traders, specialists, snipers, strategists, pairs"


# ---------------------------------------------------------------- logging

def log_call(bot, ticker, side, entry_price, reason, cause="",
             source="live", path=CALLS_PATH):
    """Append one paper call to calls.jsonl. Every call carries its
    cause (the signal and readings that fired) and its source:
    "live" for session calls, "backtest" for arena calls."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rec = {"bot": bot, "ts": datetime.now().isoformat(timespec="seconds"),
           "ticker": ticker, "side": side, "qty_ref": REF_SIZE,
           "entry_price": round(float(entry_price), 2), "reason": reason,
           "cause": cause or reason, "source": source}
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def load_calls(path=CALLS_PATH):
    calls = []
    if not os.path.exists(path):
        return calls
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                calls.append(json.loads(line))
            except json.JSONDecodeError:
                continue
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

def _ref_pnl(open_call, exit_price):
    entry = open_call["entry_price"]
    if not entry:
        return None
    shares = REF_SIZE / entry
    if open_call["side"] == "short":
        return shares * (entry - exit_price)
    return shares * (exit_price - entry)


def compute_standings(calls, price_fn=None):
    """Score all calls. price_fn(ticker) -> latest close or None.
    Returns {bot: {calls, scored: [{ticker, pnl, kind}], pnl}}."""
    if price_fn is None:
        import scanner  # lazy: data layer
        cache = {}

        def price_fn(ticker):
            if ticker not in cache:
                try:
                    cache[ticker] = scanner.fetch_daily(ticker)[-1]["close"]
                except Exception:  # noqa: BLE001
                    cache[ticker] = None
            return cache[ticker]

    opens = {}
    defensive = []
    scored = {}
    made = {}
    for c in calls:
        bot = c["bot"]
        made[bot] = made.get(bot, 0) + 1
        scored.setdefault(bot, [])
        key = (bot, c["ticker"])
        if c["side"] in ("buy", "short"):
            if key not in opens:
                opens[key] = c
        elif c["side"] == "exit":
            op = opens.pop(key, None)
            if op is not None:
                pnl = _ref_pnl(op, c["entry_price"])
                if pnl is not None:
                    scored[bot].append({"ticker": c["ticker"], "pnl": pnl,
                                        "kind": "closed"})
            else:
                defensive.append(c)
    for (bot, ticker), op in opens.items():
        mark = price_fn(ticker)
        if mark is None:
            continue
        pnl = _ref_pnl(op, mark)
        if pnl is not None:
            scored[bot].append({"ticker": ticker, "pnl": pnl, "kind": "open"})
    for c in defensive:
        mark = price_fn(c["ticker"])
        if mark is None or not c["entry_price"]:
            continue
        pnl = REF_SIZE * (c["entry_price"] - mark) / c["entry_price"]
        scored[c["bot"]].append({"ticker": c["ticker"], "pnl": pnl,
                                 "kind": "defensive"})
    out = {}
    for bot, n in made.items():
        rows = scored.get(bot, [])
        out[bot] = {
            "calls": n,
            "scored": rows,
            "pnl": sum(r["pnl"] for r in rows),
            "wins": sum(1 for r in rows if r["pnl"] > 0),
        }
    return out


def ranked_bots(standings):
    """Bots with standings, best paper P&L first, staff excluded."""
    rows = [(b, s) for b, s in standings.items() if b not in STAFF]
    rows.sort(key=lambda kv: -kv[1]["pnl"])
    return rows


MIN_PROVEN_CALLS = 5  # EQUALITY PROTOCOL: under 5 calls a bot is
# UNPROVEN, listed separately, never interleaved with proven
# standings, and DARWIN cannot bench or breed it: insufficient
# evidence is not failure.


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
    if not s or s["calls"] < MIN_PROVEN_CALLS:
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
            if (s["calls"] >= MIN_PROVEN_CALLS) == only_proven]
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
             "size per call, never places orders)",
             "Official standings: LIVE calls only. Nothing is born "
             "superior; everything is equal until proven better."]
    if not calls:
        lines.append("")
        lines.append("No live calls yet. Rankings open Monday in shadow mode.")
        lines.append("A bot earns its rank, it is not assigned one.")
    else:
        lines.append("")
        lines.append("PROVEN (5+ live calls):")
        lines = _table(lines, standings, only_proven=True)
        lines.append("")
        lines.append("UNPROVEN (under 5 live calls: listed apart, never "
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
    calls = load_calls()
    live, arena = split_sources(calls)
    standings = compute_standings(live) if live else {}
    arena_standings = compute_standings(arena) if arena else {}
    print(build_report(live, standings, arena_standings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
