"""Tests for the Tue Nov 3, 2026 bot update pass (Aaron's order):
rules.py ODDS ranked candidates, bot_factory same day exit guard,
CRESCENDO anti blowoff entry guards."""
from datetime import date

import bot_factory
import rules


def test_rules_odds_ranked_candidate_reaches_judge(monkeypatch):
    import earnings_bot
    monkeypatch.setattr(earnings_bot, "evaluate", lambda *a, **k: [])
    snapshot = {"portfolio_value": 100000, "start_value": 100000,
                "peak_gain": 0, "buying_power": 50000, "positions": {}}
    trend_ta = {"turning_up": False, "falling_knife": False,
                "atr14": 3.0, "sma20": 110.0, "sma50": 105.0,
                "rsi14": 60.0, "rel_volume": 1.6}
    scan = {"symbols": {
        "TREND": {"last_close": 120.0, "chg_5d_pct": 4.0, "ta": trend_ta},
        "KNIFE": {"last_close": 120.0, "chg_5d_pct": 4.0,
                  "ta": dict(trend_ta, falling_knife=True)},
    }}
    result = rules.evaluate(snapshot, scan)
    by_sym = {c["symbol"]: c for c in result["buy_candidates"]}
    assert "TREND" in by_sym
    assert by_sym["TREND"]["candidate_source"] == "odds_ranked"
    assert by_sym["TREND"]["ev_score"] > 0
    assert "KNIFE" not in by_sym


def test_rules_turning_up_candidate_still_tagged():
    snapshot = {"portfolio_value": 100000, "start_value": 100000,
                "peak_gain": 0, "buying_power": 50000, "positions": {}}
    scan = {"symbols": {"XYZ": {"last_close": 100,
                                "ta": {"turning_up": True,
                                       "falling_knife": False}}}}
    result = rules.evaluate(snapshot, scan)
    assert result["buy_candidates"][0]["candidate_source"] == "turning_up"


def test_same_day_exit_guard_blocks_cost_churn():
    entry = {"entry_price": 100.0, "ts": "2026-11-03T10:00:00-05:00",
             "side": "buy"}
    today = date(2026, 11, 3)
    # 1% adverse on a same day entry: churn, blocked.
    assert bot_factory._exit_blocked_same_day(entry, 99.0, today) is True
    # 4% adverse: a real break, exit allowed.
    assert bot_factory._exit_blocked_same_day(entry, 96.0, today) is False
    # Overnight position: exit freely even on a small adverse move.
    old = dict(entry, ts="2026-11-02T10:00:00-05:00")
    assert bot_factory._exit_blocked_same_day(old, 99.0, today) is False
    # Short side mirrors: price up 1% against a same day short is churn.
    short = dict(entry, side="short")
    assert bot_factory._exit_blocked_same_day(short, 101.0, today) is True
    assert bot_factory._exit_blocked_same_day(short, 104.0, today) is False
    # No logged entry: never blocked by this guard.
    assert bot_factory._exit_blocked_same_day(None, 99.0, today) is False


def test_crescendo_entry_guards():
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "handcrafted",
                        "crescendo.py")
    spec = importlib.util.spec_from_file_location("crescendo", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    day = {"high": 110.0, "low": 100.0, "open": 102.0}
    base = {"rel_volume": 3.0, "sma20": 100.0, "rsi14": 60.0}
    # Climax at the highs, 8% above SMA20: allowed.
    assert mod.entry_ok(base, day, 108.0) is True
    # Same climax but 15% above SMA20: vertical blowoff, blocked.
    tall = {"high": 116.0, "low": 100.0, "open": 102.0}
    assert mod.entry_ok(base, tall, 115.0) is False
    # Exhausted RSI: blocked.
    assert mod.entry_ok(dict(base, rsi14=85.0), day, 108.0) is False
    # No climax volume: blocked as before.
    assert mod.entry_ok(dict(base, rel_volume=1.5), day, 108.0) is False
