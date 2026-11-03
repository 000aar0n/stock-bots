"""HANDS (htmw_client) rails: gate record completeness, caps, kill
switch, idempotency, audit. Synthetic data only, no network, and the
live submit path is never exercised (it refuses unsupervised)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

import htmw_client as hands


NOW = datetime(2026, 11, 3, 21, 0, tzinfo=timezone.utc)  # Tue 16:00 ET


def _iso(dt):
    return dt.isoformat()


@pytest.fixture()
def sdir(tmp_path):
    d = tmp_path / "state"
    d.mkdir()
    (d / "hands_control.json").write_text(json.dumps({"enabled": True}))
    return str(d)


@pytest.fixture()
def calls_path(tmp_path):
    p = tmp_path / "calls.jsonl"
    p.write_text("\n".join([
        "# comment header, skipped by the reader",
        json.dumps({"id": "call-1", "bot": "FALCON", "ticker": "GPN",
                    "side": "buy", "entry_price": 99.0,
                    "ts": "2026-11-03T14:00:00-05:00",
                    "source": "live"}),
        json.dumps({"id": "call-2", "bot": "RUBBER", "ticker": "NVDA",
                    "side": "buy", "entry_price": 214.13,
                    "ts": "2026-10-31T14:09:14", "source": "backtest"}),
    ]) + "\n")
    return str(p)


def snapshot(**over):
    snap = {
        "verified": True,
        "snapshot_at": _iso(NOW - timedelta(seconds=30)),
        "portfolio_value": 100_000.0,
        "buying_power": 60_000.0,
        "cash": 10_000.0,
        "loan": 0.0,
        "positions": {"AKAM": {"qty": 100, "entry": 90.0}},
    }
    snap.update(over)
    return snap


def gated(**over):
    gate = {
        "kind": "gated", "ticker": "GPN", "side": "buy", "qty": 100,
        "price_ref": 99.0, "bot": "FALCON", "call_id": "call-1",
        "judge_approved": True, "bouncer_veto": False,
        "odds_ev": 12.0, "allocator_budget": 15_000.0, "book": "DAY",
        "book_usage": {"LONG": 0.0, "DAY": 0.0},
    }
    gate.update(over)
    return gate


def validate(gate, snap, sdir, calls_path, **kw):
    kw.setdefault("earnings_rows", [])
    return hands.validate_order(gate, snap, sdir=sdir,
                                calls_path=calls_path, now=NOW, **kw)


# ------------------------------------------------------------ happy path
def test_complete_gate_record_passes(sdir, calls_path):
    assert validate(gated(), snapshot(), sdir, calls_path) == []


def test_protective_exit_passes(sdir, calls_path):
    gate = {"kind": "protective_exit", "ticker": "AKAM",
            "side": "sell", "qty": 100, "price_ref": 80.0,
            "exit_rule": "two_red_closes",
            "reason": "two straight red closes while held"}
    assert validate(gate, snapshot(), sdir, calls_path) == []


def test_dry_run_execute_validates_and_places_nothing(sdir, calls_path,
                                                      monkeypatch):
    monkeypatch.setenv("HANDS_STATE_DIR", sdir)
    receipt = hands.execute_order(gated(), snapshot(), live=False,
                                  calls_path=calls_path,
                                  earnings_rows=[], now=NOW)
    assert receipt["status"] == "dry_run"
    audit = hands._read_jsonl(sdir + "/hands_audit.jsonl")
    assert audit[-1]["decision"] == "dry_run"
    # dry runs never enter the submission ledger
    assert hands._read_jsonl(sdir + "/hands_ledger.jsonl") == []


# ------------------------------------------------------------ gate record
def test_missing_judge_approval_refused(sdir, calls_path):
    r = validate(gated(judge_approved=False), snapshot(), sdir,
                 calls_path)
    assert any("JUDGE" in x for x in r)


def test_bouncer_veto_refused(sdir, calls_path):
    r = validate(gated(bouncer_veto=True), snapshot(), sdir, calls_path)
    assert any("BOUNCER" in x for x in r)


def test_nonpositive_ev_refused(sdir, calls_path):
    r = validate(gated(odds_ev=-1.5), snapshot(), sdir, calls_path)
    assert any("ODDS" in x for x in r)


def test_unlogged_call_refused(sdir, calls_path):
    r = validate(gated(call_id="nope"), snapshot(), sdir, calls_path)
    assert any("calls.jsonl" in x for x in r)


def test_backtest_call_cannot_back_an_order(sdir, calls_path):
    gate = gated(bot="RUBBER", call_id=None, ticker="NVDA")
    r = validate(gate, snapshot(), sdir, calls_path)
    assert any("calls.jsonl" in x for x in r)


def test_over_budget_refused(sdir, calls_path):
    r = validate(gated(qty=200), snapshot(), sdir, calls_path)
    assert any("budget" in x for x in r)


def test_protective_exit_needs_a_rule_and_a_position(sdir, calls_path):
    gate = {"kind": "protective_exit", "ticker": "GPN", "side": "sell",
            "qty": 10, "price_ref": 99.0, "exit_rule": "vibes",
            "reason": ""}
    r = validate(gate, snapshot(), sdir, calls_path)
    assert any("rule" in x for x in r)
    assert any("position" in x for x in r)


def test_unknown_kind_refused(sdir, calls_path):
    r = validate(gated(kind="yolo"), snapshot(), sdir, calls_path)
    assert any("kind" in x for x in r)


# ------------------------------------------------------------ caps
def test_envelope_cap(sdir, calls_path):
    big = snapshot(positions={"AKAM": {"qty": 100, "entry": 90.0},
                              "MSFT": {"qty": 350, "entry": 520.0}})
    # gross 191,000 + 9,900 order > 200,000 envelope
    r = validate(gated(), big, sdir, calls_path)
    assert any("envelope" in x for x in r)


def test_single_name_cap(sdir, calls_path):
    snap = snapshot(positions={"GPN": {"qty": 200, "entry": 99.0}})
    # 19,800 existing + 9,900 = 29,700 > 25% of 100,000
    r = validate(gated(), snap, sdir, calls_path)
    assert any("single name" in x for x in r)


def test_buying_power_reserve_floor(sdir, calls_path):
    snap = snapshot(buying_power=20_000.0)
    # only 5,000 above the floor; the order wants 9,900
    r = validate(gated(), snap, sdir, calls_path)
    assert any("reserve floor" in x for x in r)


def test_book_envelope_no_cross_borrowing(sdir, calls_path):
    gate = gated(book_usage={"LONG": 0.0, "DAY": 20_000.0})
    # DAY cap is (60,000 - 15,000) / 2 = 22,500; 20,000 + 9,900 over
    r = validate(gate, snapshot(), sdir, calls_path)
    assert any("envelope breached" in x for x in r)
    # the same usage on the LONG side leaves DAY room: still refused,
    # because usage follows the order's own book, never the other one
    gate2 = gated(book="LONG", book_usage={"LONG": 20_000.0,
                                           "DAY": 0.0})
    r2 = validate(gate2, snapshot(), sdir, calls_path)
    assert any("envelope breached" in x for x in r2)


def test_earnings_cap_binds_long_entries_only(sdir, calls_path):
    rows = [{"ticker": "GPN", "date": "2026-11-05", "days_until": 2,
             "sessions_until": 2}]
    gate = gated(book="LONG", qty=200,
                 allocator_budget=30_000.0)
    r = validate(gate, snapshot(), sdir, calls_path,
                 earnings_rows=rows)
    assert any("earnings cap" in x for x in r)
    # a DAY entry flattens before the close and does not ride the print
    assert validate(gated(), snapshot(), sdir, calls_path,
                    earnings_rows=rows) == []


def test_long_entry_refused_without_earnings_calendar(sdir, calls_path):
    gate = gated(book="LONG")
    r = hands.validate_order(gate, snapshot(), sdir=sdir,
                             calls_path=calls_path, now=NOW,
                             earnings_rows=None)
    assert any("earnings calendar" in x for x in r)


# ------------------------------------------------------------ snapshot
def test_stale_snapshot_refused(sdir, calls_path):
    snap = snapshot(snapshot_at=_iso(NOW - timedelta(seconds=3600)))
    r = validate(gated(), snap, sdir, calls_path)
    assert any("old" in x for x in r)


def test_unverified_snapshot_refused(sdir, calls_path):
    r = validate(gated(), snapshot(verified=False), sdir, calls_path)
    assert any("verified" in x for x in r)


# ------------------------------------------------------------ kill switch
def test_kill_switch_missing_control_halts(tmp_path, calls_path):
    d = str(tmp_path / "empty")
    r = hands.validate_order(gated(), snapshot(), sdir=d,
                             calls_path=calls_path, now=NOW,
                             earnings_rows=[])
    assert any("halted" in x for x in r)


def test_kill_switch_disabled_and_kill_file_halt(sdir, calls_path):
    import os
    with open(os.path.join(sdir, "hands_control.json"), "w") as f:
        json.dump({"enabled": False}, f)
    r = validate(gated(), snapshot(), sdir, calls_path)
    assert any("halted" in x for x in r)
    with open(os.path.join(sdir, "hands_control.json"), "w") as f:
        json.dump({"enabled": True}, f)
    open(os.path.join(sdir, "hands.kill"), "w").close()
    r = validate(gated(), snapshot(), sdir, calls_path)
    assert any("halted" in x for x in r)


def test_kill_switch_unreadable_control_halts(tmp_path, calls_path):
    d = tmp_path / "bad"
    d.mkdir()
    (d / "hands_control.json").write_text("{not json")
    r = hands.validate_order(gated(), snapshot(), sdir=str(d),
                             calls_path=calls_path, now=NOW,
                             earnings_rows=[])
    assert any("halted" in x for x in r)


# ------------------------------------------------------------ idempotency
class FakeLiveClient:
    def __init__(self):
        self.placed = []

    def login(self):
        return True

    def place_market_order(self, symbol, side, qty):
        self.placed.append((symbol, side, qty))
        return {"status": "submitted", "order_id": "ord-123"}

    def read_order_history(self):
        return [{"order_id": "ord-123", "symbol": "GPN", "side": "buy",
                 "qty": 100, "status": "Filled", "price": 99.0}]


def test_live_execute_places_reads_back_and_dedupes(sdir, calls_path,
                                                    monkeypatch):
    monkeypatch.setenv("HANDS_STATE_DIR", sdir)
    client = FakeLiveClient()
    receipt = hands.execute_order(gated(), snapshot(), live=True,
                                  client=client, calls_path=calls_path,
                                  earnings_rows=[], now=NOW)
    assert receipt["status"] == "placed"
    assert receipt["order_id"] == "ord-123"
    assert client.placed == [("GPN", "buy", 100)]
    with pytest.raises(hands.Refusal):
        hands.execute_order(gated(), snapshot(), live=True,
                            client=client, calls_path=calls_path,
                            earnings_rows=[], now=NOW)
    assert client.placed == [("GPN", "buy", 100)]  # never resubmitted
    decisions = [r["decision"] for r in
                 hands._read_jsonl(sdir + "/hands_audit.jsonl")]
    assert decisions == ["placed", "refused"]


def test_crashed_submission_blocks_rerun(sdir, calls_path, monkeypatch):
    monkeypatch.setenv("HANDS_STATE_DIR", sdir)
    key = hands.idempotency_key(gated(), "2026-11-03")
    hands.ledger_append(sdir, {"ts": "2026-11-03T21:00:00+00:00",
                               "key": key, "status": "submitting"})
    with pytest.raises(hands.Refusal):
        hands.execute_order(gated(), snapshot(), live=True,
                            client=FakeLiveClient(),
                            calls_path=calls_path, earnings_rows=[],
                            now=NOW)


def test_refusals_are_audited(sdir, calls_path, monkeypatch):
    monkeypatch.setenv("HANDS_STATE_DIR", sdir)
    with pytest.raises(hands.Refusal):
        hands.execute_order(gated(judge_approved=False), snapshot(),
                            live=False, calls_path=calls_path,
                            earnings_rows=[], now=NOW)
    audit = hands._read_jsonl(sdir + "/hands_audit.jsonl")
    assert audit[-1]["decision"] == "refused"
    assert any("JUDGE" in x for x in audit[-1]["reasons"])


# ------------------------------------------------------------ live guards
def test_live_submit_requires_supervision_flags(monkeypatch):
    monkeypatch.delenv("HANDS_LIVE", raising=False)
    monkeypatch.delenv("HTMW_HANDS_SUPERVISED", raising=False)
    client = hands.HTMWClient(dry_run=False)
    client.page = object()  # pretend logged in; flags must stop it
    with pytest.raises(hands.HTMWError):
        client._submit_live({"symbol": "GPN", "side": "buy", "qty": 1,
                             "type": "market"})


def test_live_login_requires_credentials(monkeypatch):
    monkeypatch.delenv("HTMW_USER", raising=False)
    monkeypatch.delenv("HTMW_PASS", raising=False)
    client = hands.HTMWClient(dry_run=False)
    with pytest.raises(hands.HTMWError) as e:
        client.login()
    assert "HTMW_PASS" in str(e.value)


# ------------------------------------------------------------ assembler
def test_assemble_gate_record_from_suite_outputs(tmp_path, sdir):
    out = tmp_path / "output"
    out.mkdir()
    (out / "rules-latest.json").write_text(json.dumps({
        "buy_candidates": [{"symbol": "GPN", "blocked": False,
                            "blocked_reasons": [],
                            "last_close": 99.0}]}))
    (out / "warden-latest.json").write_text(json.dumps({
        "cap_violations": [], "disagreements": []}))
    (out / "odds-latest.json").write_text(json.dumps([
        {"ticker": "GPN", "ev_score": 12.0, "close": 99.0}]))
    (out / "budget.json").write_text(json.dumps({
        "agreement": True, "per_name": {"GPN": 15000.0},
        "books": {"GPN": "DAY"},
        "envelopes": {"LONG": {"allocated": 0.0},
                      "DAY": {"allocated": 100.0}}}))
    (out / "calls.jsonl").write_text(json.dumps({
        "id": "c9", "bot": "FALCON", "ticker": "GPN", "side": "buy",
        "entry_price": 99.0, "source": "live"}) + "\n")
    record, problems = hands.assemble_gate_record(
        "GPN", "buy", 100, "DAY", out_dir=str(out))
    assert problems == []
    assert record["judge_approved"] is True
    assert record["bouncer_veto"] is False
    assert record["odds_ev"] == 12.0
    assert record["allocator_budget"] == 15000.0
    assert record["call_id"] == "c9"
    # usage = budget committed to OTHER names per book; GPN is the
    # only funded name, so both books read zero for its own order
    assert record["book_usage"] == {"LONG": 0.0, "DAY": 0.0}
    # and the assembled record passes validation as is
    assert hands.validate_order(record, snapshot(), sdir=sdir,
                                calls_path=str(out / "calls.jsonl"),
                                now=NOW, earnings_rows=[]) == []


def test_assemble_reports_missing_evidence(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    record, problems = hands.assemble_gate_record(
        "GPN", "buy", 100, "DAY", out_dir=str(out))
    assert problems  # everything missing is named, nothing defaulted
    assert record["ticker"] == "GPN"
