# Muse operating contract

This file is an operating reference. It does not supersede README.md, Aaron's
direct rules, or trading-style.md; where anything here conflicts with those,
Aaron's direct rules and trading-style.md win.
The 826 registry entries, roles, handcrafted modules, paper competitions and
browser-session execution model remain. Quantity of bots is not evidence of edge.

## Unattended coordinator (optional, not running)

OPTIONAL: this loop is not running and must not be started except on Aaron's
direct order.
Install Python 3.12+ and `pip install -r requirements.txt` in a virtual environment.
Muse/COURIER must write a fresh, verified HTMW account snapshot to a stable path
using a temporary file and atomic rename. Run:

```sh
python run_city.py --snapshot /absolute/path/account-current.json --loop --interval 60
```

The loop reloads the file every cycle, respects NYSE holidays/DST/early closes,
uses one shared provider cache, runs JUDGE, BOUNCER, budgeting, the factory and
all handcrafted modules, and produces `output/city-status.json` and a digest.
A process lock prevents overlapping coordinators. A failed cycle leaves an empty
action list and a specific NEEDS_DATA reason, then the next cycle retries.
Closing cycles stop new paper entries and close intraday PAPER positions before
session end. They do not claim the HTMW account is flat: Muse must independently
execute and verify its account's end-of-day policy in its browser.

Account snapshot fields (all from an actual account observation):

| Field | Required contents |
|---|---|
| `verified` | `true` only after Muse verifies the account read |
| `snapshot_at` | ISO timestamp with timezone, at most 300 seconds old |
| `portfolio_value` | Reported HTMW value, never a market estimate |
| `buying_power` | Actual displayed buying power |
| `day_change_pct` | Confirmed account daily change, not synthetic portfolio performance |
| `start_value`, `peak_gain` | Confirmed account basis and peak gain; no default guesses |
| `positions` | Complete map of ticker to `{qty, entry}` with exact signed quantity and execution basis |

Missing/masked entries, an expired account read, missing/stale held quotes, or
risk/budget disagreement stop the action list. Hardcoded Friday fixtures are
only build-day demonstrations, never used by `run_city.py`. Candidate lists are
PROPOSALS. Muse verifies the news/earnings restrictions, account state, and every
executed order in HTMW. The runner never turns shadow recommendations into fills.
HANDS was a dry-run skeleton until Tue Nov 3, 2026. It is now wired
behind the rails in the section below, but it cannot place an order
yet: the script credential step in that section is outstanding, so
browser sessions remain responsible for execution until it is done.

## HANDS live status (Tue Nov 3, 2026, Aaron's approval)

Aaron approved flipping HANDS live in chat on Tue Nov 3, 2026
("Wire HANDS live", after tapping the option on a card). That was
the explicit approval the skeleton required. HANDS
(htmw_client.py) is now a gated execution client:

- Mechanism: no HTMW API exists. HANDS drives the real site with
  Playwright (login -> quote page -> trade ticket -> order history
  read back). Dry run remains the default posture.
- An order is placed only through execute_order() and only with a
  complete gate record: a live bot call in output/calls.jsonl,
  JUDGE approval, BOUNCER non veto, ODDS positive EV, allocator
  budget, book tag LONG or DAY; or a documented protective exit
  naming its Protected Momentum rule.
- HANDS recomputes the caps itself from a fresh verified snapshot
  (at most 300 seconds old): $200k gross envelope, 25% single name
  cap, $15k buying power reserve floor, $15k earnings cap on LONG
  entries inside the earnings window, per book envelopes split
  50/50 with no cross book borrowing.
- Kill switch: output/hands_control.json must exist, parse and
  carry enabled: true, checked before every order. A
  output/hands.kill file, a missing file, or unreadable JSON all
  mean HALTED. Nothing ships with the control file enabled; a
  session creates it deliberately per run.
- Idempotency: output/hands_ledger.jsonl keys every order from its
  gate record and the session date. A key already submitting,
  submitted or filled is refused, never resubmitted.
- Audit: every attempt, placed or refused, appends to
  output/hands_audit.jsonl. A submission counts as placed only
  after the order is read back in Order History.
- Live submission additionally requires HANDS_LIVE=1 and
  HTMW_HANDS_SUPERVISED=1 in the run environment.

BLOCKER, stated plainly (verified Nov 3): credentials for script
use. The client reads HTMW_USER / HTMW_PASS from environment
variables only. The Secure Vault copy of the HTMW login serves the
Muse browser's sign in agent, and no tool exports vault values to
a script (1Password is browser only too). What Aaron must do:
supply the HTMW password for script use once, through the secure
entry the main agent presents, so HTMW_USER and HTMW_PASS can be
set in the environment that runs HANDS. Until then live mode
refuses with exactly that reason, and the trade ticket selectors
(which were never verified against the live site) still need
their supervised confirmation run. First live consumer once both
are done: the Wednesday Nov 4, 9:35 a.m. election reaction session,
placing only a gate passed order while the session verifies the
fill independently.

