# HTMW Bot City

## Reliability update

Read [OPERATIONS.md](OPERATIONS.md) for the current autonomous runner, verified
COURIER delivery, isolated replays, completed-trade rankings and evidence-gated
breeding. It supersedes conflicting build-day instructions below. Existing roles
and philosophy are preserved; historical test results below are not current
validation or proof of profitability.

Python bots for Aaron's HowTheMarketWorks (HTMW) sim trading account
(portfoliopilot2, fake money), built Sat Oct 31, 2026. They implement
Protected Momentum in code so the numbers come from deterministic
code paths instead of ad hoc session reads.

**The bots read, check and recommend. They do not place orders.**
The only module that could submit orders (HANDS) is a skeleton that
defaults to `DRY_RUN = True` and is not wired end to end. Paper
calls for the leaderboard are logged only when a bot is run with
`--log-calls` (Monday shadow mode), never by test runs.

Data: Yahoo's keyless chart API. Stooq was the original choice but
is unreachable from this VM (connections hang indefinitely,
verified Sat Oct 31), so Yahoo daily and 5 minute candles are the
working source for everything below.

## AETIOMORALISM: the governing doctrine

Aaron's philosophy governs how this city treats its bots. Full
verbatim text: `~/workspace/user/aetiomoralism.md`. Its five
fundamental principles, and how each is implemented here:

1. **Experiential Morality.** Every bot judges the market only
   through its own experienced data: its watchlist, its
   timeframe, its candle history. No bot's read carries inherent
   authority, which is why WATCHER and SHADOW cross check each
   name and disagreements print CONTESTED instead of trading.
2. **Moral Non-Hierarchy.** No bot is inherently superior by
   origin. Handcrafted, factory, arena bred, gen 1 or gen 5,
   origin confers nothing. ACTIONS are judged: individual calls
   on THE BOARD. A bot's existence is never declared worthless:
   benching is a deployment decision about a strategy's recent
   actions, every benched bot keeps its full record, and any
   benched bot can be reinstated by a regime change or a new
   season.
3. **Conditioned Free Will.** Bots are conditioned by their
   data and parameters (their past) but not bound by them.
   Mutations, regime resets (a THERMOMETER flip clears the
   OPTIMIZED flag and seasons resume), and Aaron's or JUDGE's
   overrides are the mechanisms by which the population acts
   against its own conditioning.
4. **Internal Achievement.** There is no single yardstick. Each
   bot is measured against its own mandate: BOUNCER by losses
   avoided, SCALES and the pair bots by gap capture, TRIPWIRE by
   detection speed and accuracy, snipers by their one name. THE
   BOARD prints standings per role as well as overall, and a
   bot's fitness for breeding is judged within its role first.
5. **Independent Significance.** Unranked and quiet work still
   counts. The warden checks that never fire, SEXTANT's daily
   line, COURIER's dedupes: their value does not depend on
   recognition or a leaderboard position. The staff tier is
   unranked by design, not by failure.

**The objective pin, above every principle:** the city's
purpose is to maximize money. Fitness is net paper P&L per call
with the drawdown guard in DARWIN's stop rule; when two designs
conflict, the one that makes more with less drawdown wins. The
philosophy governs how bots are treated; the scoreboard is
money.

