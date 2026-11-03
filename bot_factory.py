"""bot_factory.py - the bot factory. Registry plus runner for the city.

Data driven: bot instances are generated from config axes (staff,
specialists, snipers, strategists, pair bots, thermometers, and the
coverage pairs) and written to output/bots.json. Every bot record
has: name, kind, watchlist, strategy, timeframe, ranked, benched.

COVERAGE RULE: no stock and no group is watched by fewer than two
bots, ever. Every ticker in the wide universe gets a WATCHER (daily
candles, momentum logic) and a SHADOW (independent second opinion:
5 minute candle TA when intraday data exists, otherwise a daily
mean reversion strategy, a genuinely different code path). When
WATCHER and SHADOW disagree on a name (one says entry, the other
says falling knife), the digest prints a CONTESTED line and neither
logs a call. The rule exists because single source numbers burned
us before (phantom fills, wrong interim batches).

The runner (--run) executes every registered bot's signal logic
against the shared data layer (one fetch per symbol, cached and
shared across bots), prints a digest (only bots with something to
say get a line), and, with --log-calls, appends paper calls to
output/calls.jsonl under each bot's own name for THE BOARD.
Thermometers never trade; they print market regime and write
output/thermometers.json, which JUDGE and HERALD quote.

Seasons: --cull benches the bottom 10 percent of ranked bots by
paper P&L once at least 20 ranked calls exist (before that it
refuses). Top bots' configs get cloned with small variations over
time; cloning is manual for now (see README).

Sessions run the whole population with --snapshot FILE: the
verified account snapshot is loaded and handed to the digest run
through the leaderboard paper context (the same account_snapshot
run_city.py supplies), so every bot in the run sees the same
verified book the rest of the suite (JUDGE, BOUNCER, TREASURER)
already read. Market data comes from the shared scanner data
layer, one fetch per symbol, same as the standalone scan.

Run: python3 bot_factory.py [--run] [--log-calls] [--cull]
     [--snapshot FILE]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date, datetime

import arb_monitor
import scanner
import specialists
import ta

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(HERE, "output", "bots.json")
THERMO_PATH = os.path.join(HERE, "output", "thermometers.json")

STAFF_DEFS = [
    ("FALCON", "whole market scan, daily candles"),
    ("WICK", "candlestick and indicator library"),
    ("JUDGE", "Protected Momentum rules engine"),
    ("HANDS", "HTMW web client, dry run"),
    ("BOUNCER", "independent risk watchdog"),
    ("SCALES", "stat arb pair tracker"),
    ("SIREN", "earnings calendar warnings"),
    ("REWIND", "historical backtester"),
    ("COURIER", "tracker packet builder"),
    ("HERALD", "end of day summary"),
    ("TREASURER", "budget proposer (allocator)"),
    ("LEDGER", "budget verifier (allocator)"),
    ("ODDS", "expected value projector"),
    ("TRIPWIRE", "intraday speed alerts"),
    ("THE BOARD", "paper leaderboard"),
]
STRATEGIES = {
    "MOMENTUM": "trend following: buy turning_up above SMA50",
    "BREAKOUT": "buy new 20 day highs on expanding relative volume",
    "DIP": "mean reversion: buy RSI under 35 with a bullish reversal candle",
    "GHOST": "latency hunter: only calls stale price candidates",
}

# RIVAL bots (Aaron, Sat Oct 31): every covered name gets competing
# brains beyond its WATCHER (daily momentum) and SHADOW (5 minute /
# mean reversion). RAIDER and ANCHOR use different logic and
# different parameters from each other and from the sector
# strategists, on purpose:
RIVALS = {
    "RAIDER": "breakout rival: entry when the close takes out the "
              "prior 10 day high with relative volume at or above "
              "1.3 and RSI under 75 (chasing strength, not climax); "
              "exit on falling_knife",
    "ANCHOR": "mean reversion rival: entry when the close sits at "
              "least 1.2 ATR below its SMA20 with RSI at or under 42 "
              "and a green reversal day (a stretch snap back, looser "
              "and earlier than DIP); exit on falling_knife",
}

# High beta names outside the core 20 that still get a SNIPER.
SNIPER_EXTRA = ["OKLO", "SMR", "NNE", "RIOT", "IONQ", "RKLB", "SMCI",
                "HOOD"]

# SECTION CAPTAINS (Aaron, Sat Oct 31): one captain per sector
# patch plus one for the stat arb pairs. Patch bots report to their
# captain; captains aggregate, pre rank by proven record (or
# UNPROVEN), flag CONTESTED names inside the section, and escalate
# only the best qualifying calls to JUDGE. Captains are bots:
# born equal, ranked on THE BOARD by the outcomes of the calls
# they escalate (escalation quality is their mandate).
CAPTAINS = {
    "CAPTAIN CIRCUIT": "CIRCUIT",
    "CAPTAIN STACK": "STACK",
    "CAPTAIN SATOSHI": "SATOSHI",
    "CAPTAIN REACTOR": "REACTOR",
    "CAPTAIN PULSE": "PULSE",
    "CAPTAIN AEGIS": "AEGIS",
    "CAPTAIN CART": "CART",
    "CAPTAIN VAULT": "VAULT",
    "CAPTAIN ROCKET": "ROCKET",
    "CAPTAIN PAIRS": "PAIRS",
}

JUDGE_TOMBSTONE = os.path.join(HERE, "output", "judge_deleted.json")


def judge_is_deleted():
    """JUDGE was deleted by a season review verdict (judge_scorecard).
    Deletion is final: the factory never re-mints JUDGE afterwards."""
    return os.path.exists(JUDGE_TOMBSTONE)
THERMO_TICKERS = ["SPY", "QQQ", "IWM", "DIA"]

# Handcrafted bots (Phase 7): individually written craftsmen in
# handcrafted/, one file each, NOT factory parameter clones. The
# roster lives in handcrafted/roster.json (human version:
# handcrafted/ROSTER.md) and is loaded below so regeneration keeps
# every finished craftsman. kind "handcrafted", gen 1. DARWIN has
# NO exemption for them (Aaron's override): they breed and can be
# benched under the same thresholds as factory bots.


def universe_tickers():
    seen = []
    for tickers in scanner.UNIVERSE.values():
        for t in tickers:
            if t not in seen:
                seen.append(t)
    return seen


def build_registry():
    bots = []

    def add(name, kind, watchlist, strategy, timeframe, ranked):
        # EQUALITY PROTOCOL: every bot is born equal: born_equal
        # true, fitness null (unproven, not zero), same $10k
        # reference size and data access as everyone else.
        hold = ("swing" if kind == "pair"
                else "none" if kind in ("staff", "thermometer", "captain")
                else "intraday")
        bots.append({"name": name, "kind": kind, "watchlist": watchlist,
                     "strategy": strategy, "timeframe": timeframe,
                     "ranked": ranked, "benched": False,
                     "born_equal": True, "fitness": None,
                     "hold_style": hold})

    for name, role in STAFF_DEFS:
        if name == "JUDGE" and judge_is_deleted():
            continue  # deleted by verdict; never re-minted (final)
        add(name, "staff", [], role, "n/a", False)
    import earnings_bot  # lazy: FLASH's watchlist is the calendar
    roster_path = os.path.join(HERE, "handcrafted", "roster.json")
    try:
        with open(roster_path) as f:
            roster = json.load(f)
    except Exception:  # noqa: BLE001
        roster = []
    for entry in roster:
        watch = entry.get("watchlist", [])
        if watch == "CORE":
            watch = list(scanner.CORE_INTRADAY)
        elif watch == "UNIVERSE":
            watch = universe_tickers()
        elif watch == "CALENDAR":
            watch = sorted(earnings_bot.CALENDAR)
        bots.append({"name": entry["name"], "kind": "handcrafted",
                     "watchlist": watch,
                     "strategy": entry.get("strategy", ""),
                     "timeframe": entry.get("timeframe", "daily"),
                     "ranked": entry.get("ranked", True),
                     "benched": False, "gen": 1,
                     "born_equal": True, "fitness": None,
                     "hold_style": entry.get(
                         "hold", "none" if not entry.get("ranked", True)
                         else "intraday")})
    for name, cfg in specialists.SPECIALISTS.items():
        add(name, "specialist", cfg["tickers"],
            f"{cfg['sector']}: turning_up entries, falling_knife exits",
            "daily", True)
    for t in scanner.CORE_INTRADAY:
        add(f"{t} SNIPER", "sniper", [t],
            "single name: entries on turning_up plus latency windows, "
            "exits on falling_knife or the -8% rule", "daily+5m", True)
    for t in SNIPER_EXTRA:
        if t in scanner.CORE_INTRADAY:
            continue
        add(f"{t} SNIPER", "sniper", [t],
            "single name, high beta variant: entries on turning_up "
            "plus latency windows, exits on falling_knife or the "
            "-8% rule", "daily+5m", True)
    for sector, cfg in specialists.SPECIALISTS.items():
        for strat, desc in STRATEGIES.items():
            add(f"{sector} {strat}", "strategist", cfg["tickers"], desc,
                "daily+latency" if strat == "GHOST" else "daily", True)
    for a, b in scanner.PAIRS:
        add(f"PAIR {a} {b}", "pair", [a, b],
            "stat arb: call the pair at a 10 point gap or more when "
            "eligibility allows (PAPER ONLY when the news check is "
            "still manual)", "daily", True)
    for t in THERMO_TICKERS:
        add(f"{t} THERMOMETER", "thermometer", [t],
            "market regime only, never trades", "daily", False)
    for t in universe_tickers():
        add(f"{t} WATCHER", "watcher", [t],
            "daily momentum: turning_up entry, falling_knife flag",
            "daily", True)
        add(f"{t} SHADOW", "shadow", [t],
            "independent second opinion: 5 minute TA when intraday "
            "exists, else daily mean reversion", "5m/daily", True)
        for rival, desc in RIVALS.items():
            add(f"{t} {rival}", "rival", [t], desc, "daily", True)
    for cap_name, section in CAPTAINS.items():
        if section == "PAIRS":
            watch = [t for pair in scanner.PAIRS for t in pair]
            desc = ("stat arb section captain: aggregates the PAIR "
                    "bots, pre ranks their gap calls by proven record "
                    "or UNPROVEN, flags contested legs, escalates only "
                    "the best qualifying pair calls to JUDGE")
        else:
            watch = specialists.SPECIALISTS[section]["tickers"]
            desc = (f"section captain for {section} "
                    f"({specialists.SPECIALISTS[section]['sector']}): "
                    "aggregates the patch bots' calls, pre ranks by "
                    "proven record or UNPROVEN, flags CONTESTED names "
                    "in the section, escalates only the best "
                    "qualifying calls to JUDGE")
        add(cap_name, "captain", watch, desc, "daily", True)

    # Preserve bench flags across regenerations, and carry over
    # DARWIN offspring (records with a "parent" field, written by
    # evolution.py --apply) that the factory does not regenerate.
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH) as f:
                old = {b["name"]: b for b in json.load(f)["bots"]}
            for b in bots:
                if old.get(b["name"], {}).get("benched"):
                    b["benched"] = True
            new_names = {b["name"] for b in bots}
            for name, rec in old.items():
                if rec.get("parent") and name not in new_names:
                    bots.append(rec)
        except Exception:  # noqa: BLE001
            pass
    counts = {}
    for b in bots:
        counts[b["kind"]] = counts.get(b["kind"], 0) + 1
    registry = {"generated_at": datetime.now().isoformat(timespec="seconds"),
                "count": len(bots), "counts_by_kind": counts, "bots": bots}
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    from storage import atomic_json
    atomic_json(REGISTRY_PATH, registry)
    return registry


# ---------------------------------------------------------------- data layer

class DataCache:
    """One fetch per symbol, shared by every bot in the run."""

    def __init__(self):
        self._daily, self._intra = {}, {}
        self.errors = {}

    def daily(self, sym):
        if sym not in self._daily:
            try:
                self._daily[sym] = scanner.fetch_daily(sym)
            except Exception as e:  # noqa: BLE001
                self.errors[sym] = str(e)
                self._daily[sym] = None
        return self._daily[sym]

    def intra(self, sym):
        if sym not in self._intra:
            try:
                self._intra[sym] = scanner.fetch_intraday_candles(sym)
            except Exception:  # noqa: BLE001
                self._intra[sym] = None
        return self._intra[sym]

    def daily_ta(self, sym):
        c = self.daily(sym)
        return ta.analyze(c) if c else None

    def intra_ta(self, sym):
        c = self.intra(sym)
        return ta.analyze(c) if c else None

    def last_close(self, sym):
        c = self.daily(sym)
        return c[-1]["close"] if c else None

    def latency(self, sym):
        c = self.daily(sym)
        if not c:
            return {"candidate": False}
        closes = [x["close"] for x in c]
        sdata = {"last_close": round(closes[-1], 2),
                 "chg_1d_pct": round(scanner.pct(closes[-1], closes[-2]), 2)}
        return scanner.latency_check(sym, sdata, candles=self.intra(sym))


def shadow_view(cache, sym):
    """SHADOW's independent opinion: 5 minute TA when intraday
    exists, else daily mean reversion (RSI under 35 plus a bullish
    reversal candle). A different code path from WATCHER on purpose."""
    ita = cache.intra_ta(sym)
    if ita is not None:
        return {"entry": ita["turning_up"], "flag": ita["falling_knife"],
                "basis": "5m"}
    dta = cache.daily_ta(sym)
    if dta is None:
        return {"entry": False, "flag": False, "basis": "none"}
    bullish = any(p in ta.BULLISH_PATTERNS for p in dta["patterns"])
    entry = bool(dta["rsi14"] is not None and dta["rsi14"] <= 35 and bullish)
    return {"entry": entry, "flag": dta["falling_knife"],
            "basis": "daily mean reversion"}


SAME_DAY_EXIT_MIN_ADVERSE_PCT = 3.0


def _exit_blocked_same_day(entry, exit_price, today=None):
    """True when a falling knife exit would churn a position opened
    today. Review evidence (Tue Nov 3, 2026): the SNIPER family
    closed 65 paper round trips for -$3,328.77, most at exactly -$30
    per trade (modeled costs only), because a 5 minute falling_knife
    flag fired minutes after a 5 minute turning_up entry and closed
    the trade at the entry price; SHADOW showed the same pattern
    (-$8,364.06 over 93 completed). A knife exit on a same day entry
    now needs a real adverse move (>= 3% against the entry, on the
    way to the -8% stop); positions held overnight exit freely, and
    an exit with no logged entry is never blocked by this guard."""
    if not entry or not exit_price:
        return False
    ts = str(entry.get("ts") or "")
    if ts[:10] != (today or date.today()).isoformat():
        return False
    entry_price = entry.get("entry_price")
    if not entry_price:
        return False
    if entry.get("side") == "short":
        adverse = (exit_price / entry_price - 1.0) * 100.0
    else:
        adverse = (entry_price - exit_price) / entry_price * 100.0
    return adverse < SAME_DAY_EXIT_MIN_ADVERSE_PCT


# Families whose bots log entries in the digest but grew no exit
# code of their own (Tue Nov 3, 2026): specialists, strategists and
# captains logged buys only, and watcher / rival exits leaned on a
# single daily falling_knife flag diluted by watcher/shadow cross
# suppression - so whole families sat at zero completed trades
# while holding dozens of open paper positions. The sweep below
# gives every one of them the city's standing Protected Momentum
# exits, evaluated on the real current price: the -8% adverse stop
# from the logged entry, two straight closes against the position
# with pre-entry closes excluded (only closes dated on or after
# the entry count, the Mon Nov 2 entry date fix), and the daily
# falling_knife flag. Exits log at the real last close from the
# cache, never at invented prices, and the same day churn guard in
# maybe_call still applies to every exit the sweep requests.
SWEEP_EXIT_KINDS = ("watcher", "rival", "sniper", "specialist",
                    "strategist", "captain")


def _position_exit_reason(entry, cache, ticker):
    """Why an open paper position should close now, or None.
    entry is the open position record (side, entry_price, ts)."""
    price = cache.last_close(ticker)
    entry_price = entry.get("entry_price")
    if price is None or not entry_price:
        return None
    side = entry.get("side") or "buy"
    adverse = ((entry_price - price) / entry_price * 100.0) \
        if side != "short" else ((price - entry_price) / entry_price * 100.0)
    if adverse >= 8.0:
        return f"{'stop' if side != 'short' else 'cover stop'}: " \
               f"{adverse:.1f}% adverse from the logged entry " \
               "(Protected Momentum -8% exit)"
    try:
        candles = cache.daily(ticker)
    except Exception:  # noqa: BLE001
        candles = None
    if candles:
        entry_date = str(entry.get("ts") or "")[:10]
        dated = [(c.get("date"), c.get("close")) for c in candles
                 if c.get("close") is not None]
        # Two straight closes against the position, counting only
        # closes dated on or after the entry (pre-entry closes
        # never count). The first eligible close needs the close
        # before it as its comparison base.
        for i in range(2, len(dated)):
            if entry_date and dated[i - 1][0] and \
                    dated[i - 1][0] < entry_date:
                continue
            a, b, c_ = dated[i - 2][1], dated[i - 1][1], dated[i][1]
            if side != "short" and c_ < b < a:
                return "two straight red closes while held " \
                       "(Protected Momentum exit)"
            if side == "short" and c_ > b > a:
                return "two straight green closes while held " \
                       "(Protected Momentum cover)"
    try:
        dta = cache.daily_ta(ticker)
    except Exception:  # noqa: BLE001
        dta = None
    if dta and dta.get("falling_knife"):
        return "falling_knife on daily candles"
    return None


def _sweep_family_exits(bots_by_name, open_info, cache, call_fn):
    """Request exits for open positions held by the exit-less
    families. call_fn(bot_name, ticker, 'exit', price, reason) does
    the logging (maybe_call in production, which logs at the real
    intraday last close and pops open_info when the exit lands).
    An exit counts as landed when the position leaves open_info.
    Returns digest lines."""
    lines = []
    for (bot_name, ticker), entry in list(open_info.items()):
        bot = bots_by_name.get(bot_name)
        if bot is None or bot.get("kind") not in SWEEP_EXIT_KINDS:
            continue
        if bot.get("benched"):
            continue
        reason = _position_exit_reason(entry, cache, ticker)
        if not reason:
            continue
        price = cache.last_close(ticker)
        call_fn(bot_name, ticker, "exit", price,
                f"{bot_name}: family exit sweep - {reason}")
        if (bot_name, ticker) not in open_info:
            lines.append(f"  {bot_name} closes {ticker} "
                         f"({reason})")
    return lines


# ---------------------------------------------------------------- runner

def run_digest(registry, log_calls=False):
    cache = DataCache()
    bots = {b["name"]: b for b in registry["bots"]}
    active = [b for b in registry["bots"] if not b["benched"]]
    opens = set()
    open_info = {}
    if log_calls:
        from leaderboard import load_calls, open_positions
        all_calls = load_calls()
        opens = open_positions(all_calls)
        for c in all_calls:
            key = (c["bot"], c["ticker"])
            if c["side"] in ("buy", "short"):
                open_info[key] = c
            elif c["side"] == "exit":
                open_info.pop(key, None)
    lines = []
    calls_made = [0]

    def maybe_call(bot, ticker, side, price, reason):
        if not log_calls or price is None:
            return
        from leaderboard import log_call
        key = (bot, ticker)
        if side in ("buy", "short") and key in opens:
            return
        record = bots.get(bot, {})
        if record.get("benched"):
            return
        bars = cache.intra(ticker)
        if not bars:
            return
        if side == "exit" and _exit_blocked_same_day(
                open_info.get(key), bars[-1]["close"]):
            return
        saved = log_call(bot, ticker, side, bars[-1]["close"], reason, bar_id=str(bars[-1]["ts"]))
        if saved is None:
            return
        calls_made[0] += 1
        if side in ("buy", "short"):
            opens.add(key)
            open_info[key] = {"entry_price": bars[-1]["close"],
                              "ts": datetime.now().isoformat(),
                              "side": side}
        else:
            opens.discard(key)
            open_info.pop(key, None)

    # Thermometers first: regime context for everyone else.
    core = scanner.CORE_INTRADAY
    above = 0
    for t in core:
        c = cache.daily(t)
        if c:
            closes = [x["close"] for x in c]
            s50 = ta.sma(closes, 50)
            if s50 and closes[-1] > s50:
                above += 1
    breadth = 100.0 * above / len(core) if core else 0.0
    thermos = {}
    for t in THERMO_TICKERS:
        bot = bots.get(f"{t} THERMOMETER")
        if bot and bot["benched"]:
            continue
        c = cache.daily(t)
        if not c:
            continue
        closes = [x["close"] for x in c]
        s50 = ta.sma(closes, 50)
        over = s50 and closes[-1] > s50
        if over and breadth >= 60:
            regime = "risk on"
        elif not over and breadth <= 40:
            regime = "risk off"
        else:
            regime = "choppy"
        detail = (f"{t} {'above' if over else 'below'} its 50 day average, "
                  f"core list breadth {breadth:.0f}% above theirs")
        thermos[t] = {"regime": regime, "detail": detail}
        lines.append(f"{t} THERMOMETER: {regime} - {detail}")
    with open(THERMO_PATH, "w") as f:
        json.dump(thermos, f, indent=1)

    contested_tickers = set()
    section_signals = {}  # sector -> [(ticker, source bot, price)]
    pair_signals = []     # [(ticker, source bot, price)]

    # Coverage pairs: WATCHER vs SHADOW per ticker.
    for t in universe_tickers():
        wname, sname = f"{t} WATCHER", f"{t} SHADOW"
        if bots.get(wname, {}).get("benched") and bots.get(sname, {}).get("benched"):
            continue
        dta = cache.daily_ta(t)
        if dta is None:
            continue
        w_entry, w_flag = dta["turning_up"], dta["falling_knife"]
        sv = shadow_view(cache, t)
        price = cache.last_close(t)
        contested = (w_entry and sv["flag"]) or (sv["entry"] and w_flag)
        if contested:
            contested_tickers.add(t)
            lines.append(
                f"CONTESTED {t}: WATCHER says "
                f"{'entry' if w_entry else 'falling knife'}, SHADOW says "
                f"{'entry' if sv['entry'] else 'falling knife'} "
                f"({sv['basis']}) - no call from either")
            continue
        parts = []
        if w_entry:
            parts.append("WATCHER entry")
            maybe_call(wname, t, "buy", price,
                       "WATCHER: turning_up on daily candles")
        if w_flag:
            parts.append("WATCHER falling knife")
            maybe_call(wname, t, "exit", price,
                       "WATCHER: falling_knife on daily candles")
        if sv["entry"]:
            parts.append(f"SHADOW entry ({sv['basis']})")
            maybe_call(sname, t, "buy", price,
                       f"SHADOW: entry on {sv['basis']}")
        if sv["flag"]:
            parts.append(f"SHADOW falling knife ({sv['basis']})")
            maybe_call(sname, t, "exit", price,
                       f"SHADOW: falling knife on {sv['basis']}")
        if parts:
            lines.append(f"{t}: " + "; ".join(parts))

    # Snipers on the core 20 plus the high beta extras.
    for t in list(core) + [x for x in SNIPER_EXTRA if x not in core]:
        name = f"{t} SNIPER"
        if bots.get(name, {}).get("benched"):
            continue
        dta, ita = cache.daily_ta(t), cache.intra_ta(t)
        if dta is None:
            continue
        lat = cache.latency(t)
        entry = dta["turning_up"] or (ita and ita["turning_up"])
        flag = dta["falling_knife"] or (ita and ita["falling_knife"])
        price = cache.last_close(t)
        if entry or flag or lat.get("candidate"):
            bits = []
            if entry:
                bits.append("entry signal")
                maybe_call(name, t, "buy", price,
                           "SNIPER: turning_up"
                           + (" with a latency window open"
                              if lat.get("candidate") else ""))
            if flag:
                bits.append("falling knife")
                maybe_call(name, t, "exit", price, "SNIPER: falling_knife")
            if lat.get("candidate"):
                bits.append(f"latency candidate {lat['move_pct']:+.2f}%")
            lines.append(f"{name}: " + "; ".join(bits))

    # Specialists and strategists per sector.
    for sector, cfg in specialists.SPECIALISTS.items():
        rows = {}
        for t in cfg["tickers"]:
            dta = cache.daily_ta(t)
            if dta:
                rows[t] = dta
        spec = bots.get(sector)
        if spec and not spec["benched"]:
            ups = [t for t, d in rows.items()
                   if d["turning_up"] and not d["falling_knife"]]
            if ups:
                lines.append(f"{sector} (specialist): turning up "
                             + ", ".join(ups))
                for t in ups:
                    price = cache.last_close(t)
                    maybe_call(sector, t, "buy", price,
                               f"{sector} specialist: turning_up")
                    section_signals.setdefault(sector, []).append(
                        (t, sector, price))
        for strat in STRATEGIES:
            name = f"{sector} {strat}"
            bot = bots.get(name)
            if not bot or bot["benched"]:
                continue
            hits = []
            for t, d in rows.items():
                c = cache.daily(t)
                closes = [x["close"] for x in c]
                if strat == "MOMENTUM":
                    hit = d["turning_up"] and d["sma50"] \
                        and closes[-1] > d["sma50"]
                elif strat == "BREAKOUT":
                    hit = len(closes) > 21 \
                        and closes[-1] > max(closes[-21:-1]) \
                        and (d["rel_volume"] or 0) >= 1.5
                elif strat == "DIP":
                    hit = d["rsi14"] is not None and d["rsi14"] <= 35 \
                        and any(p in ta.BULLISH_PATTERNS
                                for p in d["patterns"])
                else:  # GHOST
                    hit = cache.latency(t).get("candidate", False)
                if hit:
                    hits.append(t)
            if hits:
                lines.append(f"{name}: signals on " + ", ".join(hits))
                for t in hits:
                    price = cache.last_close(t)
                    maybe_call(name, t, "buy", price,
                               f"{name}: {STRATEGIES[strat]}")
                    section_signals.setdefault(sector, []).append(
                        (t, name, price))

    # Pair bots.
    today = date.today()
    for a, b in scanner.PAIRS:
        name = f"PAIR {a} {b}"
        bot = bots.get(name)
        if not bot or bot["benched"]:
            continue
        ca, cb = cache.daily(a), cache.daily(b)
        if not ca or not cb:
            continue
        cla = [x["close"] for x in ca]
        clb = [x["close"] for x in cb]
        gap = round(scanner.pct(cla[-1], cla[-6])
                    - scanner.pct(clb[-1], clb[-6]), 2)
        if abs(gap) < 10:
            continue
        elig = arb_monitor.pair_eligibility(f"{a}/{b}", gap, today)
        long_leg, short_leg = (a, b) if gap < 0 else (b, a)
        lines.append(f"{name}: gap {gap:+.2f} pts, long {long_leg} / "
                     f"short {short_leg} - {elig}")
        if not elig.startswith("BARRED"):
            note = ("PAPER ONLY, news unverified"
                    if "news check still manual" in elig else "")
            maybe_call(name, long_leg, "buy", cache.last_close(long_leg),
                       f"{name}: gap {gap:+.2f} pts. {note}")
            maybe_call(name, short_leg, "short", cache.last_close(short_leg),
                       f"{name}: gap {gap:+.2f} pts. {note}")
            pair_signals.append(
                (long_leg, name, cache.last_close(long_leg)))

    # Rival bots per name: RAIDER (breakout) and ANCHOR (mean
    # reversion), different logic and parameters from WATCHER,
    # SHADOW and each other.
    for t in universe_tickers():
        dta = cache.daily_ta(t)
        c = cache.daily(t)
        if dta is None or not c:
            continue
        closes = [x["close"] for x in c]
        price = closes[-1]
        raider = bots.get(f"{t} RAIDER")
        if raider and not raider["benched"]:
            hit = len(closes) > 11 \
                and price > max(closes[-11:-1]) \
                and (dta["rel_volume"] or 0) >= 1.3 \
                and (dta["rsi14"] is None or dta["rsi14"] < 75)
            if hit:
                lines.append(f"{t} RAIDER: breakout entry "
                             "(10 day high, volume confirmed)")
                maybe_call(f"{t} RAIDER", t, "buy", price,
                           "RAIDER: close above the prior 10 day high "
                           "on relative volume >= 1.3, RSI under 75")
            elif dta["falling_knife"]:
                maybe_call(f"{t} RAIDER", t, "exit", price,
                           "RAIDER: falling_knife exit")
        anchor = bots.get(f"{t} ANCHOR")
        if anchor and not anchor["benched"]:
            s20, atr = dta["sma20"], dta["atr14"]
            hit = s20 and atr and price <= s20 - 1.2 * atr \
                and dta["rsi14"] is not None and dta["rsi14"] <= 42 \
                and closes[-1] > closes[-2]
            if hit:
                lines.append(f"{t} ANCHOR: mean reversion entry "
                             "(stretched below SMA20, reversal day)")
                maybe_call(f"{t} ANCHOR", t, "buy", price,
                           "ANCHOR: close at least 1.2 ATR below "
                           "SMA20, RSI at or under 42, green day")
            elif dta["falling_knife"]:
                maybe_call(f"{t} ANCHOR", t, "exit", price,
                           "ANCHOR: falling_knife exit")

    # FAMILY EXIT SWEEP (Tue Nov 3, 2026): positions held by the
    # families that never grew exit logic of their own (specialist,
    # strategist, captain) and the knife-only families (watcher,
    # rival, sniper) are checked against the standing Protected
    # Momentum exits at the real current price, so an entry any of
    # them logged can actually close and score. Sits before the
    # captains section so a captain position gets its exit check
    # even on a run where it also escalates new entries.
    if log_calls:
        sweep_lines = _sweep_family_exits(bots, open_info, cache,
                                          maybe_call)
        if sweep_lines:
            lines.append("Family exit sweep (Protected Momentum "
                         "exits for the exit-less families):")
            lines.extend(sweep_lines)

    # SECTION CAPTAINS: aggregate each section's signals, pre rank
    # by the source bot's proven record (Equality Protocol: quote
    # the record or the word UNPROVEN, never naked authority), flag
    # CONTESTED names inside the section, escalate only the top
    # qualifying calls. Captain escalations log under the captain's
    # own name, so THE BOARD ranks captains by escalation quality.
    try:
        from leaderboard import compute_standings, load_calls
        standings = compute_standings(load_calls(source="live"),
                                      price_fn=cache.last_close)
    except Exception:  # noqa: BLE001
        standings = {}

    def record_of(bot):
        st = standings.get(bot) or {}
        n = st.get("calls", 0)
        if n < 20 or st.get("sessions", 0) < 5:
            return None  # UNPROVEN
        scored = st.get("scored") or []
        per = (st.get("pnl", 0.0) / len(scored)) if scored else 0.0
        return (n, per)

    def escalate(cap_name, signals):
        bot = bots.get(cap_name)
        if not bot or bot["benched"]:
            return
        seen, ranked = set(), []
        for t, src, price in signals:
            if t in seen:
                continue
            seen.add(t)
            ranked.append((t, src, price, record_of(src)))
        ranked.sort(key=lambda r: (r[3] is not None,
                                   r[3][1] if r[3] else 0.0),
                    reverse=True)
        contested_here = [t for t, _, _, _ in ranked
                          if t in contested_tickers]
        clean = [r for r in ranked if r[0] not in contested_tickers]
        bits = []
        for t, src, price, rec in clean[:2]:
            tag = (f"{rec[0]} calls, ${rec[1]:+,.0f} per call"
                   if rec else "UNPROVEN")
            bits.append(f"{t} (from {src}, {tag})")
            maybe_call(cap_name, t, "buy", price,
                       f"{cap_name}: escalates {src}'s call on {t} "
                       f"(source record: {tag})")
        line = f"{cap_name}: escalates " + (
            "; ".join(bits) if bits else "nothing this run")
        if contested_here:
            line += (f" | CONTESTED in section, held back: "
                     f"{', '.join(contested_here)}")
        lines.append(line)

    for cap_name, section in CAPTAINS.items():
        if section == "PAIRS":
            escalate(cap_name, pair_signals)
        else:
            escalate(cap_name, section_signals.get(section, []))

    from bot_runtime import run_registered_extras
    lines.extend(run_registered_extras(registry, cache, log_calls))

    header = (f"BOT FACTORY DIGEST - {registry['count']} bots registered, "
              f"{len(active)} active, data through "
              f"{(cache.daily('SPY') or [{}])[-1].get('date', 'n/a')}")
    if log_calls:
        header += f"; {calls_made[0]} paper call(s) logged"
    return "\n".join([header] + lines)


def cull(registry):
    # One eligibility definition for both entry points; no alert-count bypass.
    import evolution
    calls = evolution.load_calls_for_season()
    _, standings, _ = evolution.pick_standings(calls)
    plan = evolution.season_plan(registry, standings)
    if standings["_ranked_calls"] < evolution.MIN_TOTAL_CALLS:
        print("Not enough completed live trades to cull; no registry changes.")
        return
    evolution.apply_plan(registry, plan, [])
    print("Benched eligible losing strategies: " + ", ".join(plan["bench"]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--log-calls", action="store_true")
    ap.add_argument("--cull", action="store_true")
    ap.add_argument("--snapshot", default=None,
                    help="path to the session's verified account "
                         "snapshot JSON; the digest run consumes it "
                         "through the paper context, the same way "
                         "run_city.py supplies it")
    args = ap.parse_args(argv)
    snapshot = None
    if args.snapshot:
        with open(args.snapshot) as f:
            snapshot = json.load(f)
        if not isinstance(snapshot, dict) \
                or "portfolio_value" not in snapshot \
                or not isinstance(snapshot.get("positions"), dict):
            ap.error(f"snapshot {args.snapshot} is not an account "
                     "snapshot (needs portfolio_value and a positions "
                     "object)")
    registry = build_registry()
    counts = ", ".join(f"{k} {v}" for k, v in
                       sorted(registry["counts_by_kind"].items()))
    print(f"BOT FACTORY - registry: {registry['count']} bots ({counts}) "
          f"written to output/bots.json")
    if snapshot is not None:
        print(f"Snapshot consumed: portfolio "
              f"${snapshot['portfolio_value']:,.2f}, "
              f"{len(snapshot['positions'])} position(s), "
              f"from {args.snapshot}")
    if args.cull:
        cull(registry)
    if args.run:
        if snapshot is not None:
            import leaderboard
            with leaderboard.paper_context(account_snapshot=snapshot):
                print(run_digest(registry, log_calls=args.log_calls))
        else:
            print(run_digest(registry, log_calls=args.log_calls))
    return 0


if __name__ == "__main__":
    sys.exit(main())
