"""judge_scorecard.py - JUDGE decision accountability.

There is exactly ONE JUDGE (Aaron, Sat Oct 31, 2026, correcting an
earlier two judge idea): no shadow challenger, no second rules
variant, no swap pointer. JUDGE holds the gavel by performance,
and it can be DELETED.

Every JUDGE decision (approve or block) on a bot call can be logged
here with log_decision(). Decisions are scored on the same $10k
paper reference as THE BOARD:
  approved calls: scored by their realized paper P&L (entry price
    vs the latest close, open position basis).
  blocked calls: scored by the paper P&L they WOULD have made,
    tracked in shadow. A block that dodged a loser scores positive
    for JUDGE's judgment; a block that killed a winner scores
    against it.

DELETION VERDICT (evaluated by evolution.py's JUDGE REVIEW and by
this module's CLI): over a review window with at least 20 scored
decisions, if JUDGE's net scored outcome is negative (approvals
lost money in aggregate, OR blocked calls would have made clearly
more than the approvals made), the verdict is DELETE JUDGE.
Deletion is final: the JUDGE record is removed from the active
registry, a tombstone (output/judge_deleted.json) stops the
factory from ever re-minting it, and its scorecard is preserved
in output/judge_scorecard.json and the decisions log as history
only. There is no bench and no reinstatement path.

SUCCESSION PRINCIPLE (Aaron): if JUDGE is ever deleted, "we can
code a new one based on what algos are working." A successor judge
is hand built fresh at that time, its rules drawn from the
evidence of what is producing then: the proven bots, their
winning logged causes, and this scorecard of what the old JUDGE
got wrong. No automatic generation, and no successor is prebuilt.

Until 20 scored decisions exist, every review prints
"insufficient decisions" and nothing else happens.

Run: python3 judge_scorecard.py [--delete]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import hashlib
from storage import locked
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output")
DECISIONS_PATH = os.path.join(OUT_DIR, "judge_decisions.jsonl")
OUTCOMES_PATH = os.path.join(OUT_DIR, "judge_outcomes.jsonl")
SUMMARY_PATH = os.path.join(OUT_DIR, "judge_scorecard.json")
TOMBSTONE_PATH = os.path.join(OUT_DIR, "judge_deleted.json")
REGISTRY_PATH = os.path.join(OUT_DIR, "bots.json")

REF_SIZE = 10_000.0
MIN_DECISIONS = 20

SUCCESSION_PRINCIPLE = (
    "Succession principle (Aaron): if JUDGE is deleted, a new judge "
    "is hand coded fresh at that time, based on what algos are "
    "working: the proven bots, their winning logged causes, and "
    "this scorecard of what the old JUDGE got wrong. No automatic "
    "generation, no prebuilt successor.")


def log_decision(bot, ticker, side, price, action, reason="", bar_id=None):
    """Deduped decision observation; no current-price counterfactual P&L."""
    if action not in ("approved", "blocked"):
        raise ValueError("invalid JUDGE decision")
    os.makedirs(OUT_DIR, exist_ok=True)
    bar_id = bar_id or datetime.now(timezone.utc).date().isoformat()
    identity = hashlib.sha256(f"{bot}|{ticker}|{side}|{bar_id}".encode()).hexdigest()
    with locked(DECISIONS_PATH):
        if any(d.get("id") == identity for d in load_decisions()):
            return None
        row = {"id": identity, "ts": datetime.now(timezone.utc).isoformat(),
               "bot": bot, "ticker": ticker, "side": side, "entry_price": price,
               "action": action, "reason": reason, "bar_id": bar_id}
        with open(DECISIONS_PATH, "a") as handle:
            handle.write(json.dumps(row) + "\n")
    return row


def load_decisions(path=None):
    path = path or DECISIONS_PATH
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def resolve_pending(fetch_daily=None):
    """Lock each decision's counterfactual at its session close, once available.
    This is a common paper evaluation horizon, not realized HTMW performance.
    """
    import scanner
    from market_clock import calendar
    from zoneinfo import ZoneInfo
    fetch_daily = fetch_daily or scanner.fetch_daily
    cache = {}
    os.makedirs(OUT_DIR, exist_ok=True)
    with locked(OUTCOMES_PATH):
        known = set()
        if os.path.exists(OUTCOMES_PATH):
            with open(OUTCOMES_PATH) as handle:
                known = {json.loads(line)["decision_id"] for line in handle if line.strip()}
        for d in load_decisions():
            if not d.get("id") or d["id"] in known or d.get("side") not in ("buy", "short"):
                continue
            try:
                observed = datetime.fromisoformat(d["ts"].replace("Z", "+00:00"))
                day = observed.astimezone(ZoneInfo("America/New_York")).date().isoformat()
                cal = calendar()
                if not cal.is_session(day):
                    continue
                end = cal.session_close(day).to_pydatetime()
                if end <= observed or end > datetime.now(timezone.utc):
                    continue
                if d["ticker"] not in cache:
                    cache[d["ticker"]] = fetch_daily(d["ticker"])
                bar = next((r for r in cache[d["ticker"]] if r["date"] == day), None)
                if bar is None:
                    continue
                outcome = {"decision_id": d["id"], "completed": True,
                           "exit_price": bar["close"], "exit_at": end.isoformat(),
                           "basis": "same-session-close counterfactual, not HTMW P/L"}
                with open(OUTCOMES_PATH, "a") as handle:
                    handle.write(json.dumps(outcome) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                known.add(d["id"])
            except (ValueError, KeyError, RuntimeError):
                continue  # missing actual outcome data stays explicitly unscored


def score_decisions(price_fn=None, decisions_path=None, outcomes_path=None):
    """Only explicit completed paper outcomes count. Never re-mark old
    decisions to today's price, which changes their horizon on every run.
    Legacy decisions without outcome fields remain unscored.
    """
    from leaderboard import _ref_pnl
    approved = {"n": 0, "pnl": 0.0}
    blocked = {"n": 0, "pnl": 0.0}
    unscored = 0
    seen = set()
    sessions = set()
    outcomes = {}
    outcomes_path = outcomes_path or OUTCOMES_PATH
    if os.path.exists(outcomes_path):
        with open(outcomes_path) as handle:
            outcomes = {r["decision_id"]: r for r in (json.loads(line) for line in handle if line.strip())}
    for original in load_decisions(decisions_path):
        d = {**original, **outcomes.get(original.get("id"), {})}
        key = d.get("id") or (d.get("bot"), d.get("ticker"), d.get("ts"), d.get("side"))
        if key in seen:
            continue
        seen.add(key)
        if (d.get("side") not in ("buy", "short") or not d.get("completed")
                or not d.get("exit_at") or not d.get("exit_price")):
            unscored += 1
            continue
        pnl = _ref_pnl(d, d["exit_price"])
        if pnl is None:
            unscored += 1
            continue
        bucket = approved if d.get("action") == "approved" else blocked
        bucket["n"] += 1
        bucket["pnl"] += pnl
        sessions.add(d["exit_at"][:10])
    scored = approved["n"] + blocked["n"]
    return {"scored": scored, "approved": approved, "blocked": blocked,
            "sessions": len(sessions), "unscored": unscored,
            "net": approved["pnl"] - max(0.0, blocked["pnl"])}


def verdict(sc):
    """(verdict, why). Verdicts: INSUFFICIENT, STANDS, DELETE."""
    if sc["scored"] < MIN_DECISIONS or sc.get("sessions", 0) < 5:
        return ("INSUFFICIENT",
                f"insufficient decisions: {sc['scored']} scored, "
                f"{MIN_DECISIONS} needed")
    ap, bl = sc["approved"]["pnl"], sc["blocked"]["pnl"]
    if ap < 0:
        return ("DELETE",
                f"approvals lost money in aggregate (${ap:+,.2f})")
    if (sc["approved"]["n"] >= MIN_DECISIONS and sc["blocked"]["n"] >= MIN_DECISIONS
            and bl / sc["blocked"]["n"] > ap / sc["approved"]["n"] and bl > 0):
        return ("DELETE",
                f"blocked calls would have made clearly more "
                f"(${bl:+,.2f}) than approvals made (${ap:+,.2f})")
    return ("STANDS",
            f"approvals ${ap:+,.2f}, blocked would-have "
            f"${bl:+,.2f}: the gate is earning its seat")


def judge_review_lines():
    """The JUDGE REVIEW block printed by evolution.py's season
    review and by this module's CLI."""
    sc = score_decisions()
    v, why = verdict(sc)
    lines = ["JUDGE REVIEW (one JUDGE, judged on its decisions):"]
    if v == "INSUFFICIENT":
        lines.append(f"  insufficient decisions: {sc['scored']} "
                     f"scored, {MIN_DECISIONS} needed before any "
                     "verdict. JUDGE stands by default until the "
                     "evidence exists.")
        return lines
    lines.append(
        f"  scorecard: {sc['scored']} scored decisions | approved "
        f"{sc['approved']['n']} calls, ${sc['approved']['pnl']:+,.2f} "
        f"paper | blocked {sc['blocked']['n']} calls, would have "
        f"made ${sc['blocked']['pnl']:+,.2f} in shadow | net "
        f"${sc['net']:+,.2f}")
    if v == "DELETE":
        lines.append(f"  VERDICT: DELETE JUDGE. {why}.")
        lines.append("  Deletion is final: the record is removed "
                     "from the active registry and preserved as "
                     "history only. No bench, no reinstatement.")
        lines.append(f"  {SUCCESSION_PRINCIPLE}")
    else:
        lines.append(f"  VERDICT: JUDGE STANDS. {why}.")
    return lines