**Cause logging.** Every paper call in `output/calls.jsonl`
carries a `cause` field: the specific signal and readings that
fired (for example "RSI 28.4 + bullish engulfing + above
SMA200"), separate from the free text reason. Until a bot passes
structured readings separately, its stated reason serves as its
cause and `log_call` copies it over, so no call exists without
one. DARWIN reads causes: offspring inherit the parent's
winning causes (the causes on its profitable closed trades),
and mutations tune the thresholds around those causes.

**Production loop and the OPTIMIZED stop rule.** Production
continues until the population is fully optimized, and
"optimized" is measurable, not a vibe: DARWIN's `--seasons N`
mode evaluates the standings, applies one breeding and culling
round (or reports why it cannot), re evaluates, and repeats,
recording every season in `output/fitness.json` (population
average paper P&L per call, best and worst bot, quartile spread,
max drawdown, benched and born counts). The population is
declared OPTIMIZED for the current regime when two consecutive
seasons each improve the top quartile's average P&L per call by
less than 2 percent AND the population max drawdown does not
worsen. Breeding then pauses; a regime change (any THERMOMETER
flipping its state in the factory digest) resets the flag and
seasons resume.

**The arena.** Live calls accumulate slowly, so `arena.py`
(REWIND's proving ground) replays any handcrafted bot's own
module over historical daily candles, day by day, with the data
sliced to what the bot would have seen. Arena calls are written
to `calls.jsonl` with source `backtest` (live calls carry source
`live`). THE BOARD keeps two views: live standings are the
official rank; arena standings print separately, labeled arena
results. DARWIN may breed from arena standings only when live
calls are below the eligibility threshold, and any bot bred
that way is stamped ARENA_BRED in the registry until it proves
itself live. An arena champion is not a live champion.

**THE EQUALITY PROTOCOL.** "Nothing is born superior.
Everything is equal until proven that some are better." Equal
birth: every bot, factory, handcrafted, any gen, starts with
the same $10k reference size, the same data access, no starting
rank, no trust weight, no priority in any digest or budget.
Every registry record carries `born_equal: true` and a
`fitness` field that starts null (unproven), never 0 ranked.
Proof is the only rank: THE BOARD lists bots with fewer than 5
calls in a separate UNPROVEN section, never interleaved with
proven standings, and DARWIN cannot bench or breed the unproven
(insufficient evidence is not failure). Even JUDGE and the staff
engines hold no naked authority: where HERALD or JUDGE quote a
bot's record, the quote carries its proven record (calls, P&L
per call) or the word UNPROVEN.

**Day trader first.** The city is day trader first because the
standing order is profit every day and overnight gaps are what
ambushed the book on Oct 29 and 30; overnight risk is the
exception a position earns, not the default. Every trading
bot's calls assume a same day exit (its exit rule is reachable
inside the session: the -8 percent rule, a target, a reversal
signal, or the close itself, whichever comes first). A bot
whose design honestly needs days declares `hold_style: "swing"`
in the registry and in its roster design note, with the reason
(the pair bots and ANVIL style mean reversion are the standing
examples). JUDGE's report and HERALD's summary both count how
many active calls are intraday versus swing, so the mix is
always visible.

## The staff (unranked)

| Bot | Module | Job |
|---|---|---|
| FALCON | scanner.py | eyes on the whole market: wide scan, pair gaps, latency candidates, core intraday TA |
| WICK | ta.py | reads the candlesticks: patterns, RSI, MACD, SMAs, ATR, trend, turning_up / falling_knife heuristics |
| JUDGE | rules.py | runs Protected Momentum by the book: PROTECT, brakes, caps, exits, candidates with loss plans |
| HANDS | htmw_client.py | does the clicking (Playwright skeleton, dry run) |
| BOUNCER | risk_warden.py | independent watchdog: re-checks JUDGE on separate code, prints DISAGREEMENT when they differ |
| SCALES | arb_monitor.py | weighs the pairs: 5 and 20 session gaps, stretch flags, eligibility windows |
| SIREN | earnings_bot.py | warns before prints: hardcoded calendar, exposure vs the $15k cap |
| REWIND | backtester.py | replays old tape through the signal rules, honestly labeled limits |
| COURIER | sync_bot.py | carries verified order packets to the tracker, deduped by order ID |
| HERALD | reporter.py | announces the score, score first, plain words, no em dashes |
| TREASURER + LEDGER | allocator.py | the budget sheet, dual sign off (below) |
| ODDS | odds.py | the projector: expected value ranking (below) |
| TRIPWIRE | tripwire.py | the speed bot: intraday squeeze, latency and defensive trip alerts |
| THE BOARD | leaderboard.py | paper leaderboard on a fixed $10k reference size per call |

## Ranked traders

Ranked on THE BOARD: FALCON, JUDGE, SCALES, BOUNCER (scored on
losses avoided: if a name rises after its exit call, that counts
negative), the 9 sector specialists, and every bot the factory
generates (snipers, strategists, pair bots, watchers, shadows).
Staff are listed unranked. **Rankings start from Monday shadow
mode: a bot earns its rank, it is not assigned one.**
`output/calls.jsonl` holds the paper calls (format in its header).

## Sector specialists (specialists.py, one config driven module)

CIRCUIT (semiconductors), STACK (big tech and software), SATOSHI
(crypto and fintech), REACTOR (nuclear and energy), PULSE (biotech
and healthcare), AEGIS (defense), CART (consumer and retail), VAULT
(banks and payments), ROCKET (high beta momentum bench). Each runs
WICK and FALCON's data layer on only its names, prints its own
sector report (closes, 1d and 5 session changes, flags, sector
latency candidates, SIREN earnings dates), and logs paper calls
under its own name with `--log-calls`.

