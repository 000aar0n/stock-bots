"""Tests for the second Nov 3, 2026 bot fix pass (Aaron: "Bro fix
the bots"):

1. The winning side never trades: a short squad call travels
   calls.jsonl -> JUDGE short_candidates -> ODDS short EV ->
   allocator budget line (DAY book by default; LONG book shorts
   bounded by the hedge cap).
2. Whole families can never be scored: the family exit sweep
   closes watcher/rival/sniper/specialist/strategist/captain
   positions under the standing Protected Momentum exits.
3. Executed selection ignores the scoreboard: ODDS/JUDGE weight
   candidates by the source bot's completed live record.
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import allocator  # noqa: E402
import earnings_bot  # noqa: E402
import bot_factory  # noqa: E402
import leaderboard  # noqa: E402
import odds  # noqa: E402
import rules  # noqa: E402


# ------------------------------------------------------------ fixtures

def _snap(positions=None, buying_power=103_017.31, value=100_714.99):
    return {"timestamp": "Tue 11/03 9:30 ET",
            "portfolio_value": value,
            "cash": 50_000.0,
            "buying_power": buying_power,
            "loan": 0.0,
            "day_change_pct": 0.4,
            "positions": positions or {}}


def _sym(last=50.0, chg5=1.0, ta=None):
    return {"last_close": last, "chg_1d_pct": 0.5, "chg_5d_pct": chg5,
            "ta": ta or {"turning_up": False, "falling_knife": False,
                         "atr14": 1.5, "sma20": 52.0, "sma50": 54.0,
                         "rsi14": 40.0, "rel_volume": 2.0},
            "latency": {"candidate": False}, "closes_tail": [],
            "closes_dated": []}


def _scan(symbols):
    return {"symbols": symbols, "pairs": [], "latency_candidates": []}


# ------------------------------------------------- defect 1: short path

def test_judge_builds_short_candidate_from_squad_call(tmp_path,
                                                      monkeypatch):
    calls = tmp_path / "calls.jsonl"
    calls.write_text(json.dumps({
        "id": "x1", "ts": "2026-11-03T14:00:00Z", "bot": "UNDERCUT",
        "ticker": "WEAK", "side": "short", "entry_price": 55.0,
        "entry_ts": None, "reason": "UNDERCUT: breakdown",
        "bar_id": "b1", "source": "live"}) + "\n")
    monkeypatch.setattr(leaderboard, "CALLS_PATH", str(calls))
    monkeypatch.setattr(earnings_bot, "evaluate", lambda *a, **k: [])
    monkeypatch.setattr(odds, "bot_records", lambda price_fn=None: {})
    d = rules.evaluate(_snap(), _scan({"WEAK": _sym()}), day_change_pct=0.4)
    shorts = d["short_candidates"]
    assert len(shorts) == 1
    c = shorts[0]
    assert c["symbol"] == "WEAK" and c["side"] == "short"
    assert c["blocked"] is False
    assert c["sources"] == ["UNDERCUT"]
    assert c["exit_price"] == 54.0  # 50.00 * 1.08 cover stop
    assert "cover" in c["exit_trigger"]


def test_short_reaches_allocator_budget_line(tmp_path, monkeypatch):
    calls = tmp_path / "calls.jsonl"
    calls.write_text(json.dumps({
        "id": "x1", "ts": "2026-11-03T14:00:00Z", "bot": "UNDERCUT",
        "ticker": "WEAK", "side": "short", "entry_price": 55.0,
        "entry_ts": None, "reason": "UNDERCUT: breakdown",
        "bar_id": "b1", "source": "live"}) + "\n")
    monkeypatch.setattr(leaderboard, "CALLS_PATH", str(calls))
    monkeypatch.setattr(earnings_bot, "evaluate", lambda *a, **k: [])
    monkeypatch.setattr(odds, "bot_records", lambda price_fn=None: {})
    snap = _snap()
    d = rules.evaluate(snap, _scan({"WEAK": _sym()}), day_change_pct=0.4)
    assert d["short_candidates"], "JUDGE produced no short candidate"
    rows = odds.build_odds(_scan({"WEAK": _sym()}),
                           records={})
    short_rows = [r for r in rows if r.get("side") == "short"]
    assert short_rows and short_rows[0]["sources"] == ["UNDERCUT"]
    sheet = allocator.build_sheet(snap, d, [], False, odds_rows=rows)
    assert sheet["agreement"], sheet["problems"]
    line = sheet["per_name"].get("WEAK")
    assert line is not None, "short never reached a budget line"
    assert line["budget"] > 0
    assert line["side"] == "short"
    assert line["book"] == "DAY"  # day book by default


def test_long_book_short_bounded_by_hedge_cap():
    snap = _snap()
    decisions = {"buy_candidates": [], "arb_candidates": [],
                 "positions": [],
                 "short_candidates": [
                     {"symbol": "HEDGEY", "blocked": False,
                      "blocked_reasons": [], "protect_capped": False,
                      "hold_style": "swing", "ev_score": 9.0,
                      "last_close": 40.0}]}
    sheet = allocator.build_sheet(snap, decisions, [], False,
                                  odds_rows=[])
    assert sheet["agreement"], sheet["problems"]
    line = sheet["per_name"]["HEDGEY"]
    assert line["book"] == "LONG" and line["side"] == "short"
    long_cap = sheet["envelopes"]["LONG"]["cap"]
    assert 0 < line["budget"] <= 0.25 * long_cap + 0.01


def test_ledger_rejects_over_hedge_capped_sheet():
    snap = _snap()
    caps = allocator.envelope_caps(88_017.31)
    per_name = {"HEDGEY": {"budget": 0.30 * caps["LONG"],
                           "cap": 25_178.75, "kind": "short",
                           "side": "short", "book": "LONG",
                           "hold_style": "swing",
                           "protect_capped": False,
                           "uncapped_budget": 0.30 * caps["LONG"],
                           "ev": 9.0}}
    sheet = {"reserve": 15_000.0, "deployable": 88_017.31,
             "buy_mode": False, "per_name": per_name,
             "envelopes": allocator.envelope_totals(per_name, caps)}
    agree, _, problems = allocator.ledger_verify(snap, sheet, [])
    assert not agree
    assert any("hedge cap" in p for p in problems)


def test_odds_scores_the_short_side():
    sdata = _sym()
    sdata["high_20d"] = 56.0
    row = odds.score_candidate("WEAK", sdata, {}, side="short")
    assert row["side"] == "short"
    # below both averages on volume: positive short momentum
    assert row["expected_gain_pct"] > row["expected_loss_pct"] - 8.0
    assert row["ev_score"] == row["heuristic_score"]


# ------------------------------------------- defect 2: family exit sweep

class _Cache:
    def __init__(self, closes_by_ticker):
        self._c = closes_by_ticker

    def daily(self, sym):
        closes = self._c[sym]
        return [{"date": f"2026-10-{20 + i:02d}", "close": c,
                 "open": c, "high": c, "low": c, "volume": 1000}
                for i, c in enumerate(closes)]

    def daily_ta(self, sym):
        return {"falling_knife": False}

    def last_close(self, sym):
        return self._c[sym][-1]


def test_exit_reason_eight_percent_stop():
    entry = {"side": "buy", "entry_price": 100.0,
             "ts": "2026-10-20T15:00:00Z"}
    cache = _Cache({"XYZ": [100.0, 99.0, 98.0, 91.0]})
    reason = bot_factory._position_exit_reason(entry, cache, "XYZ")
    assert reason and "8% exit" in reason


def test_exit_reason_two_red_closes_while_held():
    entry = {"side": "buy", "entry_price": 100.0,
             "ts": "2026-10-21T15:00:00Z"}
    cache = _Cache({"XYZ": [100.0, 100.0, 99.0, 98.0, 97.0]})
    reason = bot_factory._position_exit_reason(entry, cache, "XYZ")
    assert reason and "two straight red closes" in reason


def test_exit_reason_ignores_pre_entry_closes():
    # The two red closes happened BEFORE the entry date: no exit.
    entry = {"side": "buy", "entry_price": 97.0,
             "ts": "2026-10-23T15:00:00Z"}
    cache = _Cache({"XYZ": [100.0, 99.0, 98.0, 97.0, 97.5]})
    assert bot_factory._position_exit_reason(entry, cache, "XYZ") \
        is None


def test_exit_reason_flat_position_stays_open():
    entry = {"side": "buy", "entry_price": 100.0,
             "ts": "2026-10-20T15:00:00Z"}
    cache = _Cache({"XYZ": [100.0, 100.5, 101.0]})
    assert bot_factory._position_exit_reason(entry, cache, "XYZ") \
        is None


def test_sweep_closes_exitless_families_only():
    bots = {
        "STACK": {"name": "STACK", "kind": "specialist",
                  "benched": False},
        "CAPTAIN STACK": {"name": "CAPTAIN STACK", "kind": "captain",
                          "benched": False},
        "HANDY": {"name": "HANDY", "kind": "handcrafted",
                  "benched": False},
    }
    open_info = {
        ("STACK", "XYZ"): {"side": "buy", "entry_price": 100.0,
                           "ts": "2026-10-20T15:00:00Z"},
        ("CAPTAIN STACK", "XYZ"): {"side": "buy", "entry_price": 100.0,
                                   "ts": "2026-10-20T15:00:00Z"},
        ("HANDY", "XYZ"): {"side": "buy", "entry_price": 100.0,
                           "ts": "2026-10-20T15:00:00Z"},
    }
    cache = _Cache({"XYZ": [100.0, 95.0, 91.0]})

    def call_fn(bot, ticker, side, price, reason):
        assert side == "exit"
        open_info.pop((bot, ticker), None)  # maybe_call semantics

    lines = bot_factory._sweep_family_exits(bots, open_info, cache,
                                            call_fn)
    assert ("STACK", "XYZ") not in open_info
    assert ("CAPTAIN STACK", "XYZ") not in open_info
    # Handcrafted bots manage their own exits; the sweep skips them.
    assert ("HANDY", "XYZ") in open_info
    assert len(lines) == 2


# --------------------------------- defect 3: scoreboard weighting

def _write_calls(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _call(bot, ticker, side, price, day):
    return {"id": f"{bot}-{ticker}-{day}-{side}",
            "ts": f"2026-10-{day:02d}T15:00:00Z", "bot": bot,
            "ticker": ticker, "side": side, "entry_price": price,
            "entry_ts": None, "reason": "test", "bar_id": "b",
            "source": "live"}


def test_bot_records_tiers_from_completed_trades(tmp_path,
                                                  monkeypatch):
    calls = tmp_path / "calls.jsonl"
    rows = []
    # WINNER: 3 completed trades, all up.
    for day, (e, x) in enumerate([(100, 110), (100, 108), (100, 105)],
                                 start=20):
        rows.append(_call("WINNER", "AAA", "buy", e, day))
        rows.append(_call("WINNER", "AAA", "exit", x, day))
    # LOSER: 3 completed trades, all down.
    for day, (e, x) in enumerate([(100, 95), (100, 94), (100, 96)],
                                 start=20):
        rows.append(_call("LOSER", "BBB", "buy", e, day))
        rows.append(_call("LOSER", "BBB", "exit", x, day))
    # THIN: one completed trade only - unproven, no record.
    rows.append(_call("THIN", "CCC", "buy", 100, 20))
    rows.append(_call("THIN", "CCC", "exit", 130, 20))
    _write_calls(calls, rows)
    monkeypatch.setattr(leaderboard, "CALLS_PATH", str(calls))
    recs = odds.bot_records(price_fn=lambda t: 100.0)
    assert recs["WINNER"]["tier"] == 1 and recs["WINNER"]["ev_adj"] > 0
    assert recs["LOSER"]["tier"] == -1 and recs["LOSER"]["ev_adj"] < 0
    assert "THIN" not in recs
    assert abs(recs["WINNER"]["ev_adj"]) <= odds.RECORD_EV_CAP


def test_record_for_sources_mix_cancels():
    records = {"W": {"tier": 1, "ev_adj": 1.0},
               "L": {"tier": -1, "ev_adj": -1.0}}
    assert odds.record_for_sources(records, ["W"]) == (1, 1.0)
    assert odds.record_for_sources(records, ["L"]) == (-1, -1.0)
    assert odds.record_for_sources(records, ["W", "L"])[0] == 0
    assert odds.record_for_sources(records, ["NOBODY"]) == (0, 0.0)


def test_build_odds_unproven_source_leaves_ev_untouched():
    scan = _scan({"AAA": _sym(last=50.0), "BBB": _sym(last=50.0)})
    for s in scan["symbols"].values():
        s["ta"] = dict(s["ta"], turning_up=True)
    import scanner
    candles = [{"date": "2026-11-03", "close": 50.0,
                "open": 50.0, "high": 52.0, "low": 45.0,
                "volume": 1000}] * 25
    orig = scanner.fetch_daily
    scanner.fetch_daily = lambda sym: candles
    try:
        rows = odds.build_odds(
            scan, records={"FALCON": {"tier": 0, "ev_adj": 0.0}})
    finally:
        scanner.fetch_daily = orig
    assert len(rows) == 2
    for r in rows:
        assert r["record_tier"] == 0 and r["record_ev_adj"] == 0.0
        assert r["ev_score"] == r["heuristic_score"]


def test_build_odds_applies_source_record_adjustment():
    scan = _scan({"AAA": _sym(last=50.0)})
    scan["symbols"]["AAA"]["ta"] = dict(
        scan["symbols"]["AAA"]["ta"], turning_up=True)
    import scanner
    candles = [{"date": "2026-11-03", "close": 50.0, "open": 50.0,
                "high": 52.0, "low": 45.0, "volume": 1000}] * 25
    orig = scanner.fetch_daily
    scanner.fetch_daily = lambda sym: candles
    try:
        rows = odds.build_odds(
            scan, records={"FALCON": {"tier": -1, "ev_adj": -1.25,
                                      "calls": 9, "pnl": -900.0}})
    finally:
        scanner.fetch_daily = orig
    assert len(rows) == 1
    r = rows[0]
    assert r["record_tier"] == -1
    assert r["record_ev_adj"] == -1.25
    assert r["ev_score"] == round(r["heuristic_score"] - 1.25, 2)