def delete_judge():
    """Execute a DELETE verdict: remove JUDGE from the active
    registry and write the tombstone so the factory never re-mints
    it. Its scorecard is preserved as history. Returns a message."""
    sc = score_decisions()
    v, why = verdict(sc)
    if v != "DELETE":
        return f"refused: verdict is {v} ({why}); nothing deleted"
    snapshot = {"deleted_at": datetime.now().isoformat(timespec="seconds"),
                "verdict_why": why, "scorecard": sc,
                "succession_principle": SUCCESSION_PRINCIPLE}
    from storage import atomic_json
    atomic_json(SUMMARY_PATH, snapshot)
    atomic_json(TOMBSTONE_PATH, snapshot)
    removed = 0
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH) as f:
            reg = json.load(f)
        before = len(reg["bots"])
        reg["bots"] = [b for b in reg["bots"] if b["name"] != "JUDGE"]
        removed = before - len(reg["bots"])
        reg["count"] = len(reg["bots"])
        counts = {}
        for b in reg["bots"]:
            counts[b["kind"]] = counts.get(b["kind"], 0) + 1
        reg["counts_by_kind"] = counts
        atomic_json(REGISTRY_PATH, reg)
    return (f"JUDGE DELETED ({why}). Removed {removed} registry "
            "record(s); tombstone written so the factory never "
            "re-mints it. Scorecard preserved in "
            "output/judge_scorecard.json as history only. "
            + SUCCESSION_PRINCIPLE)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true",
                    help="execute deletion if the verdict is DELETE")
    args = ap.parse_args(argv)
    for line in judge_review_lines():
        print(line)
    if args.delete:
        print(delete_judge())
    return 0


if __name__ == "__main__":
    sys.exit(main())