```
python3 specialists.py              # all nine
python3 specialists.py --only CIRCUIT
```

## The factory (bot_factory.py): 202 factory bots, 302 registered in total with the handcrafted hundred

`python3 bot_factory.py` generates the registry
(`output/bots.json`: name, kind, watchlist, strategy, timeframe,
ranked, benched) and `--run` executes every bot's signal logic
against one shared data fetch per symbol, printing a digest where
only bots with something to say get a line.

Population (202): 15 staff, 9 specialists, 20 SNIPER bots (one per
core name: entry on turning_up plus latency windows, exit on
falling_knife or the -8% rule), 36 STRATEGIST bots (per sector:
MOMENTUM trend following, BREAKOUT new 20 day highs on expanding
volume, DIP mean reversion, GHOST latency hunter), 8 PAIR bots
(call a pair only at a 10 point gap or more and only when SCALES'
eligibility allows, logged PAPER ONLY when the news check is still
manual), 4 THERMOMETER bots (SPY, QQQ, IWM, DIA: market regime,
risk on / risk off / choppy, never trade; JUDGE and HERALD quote
the QQQ line), 55 WATCHER bots and 55 SHADOW bots (coverage rule).

**Coverage rule: no stock and no group is watched by fewer than
two bots, ever.** Every wide universe ticker has a WATCHER (daily
candles, momentum) and a SHADOW (independent second opinion:
5 minute TA when intraday data exists, otherwise a daily mean
reversion strategy, a genuinely different code path). When the two
disagree (one says entry, the other falling knife), the digest
prints a CONTESTED line and neither logs a call. The rule exists
because single source numbers burned us before: phantom fills and
wrong interim batches in the session reports.

**Seasons:** bots get culled and cloned by THE BOARD over time.
`python3 bot_factory.py --cull` benches the bottom 10% of ranked
bots by paper P&L (sets `benched` in the registry; the runner skips
benched bots), but only once at least 20 ranked calls exist; before
that it prints "not enough calls to cull yet." The full breeding
mechanic (quartile culls plus mutated offspring) lives in DARWIN,
below.

## Handcrafted bots (handcrafted/, Phase 7)

One hundred bots written one at a time, each its own file with
hand tuned logic, not factory parameter clones. The full roster
(names, files, universes, hold styles, one line logic, and a
design note justifying each bot's thresholds against its names'
actual behavior) lives in `handcrafted/ROSTER.md`; the machine
readable roster is `handcrafted/roster.json`, which the factory
loads at registry build time. They are registered in
`output/bots.json` with kind `handcrafted`, gen 1, `born_equal`
true, `fitness` null, and log paper calls to the same
`output/calls.jsonl` format behind the same `--log-calls` flag
(shorts use side `short`, which the leaderboard scores
natively). Design grid: strategy families (momentum, mean
reversion, breakout, fade and short, gap play, range trade,
relative strength, volume climax, volatility squeeze, earnings
drift, baskets, index relative, swing, intraday) crossed with
scopes and timeframes. 51 declare intraday, 48 declare swing
with reasons, SEXTANT declares none.

The first six, Aaron's original peasant order:

