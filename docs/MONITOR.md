# Bot City monitor

Public site: https://000aar0n.github.io/stock-bots/

The 3D city and interactive map use the same complete registry. Search by bot,
ticker or strategy; filter by district, book or role. The page checks the
published `data.json` once a minute while visible, and on manual Refresh. Failed
requests preserve the last validated snapshot. No price or account data is
requested by this public page.

## Read the timestamps

- **Snapshot** is the time this public export was generated.
- **Runner heartbeat** is copied from `output/city-status.json`. Rebuilding the
  page never refreshes this timestamp. Missing heartbeat says unconnected;
  older than five minutes says old, even if the page itself was just checked.
- **Last paper event** is the timestamp of the last production shadow call.
- **Last successful check** means the browser fetched published data successfully.

The Board ranks completed shadow round trips using $10,000 reference sizing,
modeled $10 commissions per side and 5 bps slippage per side. Arena/backtest
results remain separate. Cached registry fitness is never promoted into the
production scoreboard. A 20-trade/five-session threshold is an evidence
threshold, not proof of profitability. Summed strategy results overlap and are
not HTMW account P/L. Zero completed trades show unavailable P/L.

## Muse host activation

The page is deployed independently of the trading process. A GitHub merge does
not start the runner. On Muse's persistent host, pull main, keep the verified
account snapshot and existing secrets in their current locations, and follow
`OPERATIONS.md` to run the coordinator under supervision:

```
python run_city.py --snapshot /path/to/fresh-verified-account.json --loop --interval 60 --publish-monitor
```

Each cycle exports the allowlisted public monitor fields. With the host's
existing `GH_TOKEN` or `GITHUB_TOKEN` (repository contents permission),
`--publish-monitor` updates **only `docs/data.json`** on main at most once every
five minutes and verifies the committed contents. The repository's existing
Pages deployment publishes the static site from `docs/`; check its deployment
and public snapshot timestamp after activation. No credentials are sent to Pages; the publisher uses only the
GitHub API, refuses redirects, and never uses `MUSE_UPDATE_KEY`. This does not
change the host's environment variables or create a credential.

Without a GitHub credential the runner continues and writes the local public
export; remote updates remain unavailable. Muse can publish the sanitized
`docs/data.json` through its existing authenticated GitHub workflow instead.
Never commit account snapshots, tokens, raw fills, budget files or private logs.
Check the published runner timestamp to verify activation rather than assuming
the page's availability proves the bots are running.

For a manual build from local source stores:

```
python docs/build_page.py
```

The exporter is read-only against the registry and paper logs. It never runs
JUDGE, fetches market prices, resolves outcomes, modifies bot status or trades.
