"""arena.py - THE ARENA (REWIND's proving ground).

Live paper calls accumulate slowly, a handful per session. The
arena gives the handcrafted craftsmen somewhere to PRODUCE now:
it replays each bot's own module over historical daily candles,
one trading day at a time, with the data layer sliced so the bot
sees only what it would have seen that day. Calls the bot logs
are written to output/calls.jsonl with source "backtest".

HONEST LABELING, everywhere: THE BOARD's official standings use
live calls only. Arena standings print separately as ARENA
RESULTS. An arena champion is not a live champion. DARWIN may
breed from arena standings only while live calls are below the
eligibility threshold, and anything it breeds that way is
stamped ARENA_BRED in the registry until it proves itself live.

Limits, stated plainly: there is no historical 5 minute tape in
this data layer, so intraday dependent bots (MOSAIC's 5m leg,
PRESSURE, SCALPEL, NEEDLE, RAPID, CURRENT, TIC, ARBITER) mostly
stand down or error in the arena; their arena silence is a data
limit, not a verdict. Arena call timestamps are the run time;
sequence is append order. Factory bots are not replayed here:
their rule sets live in the factory digest, which produces live
in shadow mode instead.

Run: python3 arena.py [--days 20] [--bots RUBBER,VICE]
     (default: all 100 handcrafted bots, last 20 trading days)
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import leaderboard  # noqa: E402
import scanner  # noqa: E402


def load_roster():
    with open(os.path.join(HERE, "handcrafted", "roster.json")) as f:
        return json.load(f)


class Replay:
    """Sliced data layer: bots see history only up to replay day."""

    def __init__(self):
        self.cache = {}
        self.cutoff = None  # a date string; candles after it hide

    def full(self, sym):
        if sym not in self.cache:
            self.cache[sym] = scanner._real_fetch_daily(sym)
        return self.cache[sym]

    def daily(self, sym):
        rows = self.full(sym)
        if self.cutoff is None:
            return rows
        return [c for c in rows if c["date"] <= self.cutoff]

    def intraday(self, sym):
        return []  # no historical intraday tape exists in this layer


def run_arena(days, bot_names):
    roster = {e["name"]: e for e in load_roster()}
    names = bot_names or [e["name"] for e in load_roster()]
    unknown = [n for n in names if n not in roster]
    if unknown:
        print(f"ARENA - unknown handcrafted bots: {', '.join(unknown)}")
        return 1

    replay = Replay()
    scanner._real_fetch_daily = scanner.fetch_daily
    scanner.fetch_daily = replay.daily
    scanner.fetch_intraday = replay.intraday

    written = {"n": 0}
    real_log = leaderboard.log_call

    def arena_log(bot, ticker, side, price, reason, cause="",
                  source="live", path=leaderboard.CALLS_PATH):
        written["n"] += 1
        return real_log(bot, ticker, side, price, reason,
                        cause=cause, source="backtest", path=path)

    leaderboard.log_call = arena_log

    spy = replay.full("SPY")
    all_dates = [c["date"] for c in spy][-days:]
    print(f"ARENA - replaying {len(names)} handcrafted bot(s) over "
          f"{len(all_dates)} trading days "
          f"({all_dates[0]} to {all_dates[-1]}), source: backtest")
    errors = 0
    try:
        for day in all_dates:
            replay.cutoff = day
            for name in names:
                entry = roster[name]
                path = os.path.join(HERE, "handcrafted", entry["file"])
                spec = importlib.util.spec_from_file_location(
                    f"arena_{entry['file'][:-3]}", path)
                mod = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(mod)
                    with contextlib.redirect_stdout(io.StringIO()):
                        mod.main(["--log-calls"])
                except Exception:  # noqa: BLE001
                    errors += 1
    finally:
        scanner.fetch_daily = scanner._real_fetch_daily
        del scanner._real_fetch_daily
        leaderboard.log_call = real_log
    print(f"ARENA - done: {written['n']} backtest call(s) written to "
          f"output/calls.jsonl (source \"backtest\"), {errors} bot-day "
          "error(s) stood down (mostly intraday bots with no "
          "historical 5 minute tape).")
    print("ARENA - these are arena results, not live rank. See "
          "leaderboard.py for the separate arena standings.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=20)
    ap.add_argument("--bots", default="",
                    help="comma separated bot names (default: all "
                         "handcrafted)")
    args = ap.parse_args(argv)
    names = [n.strip().upper() for n in args.bots.split(",") if n.strip()]
    return run_arena(args.days, names)


if __name__ == "__main__":
    sys.exit(main())