| Bot | File | Craft |
|---|---|---|
| MOSAIC | handcrafted/mosaic.py | NVDA only. Multi timeframe confluence: entry only when daily close is above SMA50 AND 5 minute turning_up AND daily relative volume over 1.5 all agree; it names the failed leg when they do not. Exits on 5 minute falling_knife or the -8% rule |
| ANVIL | handcrafted/anvil.py | Oversold mega cap mean reversion on the core 20: RSI(14) under 32 AND a hammer or bullish engulfing AND price above SMA200 (quality only, no broken names). Exit at RSI over 55 or the -8% rule |
| FLASH | handcrafted/flash.py | Earnings reaction, off SIREN's calendar: a name gaps over 5% on its reaction session and HOLDS above the gap midpoint on rising volume, or there is no call. Faded gaps are traps (the RDDT / RBLX lesson) |
| MIRROR | handcrafted/mirror.py | The short side craftsman: shorts only the fade (up 15%+ in 5 sessions, bearish engulfing or shooting star, relative volume 1.2+). Every call carries a "news unverified" flag because keyless news checking is unreliable; a human clears the news. Exit at +5% against or two green closes |
| TWINSMITH | handcrafted/twinsmith.py | Pairs craftsman working only SOFI/HOOD and COIN/MSTR: gap over 15 points (stricter than SCALES' 10) AND a reversal candle on the stretched leg, under the same earnings bars as SCALES (both pairs barred through Mon Nov 2, 2026) |
| SEXTANT | handcrafted/sextant.py | Regime navigator, never trades: one line of positioning advice from the four thermometers plus core breadth (risk on = full budget, choppy = half, risk off = arb and defensive only), written to output/sextant.json for JUDGE to quote |

```
python3 handcrafted/mosaic.py        # each takes --log-calls like the staff
python3 handcrafted/sextant.py       # prints one line, writes output/sextant.json
```

## DARWIN: seasons and breeding (evolution.py)

`python3 evolution.py` runs a season over THE BOARD's standings.
Default mode is a DRY RUN: it prints the breeding plan (who would
be benched, who would be cloned, and each offspring's mutated
config) and changes nothing. `--apply` runs it for real.

- Eligibility: at least 20 ranked calls on file in total, AND at
  least 5 calls for an individual bot before that bot can breed or
  be culled. Below that DARWIN prints exactly what is missing and
  exits 0.
- Cull: the bottom quartile of eligible ranked bots by paper P&L
  is benched (`benched` in the registry; the factory digest stops
  running them).
- Breed: the top quartile each produce 2 offspring, registered
  with gen = parent gen + 1 and a `parent` field. Mutations come
  from a fixed menu: RSI threshold +/-3, lookback window +/-5
  days, timeframe swap (daily <-> daily+5m), strategy swap to a
  sibling strategy, watchlist narrowed to the parent's best
  performing half of tickers by its own call history. Offspring
  names are the parent name plus a generation suffix, e.g.
  CIRCUIT DIP G2A and CIRCUIT DIP G2B.
- Gen cap: no bot exceeds gen 5. Gen 5 bots are ELDERs, printed
  as such, and cannot breed further.
- NO EXEMPTIONS by origin (Aaron's override, under Moral
  Non-Hierarchy): handcrafted bots breed and can be benched
  under exactly the same thresholds as factory bots. Only staff
  sit seasons out, because they are infrastructure, unranked,
  and outside THE BOARD entirely. Under the Equality Protocol
  the UNPROVEN (under 5 calls of their own) can neither breed
  nor be benched: insufficient evidence is not failure.
- Causes: offspring records carry `inherited_causes`, the
  parent's winning causes from its profitable closed trades, and
  mutations tune the thresholds around those causes (see the
  AETIOMORALISM section).
- Arena seasons: while live ranked calls are below the
  threshold, a season may run on arena standings; offspring are
  stamped `arena_bred` in the registry until they prove
  themselves live.
- Production loop: `python3 evolution.py --seasons N` runs the
  loop and tracks fitness in `output/fitness.json`, under the
  OPTIMIZED stop rule defined in the doctrine section (two
  consecutive seasons improving the top quartile's average P&L
  per call by under 2 percent, with max drawdown not worsening;
  a THERMOMETER regime flip resets the flag).
- Honest limit: offspring are registered in `output/bots.json`
  and carried over factory regenerations (records with a `parent`
  field survive), and THE BOARD ranks any calls logged under
  their names, but the factory digest does not yet execute
  offspring mutated params as distinct logic. Wiring that in is a
  later phase.

## Core intraday list (FALCON)

Two speeds: the wide scan runs on daily candles for discovery. The
`CORE_INTRADAY` list also gets TA on 5 minute candles for timing,
with the report marking which timeframe drives each turning_up or
falling_knife flag. The 20 names are kept as a default and were
chosen for liquidity and tradable volatility, not strict market
cap rank: AAPL, NVDA, MSFT, GOOGL, AMZN, META, AVGO, TSLA, LLY,
JPM, WMT, V, XOM, COST, AMD, PLTR, MU, COIN, MSTR, NOW. AAPL and V
are in the scan universe because the core list needs them.

## Loss side first (Aaron's steering)

The build is weighted toward not losing: exit rules, daily brakes,
position caps, falling knife blocks and latency verification are
the priority features, entries second. Concretely: JUDGE prints
every buy candidate with its exit trigger and the current brake
state attached, and prints it BLOCKED when PROTECT mode or the
brake forbids entries. Falling knife names are never candidates.
BOUNCER re-derives every risk verdict on independent code and the
two engines cross check each other on every run.

## The budget: TREASURER and LEDGER (allocator.py)

TREASURER proposes the budget from the snapshot plus JUDGE's
candidate list: reserve held back ($10k in buy mode, $15k floor
normally), total deployable, and per name budgets. Single names
are funded top down by ODDS expected value until the deployable
runs out; **any candidate with a negative EV score is skipped, no
matter how loud its bot is.** Pairs split what remains by gap
strength. Every budget respects the 25% single name cap and the
$15k earnings cap inside the earnings window. LEDGER verifies the
sheet against the raw snapshot with its own arithmetic. Agreement
prints one BUDGET SHEET; disagreement prints both numbers and the
sheet uses the SMALLER deployable, flagged DISAGREEMENT. Dual sign
off or the smaller number wins, no exceptions.

**Speed wiring: the morning budget sheet is PRE AUTHORIZATION.**
TREASURER and LEDGER settle the budget before the open, so when
TRIPWIRE fires during the day, JUDGE and HANDS do not wait on
budgeting; they only verify the account state and the fill.
Thorough on account numbers, fast on market detection. JUDGE
consumes the sheet via `output/budget.json` (fields: reserve,
deployable, per_name, caps); the wiring is the shared file for now.

```
python3 allocator.py                 # normal reserve, Fri fixture
python3 allocator.py --buy-mode      # $10k reserve
python3 allocator.py --buy-mode --sample-candidates   # test mode
```

## ODDS (odds.py)

For every candidate the other bots surface, ODDS computes an
expected value score from data we actually have: expected move
size (ATR as a percent of price plus the live move in progress),
momentum strength (distance above SMA20 and SMA50, RSI zone,
relative volume), catalyst flags (latency counts for, earnings
inside 2 sessions counts against unless it is a deliberate
reaction play), and a downside estimate (distance to the nearer
of the -8% exit and the 20 day low). EV = expected gain minus
expected loss, ranked high to low. **Hard rule: ODDS ranks, it
never promises. The outputs are estimates from volatility, not
predictions.**

## TRIPWIRE (tripwire.py)

Poller for market hours (`--loop --interval 60`; `--once` for
tests). Watches the core 20 plus every held name on Yahoo intraday
bars and fires loudly on: a squeeze (move of 3% or more within
15 minutes on relative volume of 2x or more), a fresh latency
candidate on a watched name, or a held name dropping 3% or more
within 15 minutes (the defensive trip). Alerts append to
`output/tripwire.jsonl`. Detection speed is seconds to a minute;
**execution speed is capped by the HTMW website itself**, and
Monday shadow mode will measure the real lag.

## Latency edge (sim only)

HTMW quotes are 15 minutes delayed; FALCON reads live prices. A
name whose live price moved sharply in the most recent window
(last ~30 minutes of 5 minute bars, flag at 2% or more; daily
fallback flag at 4% or more) is a `latency_candidate`: the sim may
still be showing, and filling near, the older price. Every
candidate carries the note to verify against the price HTMW
displays before any order. Monday shadow mode tests the fill
mechanics: during a fast mover, record the live price at decision
time, the price HTMW displays, and the actual fill. The honest
limit: this edge, if it exists, is an artifact of the sim's
delayed feed and does NOT transfer to real money brokers, where
orders fill at live prices. It must not be counted in the real
trading scale up case.

## Monday shadow mode plan

1. Before the open: FALCON scan, JUDGE on a fresh snapshot,
   BOUNCER cross check, TREASURER and LEDGER settle the budget
   sheet (pre authorization), SIREN prints the earnings warnings.
2. The scheduled agent session executes the plan as already
   ordered (including Aaron's CVNA full exit) and cross checks its
   account reads against the bot outputs. Disagreements resolve in
   favor of the live account read and get reported.
3. Bots run with `--log-calls` during shadow mode so THE BOARD
   starts ranking. TRIPWIRE runs `--once` per session (or `--loop`
   if a session hosts it) and any fast mover gets the three price
   latency test.
4. Bots place orders only after BOTH: Aaron explicitly approves
   flipping HANDS' DRY_RUN off, and credentials are supplied for
   script use as environment variables. Playwright also needs
   installing first (`pip install playwright && playwright
   install chromium`).

## Known limits

- HTMW has no API; automation drives its website. Quotes are
  15 minute delayed, orders after the close fill at the next open,
  and a pending sell does not free buying power until it fills.
- Yahoo is a free, keyless, unofficial source: it can rate limit
  (HTTP 429, handled with retries) or change without notice.
- Candlestick and TA signals are heuristics, not predictions.
- JUDGE and SCALES cannot check the news/earnings disqualifier
  behind a pair gap beyond the encoded windows; that check stays
  manual.
- REWIND's replay: daily candles only, fills at the close, no
  slippage beyond the $10 per order commission, fractional shares,
  survivorship in the symbol list. In its first test (last ~182
  days to Oct 30, 2026) the naive turning_up strategy LOST money
  on both test names (NVDA and CVNA, see test results). Treat the
  signals accordingly: they are inputs, not an edge by themselves.
- ODDS expected values are estimates built from volatility and
  recent action; a big earnings day inflates ATR and can flatter
  a name's expected gain (GPN after its Oct 30 print is the
  standing example).

## First test results (Sat Oct 31, 2026, Fri Oct 30 closes)

- FALCON: 55 symbols, 0 errors. Top 5 session movers: CVNA
  +18.13%, CPRI +17.71%, GPN +16.93%, REGN +15.26%, SOFI +14.68%.
  Latency candidates: INTC +3.19%, COIN +2.24%, SMCI +2.23%,
  RIOT +2.19% (last ~30 min of Friday's session).
- JUDGE on the Fri fixture (day change -9.3%): PROTECT ON, full
  brake, buying power $3,691.49 under the floor, cap violations
  CVNA 56.3% (full exit directive shown) and SOFI 27.5%, exit
  flags NVDA, AVGO, AMZN, MSTR (two straight red closes), both
  arb candidates printed BLOCKED by the full brake with their
  loss plans attached.
- BOUNCER: agreed with JUDGE on every check.
- SCALES: SOFI/HOOD 5d gap +25.28 (20d +30.89) and AMD/INTC
  +22.06 (20d +24.53), both stretched and both BARRED through
  Mon Nov 2 on earnings. No other pair stretched.
- SIREN: PLTR Mon Nov 2 (not held), RIOT Wed Nov 4 (not held),
  GPN Thu Nov 5 held at $9,684 of the $15k cap.
- ODDS: GPN EV +16.54, INTC +8.30, COIN +3.75, RIOT +3.28,
  SMCI +2.24 (estimates; GPN flattered by its earnings spike).
- Allocator, Fri fixture: normal mode deployable $0.00 (buying
  power is under the $15k reserve), TREASURER and LEDGER agree.
  Buy mode: deployable $1,308.51, split SOFI/HOOD $698.76 and
  AMD/INTC $609.75. Sample candidate test: EV top down funding
  put the full $1,308.51 on GPN (top EV) and $0 on the rest.
- TRIPWIRE --once: watching 26 names, fired one LATENCY alert
  (COIN) from Friday's data, exit 0.
- Specialists: all nine ran; the only TURNING_UP name in any
  sector was GPN (VAULT). Sector latency candidates: SMCI and
  INTC (CIRCUIT), COIN and RIOT (SATOSHI).
- REWIND: NVDA return -18.9%, max drawdown 28.5%, win rate 33%,
  12 trades. CVNA return -28.9%, max drawdown 37.1%, win rate
  27%, 11 trades. The naive signal strategy lost on both.
- COURIER: two SAMPLE orders built into packets; a second run
  skipped both as duplicates. Sample data lives in
  samples/sample-orders-SAMPLE.json and its own seen file, never
  mixed with real data.
- Factory: registry 202 bots. Digest on Fri data: all four
  thermometers risk off (breadth 40%); pair bots printed both
  stretched pairs as BARRED; strategist hits included CIRCUIT
  GHOST (SMCI, INTC), SATOSHI DIP (HOOD), REACTOR BREAKOUT
  (XOM, CVX, LNG). No CONTESTED lines on this dataset (no name
  had one coverage bot saying entry while the other said falling
  knife). Cull correctly refused: 0 ranked calls, 20 needed.
- THE BOARD: no calls yet, rankings open Monday.
- HERALD: printed the full summary with the QQQ regime line
  (risk off) and BOUNCER's agreement.


## ADDENDUM (Sat Oct 31, 2026, Aaron by voice): bots drive Monday, hybrid nights
- Aaron confirmed the bot city is the top development priority, and that JUDGE supervises every buy the bots recommend. Nothing trades without JUDGE approval and a BOUNCER non veto.
- Monday Nov 2 is the bots' first LIVE TEST DAY: bot calls that JUDGE approves, BOUNCER does not veto, and ODDS ranks positive EV become the sessions' action list (alongside the fixed Monday steps). Sessions still place and verify orders through the browser; HANDS stays in dry run. Every bot driven trade is reported with the bot's name and cause.
- HYBRID overnight policy is now the standing EOD rule: the day book goes flat by the close. Only a winners sleeve may ride overnight: position up with a cushion, no earnings within 2 sessions, source PROVEN (5 or more ranked live calls, positive record) or a named main book swing call, sleeve capped at about one third of the book. Intraday bots never ride. Swing bots ride only through the sleeve test. Stat arb pairs are exempt.


## ADDENDUM 2 (Sat Oct 31, 2026): wide fence, rivals, captains, one JUDGE on the record

### The fence is wide: 150 names (see UNIVERSE.md)
Standing coverage grew from 55 to 150 liquid names across every
sector in the widened universe. Penny fence: standing coverage
requires a real stock, price generally above $5 and real daily
dollar volume. UMAC, ONDS, AMPX, NUWE and BRAI are explicitly
excluded from standing coverage (scanner.py EXCLUDED_PENNY); they
stay scan only, in the day trade sleeve's world, with no bots
minted on them.

### Rivals on every name
Every covered name now has four competing brains: its WATCHER
(daily momentum), its SHADOW (5 minute or daily mean reversion),
a RAIDER (breakout rival: prior 10 day high, relative volume at
or above 1.3, RSI under 75) and an ANCHOR (mean reversion rival:
at least 1.2 ATR below SMA20, RSI at or under 42, green reversal
day). Different logic, different parameters, same tape. High beta
names outside the core 20 (OKLO, SMR, NNE, RIOT, IONQ, RKLB,
SMCI, HOOD) also get SNIPERs. Each sector patch keeps its
specialist plus the four strategist variants (MOMENTUM, BREAKOUT,
DIP, GHOST), so every patch runs at least five section level
brains plus four per name.

### The hierarchy: section captains

```
        bot calls (patch bots: watchers, shadows, rivals,
        snipers, specialists, strategists, pair bots)
                          |
                    SECTION CAPTAINS
        aggregate the section, pre rank by proven record
        or UNPROVEN, flag CONTESTED, escalate only the best
                          |
                        JUDGE
              final rules gate (one judge, see below)
                          |
              TREASURER + LEDGER (budget)
                          |
                   sessions execute
```

Captains (kind "captain", born equal, fitness null, ranked on
THE BOARD by the outcomes of the calls they escalate, which is
their mandate): CAPTAIN CIRCUIT (semis), CAPTAIN STACK (big
tech), CAPTAIN SATOSHI (crypto and fintech), CAPTAIN REACTOR
(nuclear and energy), CAPTAIN PULSE (biotech and health),
CAPTAIN AEGIS (defense), CAPTAIN CART (consumer), CAPTAIN VAULT
(banks and payments), CAPTAIN ROCKET (high beta), CAPTAIN PAIRS
(stat arb pairs). In the factory digest each captain prints its
escalations with the source bot's record quoted (calls and P&L
per call) or the word UNPROVEN, and names any CONTESTED tickers
it held back inside its section.

### JUDGE accountability: one judge, and it can be deleted
There is exactly ONE JUDGE. No shadow challenger, no second
variant, no swap. judge_scorecard.py logs every JUDGE decision
(approve or block) and scores it on the $10k paper basis:
approvals by their realized paper P&L, blocked calls by what
they would have made in shadow. evolution.py's season review
runs a JUDGE REVIEW: under 20 scored decisions it prints
"insufficient decisions" and nothing happens. With 20 or more,
if approvals lost money in aggregate, or blocked calls would
have made clearly more than approvals made, the verdict is
DELETE JUDGE. Deletion is final: the record leaves the active
registry, a tombstone (output/judge_deleted.json) stops the
factory from re-minting it, and the scorecard is preserved as
history only. No bench, no reinstatement.

Succession principle (Aaron): if JUDGE is ever deleted, "we can
code a new one based on what algos are working." A successor is
hand built fresh at that time, its rules drawn from the evidence
of what is producing then: the proven bots, their winning logged
causes, and the old JUDGE's scorecard of what it got wrong. No
automatic generation, and no successor is prebuilt.
