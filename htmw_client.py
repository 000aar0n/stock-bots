"""htmw_client.py - HANDS. The execution hand of the Bot City.

HANDS places orders on HowTheMarketWorks. Until Tue Nov 3, 2026 it
was a dry-run skeleton. That evening Aaron gave the explicit approval
the skeleton was waiting for ("Wire HANDS live", in chat, after an
options card), so the live path is now wired, behind the rails
below. Approval alone does not make an order placeable: every rail
must pass, every run, or HANDS refuses and logs the refusal.

WHAT HANDS IS, MECHANICALLY:
- There is no HTMW API. HANDS drives the real website with
  Playwright (login page -> quote page -> trade ticket -> order
  history read back), the same pages the agent sessions use in the
  Muse browser. It inherits the site's limits: 15 minute delayed
  quotes, regular hours fills, after hours orders fill at the next
  open, a pending sell does not free buying power until it fills.
- The page selectors in the live path are carried over from the
  skeleton and are NOT yet verified against the live site. The
  first live use must be a supervised run (HTMW_HANDS_SUPERVISED=1)
  that confirms the login and trade ticket flow while placing only
  a gate passed order; the supervising session then verifies the
  fill in Order History independently, as sessions always have.

CREDENTIALS:
- Read ONLY from the environment variables HTMW_USER and HTMW_PASS.
  Nothing hardcoded, nothing read from files, nothing logged.
- The Secure Vault copy of the HTMW login serves the Muse
  browser's sign in agent only; no tool exports vault values to a
  script. Until Aaron supplies the password for script use (the
  HTMW_PASS environment variable in the environment that runs
  HANDS), live mode refuses cleanly with that exact reason. See
  OPERATIONS.md, "HANDS live status".

THE RAILS (all mandatory, all fail closed):
1. GATE RECORD. A gated order must arrive as a complete gate record
   (JSON): a bot call logged in output/calls.jsonl with source
   "live" (matched by call id, or by bot+ticker+side), JUDGE
   approval, BOUNCER no veto, ODDS ev_score positive, an allocator
   budget for the name, and a book tag, LONG or DAY. The alternative
   is a protective exit record naming its Protected Momentum rule
   (momentum exit, two red closes, daily brake, PROTECT, day
   flatten). Anything else is refused and the refusal is audited.
2. CAPS, recomputed here from a fresh verified session snapshot
   (same contract as run_city.py: verified true, snapshot_at at
   most 300 seconds old): gross exposure including this order at
   most TOTAL_ENVELOPE ($200k); post order position in one name at
   most 25 percent of portfolio value; entry notional at most
   buying power minus the $15k reserve floor; a LONG entry in a
   name inside its earnings window keeps the post order position
   at or under the $15k earnings cap; per book envelopes split
   deployable 50/50 and never borrow across books.
3. KILL SWITCH. output/hands_control.json must exist, parse, and
   carry enabled: true, checked fresh before every order. A
   output/hands.kill file halts instantly. Missing, unreadable or
   disabled control state means HALTED. To halt HANDS: create
   hands.kill, delete the control file, or set enabled false.
4. IDEMPOTENCY. Every order carries a key hashed from its gate
   record and the session date. output/hands_ledger.jsonl records
   each attempt; a key already submitted, filled, or stuck in
   "submitting" (a crashed run) is refused, never resubmitted.
   This exists because a human session double submitted a SOFI
   short on Nov 3; HANDS does not get to repeat that.
5. AUDIT AND READ BACK. Every attempt, placed or refused, appends
   to output/hands_audit.jsonl. A placed order is only reported as
   placed after HANDS reads Order History back and finds the order
   id the site returned; an unconfirmed submission is reported as
   UNCONFIRMED, never as a fill.

DRY RUN stays the default. Live submission requires all of:
HANDS_LIVE=1 in the environment, credentials present, the kill
switch state enabled, and HTMW_HANDS_SUPERVISED=1 acknowledging a
supervised run.

CLI:
    python3 htmw_client.py                      # skeleton demo (dry)
    python3 htmw_client.py status               # control/creds state
    python3 htmw_client.py prepare --ticker GPN --side buy --qty 100 \
        --book DAY [--bot FALCON]               # assemble a gate record
                                                # from output/*-latest
    python3 htmw_client.py execute --gate gate.json \
        --snapshot snapshot.json [--live]       # validate (+ place)

Requires: pip install playwright (and `playwright install chromium`)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

DRY_RUN = True  # Default posture. Aaron approved live wiring on
# 2026-11-03, but live submission additionally requires HANDS_LIVE=1,
# credentials, enabled kill switch state and a supervised run, per
# call. Nothing about importing this module can place an order.

BASE_URL = "https://app.howthemarketworks.com"
LOGIN_URL = BASE_URL + "/login"            # TODO: confirm exact path
PORTFOLIO_URL = BASE_URL + "/portfolio"    # TODO: confirm exact path
ORDERS_URL = BASE_URL + "/orders"          # TODO: confirm exact path

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, "output")

# ------------------------------------------------------------- rails
TOTAL_ENVELOPE = 200_000.0        # JUDGE's gross envelope (Aaron)
SINGLE_NAME_CAP_PCT = 0.25        # of portfolio value, post order
BP_RESERVE_FLOOR = 15_000.0       # buying power always held back
EARNINGS_CAP = 15_000.0           # per name held through a print
EARNINGS_WINDOW_SESSIONS = 2      # matches allocator.py
SNAPSHOT_MAX_AGE_S = 300          # run_city.py verified snapshot rule

ENTRY_SIDES = ("buy", "short")
EXIT_SIDES = ("sell", "cover")
ALL_SIDES = ENTRY_SIDES + EXIT_SIDES
BOOKS = ("LONG", "DAY")
PROTECTIVE_RULES = (
    "momentum_exit_8pct", "two_red_closes", "daily_brake_4pct",
    "daily_brake_6pct", "protect_mode", "day_flatten",
    "earnings_cap_exit", "session_documented_exit",
)


class HTMWError(RuntimeError):
    pass


class Refusal(HTMWError):
    """An order HANDS will not place. Carries every reason found."""

    def __init__(self, reasons):
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


# ------------------------------------------------------------ state io
def state_dir():
    return os.environ.get("HANDS_STATE_DIR") or OUTPUT_DIR


def _read_json_file(path):
    with open(path) as f:
        return json.load(f)


def _append_jsonl(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")


def _read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------- kill switch
def control_state(sdir=None):
    """Return (enabled, state, detail). Fail closed: anything short
    of a parseable control file with enabled exactly true, and no
    hands.kill file present, means HANDS is halted."""
    sdir = sdir or state_dir()
    kill = os.path.join(sdir, "hands.kill")
    if os.path.exists(kill):
        return False, "kill_file", f"{kill} present"
    path = os.path.join(sdir, "hands_control.json")
    if not os.path.exists(path):
        return False, "control_missing", f"{path} does not exist"
    try:
        data = _read_json_file(path)
    except Exception as e:  # unreadable state halts, by design
        return False, "control_unreadable", f"{path}: {e}"
    if not isinstance(data, dict) or data.get("enabled") is not True:
        return False, "control_disabled", "enabled is not true"
    return True, "enabled", data.get("note", "")


# ------------------------------------------------------------- gate log
def find_logged_call(calls_path, call_id=None, bot=None, ticker=None,
                     side=None):
    """Find a live source call in calls.jsonl. Bot paper calls are
    ranked by THE BOARD; only source "live" rows can back a real
    order (backtest and arena rows never can)."""
    for row in _read_jsonl(calls_path):
        if row.get("source") != "live":
            continue
        if call_id:
            if row.get("id") == call_id:
                return row
            continue
        if bot and row.get("bot") != bot:
            continue
        if ticker and row.get("ticker") != ticker:
            continue
        if side and row.get("side") != side:
            continue
        return row
    return None


def idempotency_key(gate, day_str):
    basis = {
        "date": day_str,
        "kind": gate.get("kind"),
        "bot": gate.get("bot") or gate.get("exit_rule") or "",
        "ticker": gate.get("ticker"),
        "side": gate.get("side"),
        "qty": gate.get("qty"),
        "book": gate.get("book") or "",
        "call_id": gate.get("call_id") or "",
    }
    blob = json.dumps(basis, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def ledger_statuses(sdir, key):
    path = os.path.join(sdir, "hands_ledger.jsonl")
    return [r.get("status") for r in _read_jsonl(path)
            if r.get("key") == key]


# ------------------------------------------------------------ validation
def _parse_ts(ts):
    if not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt


def validate_snapshot(snapshot, now=None):
    reasons = []
    if not isinstance(snapshot, dict):
        return ["snapshot is not an object"]
    if snapshot.get("verified") is not True:
        reasons.append("snapshot is not marked verified")
    ts = _parse_ts(snapshot.get("snapshot_at"))
    if ts is None:
        reasons.append("snapshot_at missing or not timezone bearing")
    else:
        age = (now or datetime.now(timezone.utc)).timestamp() - \
            ts.timestamp()
        if age > SNAPSHOT_MAX_AGE_S:
            reasons.append(
                f"snapshot is {int(age)}s old, over the "
                f"{SNAPSHOT_MAX_AGE_S}s limit")
        if age < -60:
            reasons.append("snapshot_at is in the future")
    for field in ("portfolio_value", "buying_power"):
        if not isinstance(snapshot.get(field), (int, float)):
            reasons.append(f"snapshot missing numeric {field}")
    if not isinstance(snapshot.get("positions"), dict):
        reasons.append("snapshot positions missing")
    return reasons


def _position_value(snapshot, ticker):
    pos = (snapshot.get("positions") or {}).get(ticker)
    if not pos:
        return 0.0
    return abs(pos.get("qty", 0)) * float(pos.get("entry") or 0)


def _gross_exposure(snapshot):
    return sum(abs(p.get("qty", 0)) * float(p.get("entry") or 0)
               for p in (snapshot.get("positions") or {}).values())


def _earnings_in_window(ticker, earnings_rows):
    for row in earnings_rows or []:
        if row.get("ticker") != ticker:
            continue
        days = row.get("days_until")
        sessions = row.get("sessions_until")
        if days is not None and days < 0:
            continue  # the print already happened
        if sessions is not None and sessions <= EARNINGS_WINDOW_SESSIONS:
            return row
        if sessions is None and days is not None and days <= 3:
            return row
    return None


def validate_order(gate, snapshot, *, sdir=None, calls_path=None,
                   earnings_rows=None, book_usage=None, now=None):
    """Return the list of refusal reasons for an order. Empty list
    means every rail passed. Pure: reads files, changes nothing."""
    sdir = sdir or state_dir()
    calls_path = calls_path or os.path.join(OUTPUT_DIR, "calls.jsonl")
    reasons = []

    # kill switch first: a halted HANDS validates nothing further
    enabled, cstate, detail = control_state(sdir)
    if not enabled:
        return [f"HANDS halted: kill switch state {cstate} ({detail})"]

    reasons += validate_snapshot(snapshot, now=now)
    if reasons:
        return reasons

    # ---- gate record completeness
    if not isinstance(gate, dict):
        return ["gate record is not an object"]
    ticker = str(gate.get("ticker") or "").upper()
    side = str(gate.get("side") or "").lower()
    qty = gate.get("qty")
    price = gate.get("price_ref")
    if not ticker:
        reasons.append("gate record missing ticker")
    if side not in ALL_SIDES:
        reasons.append(f"gate record side {side!r} not one of {ALL_SIDES}")
    if not isinstance(qty, (int, float)) or qty <= 0:
        reasons.append("gate record qty missing or not positive")
    if not isinstance(price, (int, float)) or price <= 0:
        reasons.append("gate record price_ref missing or not positive")
    if reasons:
        return reasons
    notional = float(qty) * float(price)
    kind = gate.get("kind")
    book = gate.get("book")

    if kind == "gated":
        if gate.get("call_id") or gate.get("bot"):
            call = find_logged_call(
                calls_path, call_id=gate.get("call_id"),
                bot=gate.get("bot"), ticker=ticker, side=side)
            if call is None:
                reasons.append(
                    "no live bot call in calls.jsonl matches this "
                    "gate record")
        else:
            reasons.append("gated order carries no bot or call id")
        if gate.get("judge_approved") is not True:
            reasons.append("JUDGE approval not recorded")
        if gate.get("bouncer_veto") is not False:
            reasons.append("BOUNCER veto state is not a recorded "
                           "non veto")
        ev = gate.get("odds_ev")
        if not isinstance(ev, (int, float)) or ev <= 0:
            reasons.append("ODDS ev is not positive")
        budget = gate.get("allocator_budget")
        if not isinstance(budget, (int, float)) or budget <= 0:
            reasons.append("allocator budget missing")
        elif notional > float(budget) * 1.02:
            reasons.append(
                f"order notional ${notional:,.2f} exceeds allocator "
                f"budget ${float(budget):,.2f}")
        if book not in BOOKS:
            reasons.append("gated order missing book tag LONG or DAY")
    elif kind == "protective_exit":
        if side not in EXIT_SIDES:
            reasons.append("protective exit must be a sell or cover")
        if gate.get("exit_rule") not in PROTECTIVE_RULES:
            reasons.append(
                "protective exit names no recognized Protected "
                "Momentum rule")
        if not gate.get("reason"):
            reasons.append("protective exit carries no documented "
                           "reason")
        pos = (snapshot.get("positions") or {}).get(ticker)
        if not pos or pos.get("qty", 0) == 0:
            reasons.append(f"no open position in {ticker} to exit")
        elif abs(pos["qty"]) < qty:
            reasons.append(
                f"exit qty {qty} exceeds open position "
                f"{abs(pos['qty'])} in {ticker}")
    else:
        reasons.append(f"gate record kind {kind!r} is neither "
                       f"'gated' nor 'protective_exit'")
    if reasons:
        return reasons

    # ---- caps (entries; exits only reduce exposure)
    if side in ENTRY_SIDES:
        value = float(snapshot["portfolio_value"])
        bp = float(snapshot["buying_power"])
        gross_after = _gross_exposure(snapshot) + notional
        if gross_after > TOTAL_ENVELOPE:
            reasons.append(
                f"gross exposure after order ${gross_after:,.2f} "
                f"exceeds the $200k envelope")
        name_after = _position_value(snapshot, ticker) + notional
        if name_after > SINGLE_NAME_CAP_PCT * value:
            reasons.append(
                f"{ticker} would be ${name_after:,.2f}, over the "
                f"25% single name cap (${0.25 * value:,.2f})")
        if notional > max(0.0, bp - BP_RESERVE_FLOOR):
            reasons.append(
                f"order notional ${notional:,.2f} breaches the $15k "
                f"buying power reserve floor (buying power "
                f"${bp:,.2f})")
        # per book envelope: deployable splits 50/50, no spill
        usage = book_usage if book_usage is not None \
            else gate.get("book_usage")
        if book in BOOKS:
            deployable = max(0.0, bp - BP_RESERVE_FLOOR)
            cap = deployable / 2.0
            if not isinstance(usage, dict) or book not in usage:
                reasons.append(
                    "book usage unavailable; per book envelope "
                    "cannot be verified, refusing")
            elif float(usage[book]) + notional > cap:
                reasons.append(
                    f"{book} book envelope breached: "
                    f"${float(usage[book]):,.2f} used + "
                    f"${notional:,.2f} over its ${cap:,.2f} cap; "
                    f"books do not borrow from each other")
        # earnings cap binds positions held through a print: LONG
        # entries. DAY entries flatten before the close and never
        # ride an after close print (see module docstring).
        if book == "LONG":
            row = _earnings_in_window(ticker, earnings_rows)
            if row is not None and name_after > EARNINGS_CAP:
                reasons.append(
                    f"{ticker} reports {row.get('date')} (inside "
                    f"the earnings window); LONG position would be "
                    f"${name_after:,.2f}, over the $15k earnings cap")
            if earnings_rows is None:
                reasons.append(
                    "earnings calendar unavailable; a LONG entry "
                    "cannot be checked against the earnings cap")
    return reasons


# ------------------------------------------------------- gate assembly
def assemble_gate_record(ticker, side, qty, book, out_dir=None, bot=None):
    """Build a gate record for a single name from the latest suite
    outputs (rules, warden, odds, budget, calls). Returns
    (record, problems). Missing evidence is a problem, never a
    default pass. Pairs are two separate legs and out of scope."""
    out_dir = out_dir or OUTPUT_DIR
    ticker = ticker.upper()
    problems = []
    record = {"kind": "gated", "ticker": ticker, "side": side,
              "qty": qty, "book": book}

    def load(name):
        path = os.path.join(out_dir, name)
        if not os.path.exists(path):
            problems.append(f"{name} missing")
            return None
        try:
            return _read_json_file(path)
        except Exception as e:
            problems.append(f"{name} unreadable: {e}")
            return None

    rules = load("rules-latest.json")
    cand = None
    if rules:
        # A short looks in JUDGE's short candidate list (Tue
        # Nov 3, 2026); before this the assembler only ever searched
        # buy_candidates, so a fully gated short could not even be
        # prepared for HANDS.
        pool = rules.get("short_candidates", []) if side == "short" \
            else rules.get("buy_candidates", [])
        for c in pool:
            if c.get("symbol") == ticker:
                cand = c
                break
        if cand is None:
            problems.append(f"JUDGE has no {side} candidate for {ticker}")
        else:
            record["judge_approved"] = cand.get("blocked") is False
            if not record["judge_approved"]:
                problems.append(f"JUDGE blocked {ticker}: "
                                f"{cand.get('blocked_reasons')}")
            record["price_ref"] = cand.get("last_close")
    warden = load("warden-latest.json")
    if warden is not None:
        veto = ticker in (warden.get("cap_violations") or []) or \
            any(ticker in str(d)
                for d in warden.get("disagreements") or [])
        record["bouncer_veto"] = bool(veto)
        if veto:
            problems.append(f"BOUNCER flags {ticker}")
    odds_rows = load("odds-latest.json")
    if isinstance(odds_rows, list):
        # Prefer the row for this side (a name can carry both a
        # long and a short row now); fall back to any row for the
        # ticker so pre-short-era files still assemble.
        row = next((r for r in odds_rows
                    if r.get("ticker") == ticker
                    and r.get("side", "long") == side), None) or \
            next((r for r in odds_rows
                  if r.get("ticker") == ticker), None)
        if row is None:
            problems.append(f"ODDS has no row for {ticker}")
        else:
            record["odds_ev"] = row.get("ev_score")
            if not record.get("price_ref"):
                record["price_ref"] = row.get("close")
    budget = load("budget.json")
    if budget is not None:
        if budget.get("agreement") is not True:
            problems.append("allocator sheet is in DISAGREEMENT "
                            "(deployable zeroed)")
        per = (budget.get("per_name") or {}).get(ticker)
        if per is None:
            problems.append(f"allocator funded nothing for {ticker}")
        else:
            record["allocator_budget"] = per
        books = budget.get("books") or {}
        if ticker in books and books[ticker] != book:
            problems.append(
                f"book mismatch: allocator tags {ticker} "
                f"{books[ticker]}, gate record says {book}")
        sides = budget.get("sides") or {}
        if ticker in sides and sides[ticker] == "short" \
                and side != "short":
            problems.append(
                f"side mismatch: allocator funded {ticker} as a "
                f"short, gate record says {side}")
        # Book usage for the envelope rail means dollars already
        # committed in a book BEFORE this order. On the allocator
        # sheet that is the budget committed to OTHER names in the
        # same book (this name's own budget is checked separately);
        # a session may instead supply position based usage in the
        # gate record, which validate_order treats identically.
        per_name = budget.get("per_name") or {}
        record["book_usage"] = {
            b: round(sum(v for t, v in per_name.items()
                         if t != ticker and books.get(t) == b), 2)
            for b in BOOKS}
    call = find_logged_call(os.path.join(out_dir, "calls.jsonl"),
                            bot=bot, ticker=ticker, side=side)
    if call is None:
        problems.append(f"no live call logged for {ticker} {side}")
    else:
        record["bot"] = call.get("bot")
        record["call_id"] = call.get("id")
        if not record.get("price_ref"):
            record["price_ref"] = call.get("entry_price")
    return record, problems


# ---------------------------------------------------------------- audit
def audit(sdir, row):
    row = {"ts": _now_iso(), **row}
    _append_jsonl(os.path.join(sdir, "hands_audit.jsonl"), row)
    return row


def ledger_append(sdir, row):
    _append_jsonl(os.path.join(sdir, "hands_ledger.jsonl"), row)


# ------------------------------------------------------------- the client
class HTMWClient:
    def __init__(self, dry_run=DRY_RUN):
        self.dry_run = dry_run
        self.user = os.environ.get("HTMW_USER")
        self.password = os.environ.get("HTMW_PASS")
        self._pw = None
        self._browser = None
        self.page = None

    # ------------------------------------------------------------ lifecycle
    def _require_playwright(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise HTMWError(
                "playwright is not installed. Run: pip install playwright "
                "&& playwright install chromium")

    def _require_creds(self):
        if not self.user or not self.password:
            raise HTMWError(
                "HTMW_USER / HTMW_PASS environment variables are not "
                "set. The Secure Vault copy of the login serves the "
                "browser sign in agent only and cannot be exported "
                "to a script; Aaron must supply the password for "
                "script use (see OPERATIONS.md). Credentials are "
                "never hardcoded or read from files.")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()
        self._browser = self._pw = self.page = None

    # ------------------------------------------------------------ session
    def login(self):
        """Sign in to HTMW. Known gotcha from the agent sessions: the
        username field sometimes comes prefilled with Aaron's school
        email, which the site rejects. Always clear the field and type
        the username (HTMW_USER, i.e. portfoliopilot2) exactly."""
        self._require_playwright()
        self._require_creds()
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self.page = self._browser.new_page()
        self.page.goto(LOGIN_URL)
        # TODO selectors: confirm the real field names/ids on the live
        # login form during the supervised first run.
        user_field = self.page.locator("input[name='username'], "
                                       "input#username").first
        pass_field = self.page.locator("input[name='password'], "
                                       "input#password").first
        user_field.click()
        user_field.press("Control+A")
        user_field.fill(self.user)  # exact username, clears autofill
        pass_field.fill(self.password)
        self.page.locator("button[type='submit'], "
                          "input[type='submit']").first.click()
        self.page.wait_for_load_state("networkidle")
        # TODO: verify success by checking for the account banner
        # ("Welcome, <user>") and raise HTMWError on the site's
        # wrong-username/password message.
        return True

    def _require_login(self):
        if self.page is None:
            raise HTMWError("not logged in - call login() first")

    # ------------------------------------------------------------ reads
    def read_portfolio(self):
        """Return {portfolio_value, cash, loan, buying_power,
        positions: [{symbol, qty, ...}]} parsed from the portfolio /
        account balances pages. TODO: table selectors unconfirmed."""
        self._require_login()
        self.page.goto(PORTFOLIO_URL)
        self.page.wait_for_load_state("networkidle")
        raise NotImplementedError(
            "read_portfolio: page selectors not yet confirmed against "
            "the live site. Confirm in a supervised run, then parse the "
            "balances header and positions table here.")

    def read_order_history(self):
        """Return a list of order dicts {order_id, symbol, side, qty,
        status, price} from the order history page (prices can show "
        "masked as $XXX.xx same-day on HTMW; keep them as None then).
        TODO: table selectors unconfirmed."""
        self._require_login()
        self.page.goto(ORDERS_URL)
        self.page.wait_for_load_state("networkidle")
        raise NotImplementedError(
            "read_order_history: page selectors not yet confirmed "
            "against the live site.")

    # ------------------------------------------------------------ orders
    def place_market_order(self, symbol, side, qty):
        """Place a market order via the stock's trade ticket.

        DRY RUN (the default) only prints the intended order and
        returns a dry-run receipt; it does not even need a login, and
        it performs NO gate or cap checks. Callers who want the rails
        enforced use execute_order(), which validates first and calls
        this only after every rail passed.
        Live submission goes through _submit_live, which refuses
        unless HANDS_LIVE=1 and HTMW_HANDS_SUPERVISED=1 are both set.
        """
        side = side.lower()
        if side not in ALL_SIDES:
            raise ValueError(f"bad side {side!r}")
        if qty <= 0:
            raise ValueError("qty must be positive")
        order = {"symbol": symbol.upper(), "side": side, "qty": int(qty),
                 "type": "market"}
        if self.dry_run:
            print(f"[HANDS] [DRY RUN] would place: market {side} "
                  f"{qty} x {symbol.upper()} on HTMW (nothing submitted)")
            return {"status": "dry_run", **order}
        self._require_login()
        return self._submit_live(order)

    def _submit_live(self, order):
        """Live submission through the trade ticket. UNVERIFIED
        selectors: the flow follows the documented HTMW pages, but
        the ticket selectors and confirm step must be confirmed in
        the supervised first run. Refuses to run unsupervised."""
        if os.environ.get("HANDS_LIVE") != "1":
            raise HTMWError(
                "live submission requires HANDS_LIVE=1 in the "
                "environment for this run")
        if os.environ.get("HTMW_HANDS_SUPERVISED") != "1":
            raise HTMWError(
                "live submission requires HTMW_HANDS_SUPERVISED=1: "
                "the trade ticket selectors are not yet verified "
                "against the live site, so the first live runs must "
                "be supervised")
        # Supervised confirmation checklist (first live run):
        #   1. goto the symbol quote page, open the trade ticket
        #   2. select side, enter qty, market order type
        #   3. preview: verify symbol, side and qty on the preview
        #   4. submit, capture the confirmation/order id shown
        #   5. read the order back in order history (read back is
        #      enforced by execute_order after this returns)
        raise NotImplementedError(
            "live trade ticket flow is not yet confirmed against "
            "the live site. Confirm it in the supervised first run "
            "(Wednesday 9:35 session), then wire the selectors here.")


# ------------------------------------------------------------- execution
def execute_order(gate, snapshot, *, live=False, client=None,
                  sdir=None, calls_path=None, earnings_rows=None,
                  book_usage=None, now=None):
    """The one door orders go through. Validates every rail, checks
    idempotency, places (live or dry), reads back, audits. Returns a
    receipt dict; raises Refusal with all reasons when any rail
    fails. A receipt with status "dry_run" placed nothing."""
    sdir = sdir or state_dir()
    day = (now or datetime.now(timezone.utc)).astimezone().strftime(
        "%Y-%m-%d")
    key = idempotency_key(gate, day)
    base = {"key": key, "ticker": gate.get("ticker"),
            "side": gate.get("side"), "qty": gate.get("qty"),
            "book": gate.get("book"), "kind": gate.get("kind"),
            "live": bool(live)}

    reasons = validate_order(gate, snapshot, sdir=sdir,
                             calls_path=calls_path,
                             earnings_rows=earnings_rows,
                             book_usage=book_usage, now=now)
    if reasons:
        audit(sdir, {**base, "decision": "refused", "reasons": reasons})
        raise Refusal(reasons)

    prior = [s for s in ledger_statuses(sdir, key)
             if s in ("submitting", "submitted", "filled")]
    if prior:
        audit(sdir, {**base, "decision": "refused",
                     "reasons": [f"duplicate: this order key is "
                                 f"already {prior[-1]} in the ledger; "
                                 f"refusing to resubmit"]})
        raise Refusal([f"duplicate order key already {prior[-1]}"])

    if not live:
        receipt = (client or HTMWClient(dry_run=True)) \
            .place_market_order(gate["ticker"], gate["side"],
                                gate["qty"])
        audit(sdir, {**base, "decision": "dry_run",
                     "receipt": receipt})
        return {"status": "dry_run", "key": key, "receipt": receipt}

    # live: mark the ledger BEFORE submitting, so a crash mid submit
    # can never look like a fresh order on the next run
    ledger_append(sdir, {"ts": _now_iso(), "key": key,
                         "status": "submitting", **base})
    client = client or HTMWClient(dry_run=False)
    try:
        client.login()
        placed = client.place_market_order(gate["ticker"],
                                           gate["side"], gate["qty"])
    except Exception as e:
        ledger_append(sdir, {"ts": _now_iso(), "key": key,
                             "status": "error", "error": str(e),
                             **base})
        audit(sdir, {**base, "decision": "error", "error": str(e)})
        raise
    order_id = placed.get("order_id")
    ledger_append(sdir, {"ts": _now_iso(), "key": key,
                         "status": "submitted", "order_id": order_id,
                         **base})
    # read back: an order is only "placed" once order history shows it
    confirmed = None
    try:
        for row in client.read_order_history():
            if order_id and row.get("order_id") == order_id:
                confirmed = row
                break
    except Exception as e:
        audit(sdir, {**base, "decision": "placed_unconfirmed",
                     "order_id": order_id, "error": str(e)})
        return {"status": "placed_unconfirmed", "key": key,
                "order_id": order_id, "error": str(e)}
    if confirmed is None:
        audit(sdir, {**base, "decision": "placed_unconfirmed",
                     "order_id": order_id})
        return {"status": "placed_unconfirmed", "key": key,
                "order_id": order_id}
    ledger_append(sdir, {"ts": _now_iso(), "key": key,
                         "status": "filled", "order_id": order_id,
                         **base})
    audit(sdir, {**base, "decision": "placed",
                 "order_id": order_id, "fill": confirmed})
    return {"status": "placed", "key": key, "order_id": order_id,
            "fill": confirmed}


# ------------------------------------------------------------------ CLI
def _load_json_arg(path):
    with open(path) as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="htmw_client.py",
                                 description="HANDS execution client")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    p = sub.add_parser("prepare")
    p.add_argument("--ticker", required=True)
    p.add_argument("--side", required=True, choices=list(ALL_SIDES))
    p.add_argument("--qty", required=True, type=int)
    p.add_argument("--book", required=True, choices=list(BOOKS))
    p.add_argument("--bot")
    p.add_argument("--out-dir", default=OUTPUT_DIR)
    e = sub.add_parser("execute")
    e.add_argument("--gate", required=True)
    e.add_argument("--snapshot", required=True)
    e.add_argument("--live", action="store_true")
    e.add_argument("--earnings", default=None,
                   help="earnings-latest.json path (default: output/)")
    args = ap.parse_args(argv)

    if args.cmd == "status":
        enabled, cstate, detail = control_state()
        print(f"kill switch: {'ENABLED' if enabled else 'HALTED'} "
              f"({cstate}: {detail})")
        print(f"credentials: HTMW_USER "
              f"{'set' if os.environ.get('HTMW_USER') else 'NOT set'}, "
              f"HTMW_PASS "
              f"{'set' if os.environ.get('HTMW_PASS') else 'NOT set'}")
        print(f"playwright: {'installed' if PLAYWRIGHT_AVAILABLE else 'NOT installed'}")
        print(f"HANDS_LIVE: {os.environ.get('HANDS_LIVE', 'unset')}, "
              f"supervised flag: "
              f"{os.environ.get('HTMW_HANDS_SUPERVISED', 'unset')}")
        return 0
    if args.cmd == "prepare":
        record, problems = assemble_gate_record(
            args.ticker, args.side, args.qty, args.book,
            out_dir=args.out_dir, bot=args.bot)
        print(json.dumps(record, indent=1))
        if problems:
            print("PROBLEMS:", file=sys.stderr)
            for prob in problems:
                print(f"  - {prob}", file=sys.stderr)
            return 1
        return 0
    if args.cmd == "execute":
        gate = _load_json_arg(args.gate)
        snapshot = _load_json_arg(args.snapshot)
        earn_path = args.earnings or os.path.join(
            OUTPUT_DIR, "earnings-latest.json")
        earnings_rows = None
        if os.path.exists(earn_path):
            earnings_rows = _load_json_arg(earn_path).get("rows")
        try:
            receipt = execute_order(gate, snapshot, live=args.live,
                                    earnings_rows=earnings_rows)
        except Refusal as r:
            print(f"[HANDS] REFUSED: {r}", file=sys.stderr)
            return 1
        print(json.dumps(receipt, indent=1))
        return 0
    # no subcommand: the original skeleton demo
    if not PLAYWRIGHT_AVAILABLE:
        print("playwright not installed - client skeleton only. "
              "pip install playwright && playwright install chromium",
              file=sys.stderr)
    client = HTMWClient()
    print(client.place_market_order("NVDA", "buy", 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
