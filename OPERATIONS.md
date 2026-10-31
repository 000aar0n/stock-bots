# Muse operating contract

This file supersedes the original build-day run instructions in README.md.
The 802 registry entries, roles, handcrafted modules, paper competitions and
browser-session execution model remain. Quantity of bots is not evidence of edge.

## Unattended coordinator

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
HANDS remains a dry-run skeleton; no claim of a newly activated execution bridge
is made. Keep the existing browser sessions responsible for execution.

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
- The PROVEN label means research eligibility only: 20 completed trades across
  five sessions. It is not proof of profitability or statistical significance.
- Every arena run has its own log under `output/arena-runs/<UUID>/`. Historical
  bots see only daily candles through the replay date, signal at a close and fill
  at the following session open. Intraday fetches fail closed; present-day tape
  can never substitute. No forced final liquidation is invented.
- Arena results have survivorship/calendar limitations and cannot breed the live
  population. Original arena records remain preserved, but cannot enter live state.
- DARWIN consumes each closed-trade evidence set once. It only breeds supported
  positive-record strategies and benches eligible losers. Offspring apply actual
  parameters/watchlist filters through `bot_runtime.py`; ineffective mutations
  are not minted. A plateau never means the market has been optimized.
- ODDS is explicitly an uncalibrated heuristic, not probability-weighted expected
  profit. Its `ev_score` key remains as a compatibility alias. Missing or
  nonpositive scores are not budgeted. Any budget disagreement blocks allocation.
- JUDGE logs decisions once per source bar. Each decision locks to a same-session-close counterfactual once that actual
  close is available. Missing outcomes stay unscored; indefinite re-marking to
  today's price is removed. These are paper evaluation outcomes, not HTMW P/L. Autonomous
  breeding does not delete JUDGE. Hard risk checks always remain mandatory.

## Validation and runtime

```sh
pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q .
```

Tests prohibit network access and use synthetic data only. The CI workflow runs
these checks on pushes and pull requests. To keep the loop running through host
restarts, Muse should use the existing persistent host's service manager with
restart-on-failure, the repository as working directory, and the command above.
A GitHub push alone does not start a process on Muse's host. Muse owns that host
and should verify `city-status.json` updates and the process is supervised, then
post confirmation in Desk Messages. No paid host or extra secret is required by
this patch.