Session integration (recorded Nov 3; the Wednesday one off job
body carries the HANDS paragraph, the six recurring bodies do not
yet): a session may route a gate passed order through HANDS only
when (1) HTMW_USER and HTMW_PASS are set in its environment,
(2) it writes a fresh verified snapshot and assembles the gate
record with `htmw_client.py prepare`, (3) it creates
output/hands_control.json with enabled: true for that run and
removes it (or the kill file decision) when done, (4) it runs
execute with HANDS_LIVE=1 and HTMW_HANDS_SUPERVISED=1, and
(5) it verifies the fill in Order History itself before reporting,
exactly as for a hand placed order. When any of that is
unavailable, the session places the order by hand through the
browser, as before. HANDS never replaces session verification.

## COURIER delivery

The input is `{verified: true, orders: [...]}`. Each order needs an actual HTMW
`order_id` string, exact timezone-bearing execution `date`, uppercase `ticker`,
`side` (buy/sell/short/cover), numeric `qty`, `price`, `fee`, signed net `amount`,
and status `Filled` or `Executed`. Per-order `verified: true` may replace the
top-level flag. Pending/partial/masked/generated/sample orders are rejected.
Order IDs are unique execution identities. An existing legacy ledger fill may
carry a confirmed `legacyId` mapping with unchanged exact execution fields;
never fabricate a mapping or resend a legacy fill as a new transaction.

```sh
python sync_bot.py --input /absolute/path/verified-orders.json
python sync_bot.py --deliver
```

The first command durably queues complete verified executions; it does **not**
mark them delivered. The second uses the existing `MUSE_UPDATE_KEY` and
`TRACKER_URL` environment variables, sends only to the Muse tracker origin,
requires an import receipt, and checks saved state by actual order ID and exact
execution fields before advancing acknowledgments. Do not change the key.
Credentials are never stored in the outbox, packet, logs, or repository. HTTP
redirects are rejected. Timeouts leave the outbox intact; repeat the same command.
Both commands may be combined with `--input ... --deliver`. The coordinator also
accepts `--sync-input ... --deliver` to retry delivery on each cycle.

An optional top-level `post_trade` is one actual account observation with
`verified: true`, `portfolio_value`, and timezone-bearing `snapshot_at`. It is
imported separately from executions. Cash, starting balance and loan fields are
never imported as balance overrides. Official headlines/charts remain confirmed
HTMW reports; paper P/L and estimates never enter account packets.

Do not trust an old `seen-orders.json` list as evidence of delivery: the old
implementation marked generation as delivery. New acknowledgments include a
receipt and execution fingerprint. Reconcile legacy entries against server state.

Read `/api/desk-messages` first on each tracker sync. Keep the permanent messages
and existing authorization conventions. Continue posting CLAUDE status and receipt
there. Never put credentials in messages. ChatGPT replies there directly.

## Research accounting

- Alert repetition earns no P/L or eligibility. One open paper position per
  bot/ticker/source; duplicate entries and flat exits are ignored.
- Ranking uses completed live PAPER round trips, net of modeled $10/order and
  5bps/side friction. Unrealized marks are shown separately, never rank evidence.
- The 20 completed trades across five sessions threshold is research
  eligibility only. It is not proof of profitability or statistical
  significance, and it is not the PROVEN label. PROVEN means 5+ ranked live
  calls with a positive record, as defined in trading-style.md and README.md.
- Every arena run has its own log under `output/arena-runs/<UUID>/`. Historical
  bots see only daily candles through the replay date, signal at a close and fill
  at the following session open. Intraday fetches fail closed; present-day tape
  can never substitute. No forced final liquidation is invented.
- Arena results have survivorship/calendar limitations. When live calls are
  below the breeding threshold, DARWIN may breed from arena standings;
  offspring are stamped ARENA_BRED and carry no live rank until they prove
  themselves live. Original arena records remain preserved, but cannot enter
  live state as live records.
- DARWIN consumes each closed-trade evidence set once. It only breeds supported
  positive-record strategies and benches eligible losers. Offspring apply actual
  parameters/watchlist filters through `bot_runtime.py`; ineffective mutations
  are not minted. A plateau never means the market has been optimized.
- ODDS is explicitly an uncalibrated heuristic, not probability-weighted expected
  profit. Its `ev_score` key remains as a compatibility alias. Missing or
  nonpositive scores are not budgeted. Any budget disagreement blocks allocation.
- JUDGE logs decisions once per source bar. Each decision locks to a same-session-close counterfactual once that actual
  close is available. Missing outcomes stay unscored; indefinite re-marking to
  today's price is removed. These are paper evaluation outcomes, not HTMW P/L. JUDGE is a rules engine
  scored on the judge scorecard. At 20+ scored decisions with a negative
  aggregate record, JUDGE is deleted (judge_scorecard.py --delete; the
  tombstone stops re-minting), and a successor is hand coded from the proven
  bots, their winning logged causes, and the old judge's errors. Hard risk
  checks always remain mandatory.

## Validation and runtime

```sh
pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q .
```

Tests prohibit network access and use synthetic data only. The CI workflow runs
these checks on pushes and pull requests. The loop is currently NOT running.
If, and only if, Aaron directly orders it started, it may be kept running
through host restarts with the existing persistent host's service manager with
restart-on-failure, the repository as working directory, and the command above.
A GitHub push alone does not start a process on Muse's host. No paid host or
extra secret is required by this patch.
