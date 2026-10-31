"""DARWIN: evidence-gated registry breeding, never a claim of optimality.

Only completed live paper trades qualify: 20 trades per bot across at least
five sessions. Arena results and open marks never select production offspring.
Each evidence set is consumed once; --seasons waits for new closed trades.
Supported offspring execute actual mutated parameters via bot_runtime.py.
JUDGE reviews are advisory; breeding never removes the mandatory risk gate.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import hashlib
from storage import atomic_json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(HERE, "output", "bots.json")

MIN_TOTAL_CALLS = 20
MIN_BOT_CALLS = 20
MIN_BOT_SESSIONS = 5
GEN_CAP = 5
EXEMPT_KINDS = {"staff"}  # handcrafted bots compete like everyone else
SIBLING_STRATEGIES = {
    "MOMENTUM": "trend following: buy turning_up above SMA50",
    "BREAKOUT": "buy new 20 day highs on expanding relative volume",
    "DIP": "mean reversion: buy RSI under 35 with a bullish reversal candle",
    "GHOST": "latency hunter: only calls stale price candidates",
}
TIMEFRAME_SWAPS = {"daily": "daily+5m", "daily+5m": "daily",
                   "5m/daily": "daily", "daily+latency": "daily+5m"}


def load_registry():
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def save_registry(reg):
    reg["generated_at"] = datetime.now().isoformat(timespec="seconds")
    reg["count"] = len(reg["bots"])
    counts = {}
    for b in reg["bots"]:
        counts[b["kind"]] = counts.get(b["kind"], 0) + 1
    reg["counts_by_kind"] = counts
    atomic_json(REGISTRY_PATH, reg)


def bot_gen(rec):
    return int(rec.get("gen", 1))


def eligible_bots(registry, standings):
    """Ranked, non exempt bots with at least MIN_BOT_CALLS calls.
    Returns (breeders, cull_pool, elders): elders are gen capped
    and cannot breed but stay in the cull pool's standings print;
    for benching they are treated like anyone else in the pool."""
    by_name = {b["name"]: b for b in registry["bots"]}
    pool = []
    for name, rec in by_name.items():
        if rec["kind"] in EXEMPT_KINDS or not rec.get("ranked"):
            continue
        calls = standings.get(name, {}).get("calls", 0)
        if (calls >= MIN_BOT_CALLS and standings.get(name, {}).get("sessions", 0) >= MIN_BOT_SESSIONS
                and not rec.get("benched")):
            pool.append(name)
    from bot_runtime import supported
    breeders = [n for n in pool if bot_gen(by_name[n]) < GEN_CAP and supported(by_name[n])]
    elders = [n for n in pool if bot_gen(by_name[n]) >= GEN_CAP]
    return breeders, pool, elders


def infer_base_params(rec):
    """Best effort base params from the registry record, so a
    mutation has something honest to mutate."""
    params = {}
    strat = rec.get("strategy", "")
    if "RSI under 35" in strat or "mean reversion" in strat:
        params["rsi_threshold"] = 35
    if "10 point gap" in strat:
        params["gap_threshold"] = 10
    params.setdefault("lookback_days", 20)
    return params


def ticker_pnl(standings, bot):
    """Per ticker paper P&L from the bot's own scored calls."""
    out = {}
    for row in standings.get(bot, {}).get("scored", []):
        out[row["ticker"]] = out.get(row["ticker"], 0.0) + row["pnl"]
    return out


def mutate(parent, variant, standings, rng):
    """Build one offspring record. Returns (record, [mutation notes])."""
    gen = bot_gen(parent) + 1
    name = f"{parent['name']} G{gen}{variant}"
    rec = {"name": name, "kind": parent["kind"],
           "watchlist": list(parent.get("watchlist", [])),
           "strategy": parent.get("strategy", ""),
           "timeframe": parent.get("timeframe", "daily"),
           "ranked": parent.get("ranked", True), "benched": False,
           "gen": gen, "parent": parent["name"]}
    if parent["kind"] == "handcrafted":
        from bot_runtime import handcrafted_params, module_for
        params = dict(parent.get("params") or handcrafted_params(parent, load_registry()))
        rec["module"] = module_for(parent, load_registry())
    else:
        params = dict(parent.get("params") or infer_base_params(parent))
    notes = []

    menu = []
    if "rsi_threshold" in params:
        menu.append("rsi")
    if parent["kind"] != "handcrafted":
        menu.append("lookback")
    for key in params:
        if parent["kind"] == "handcrafted":
            menu.append("constant:" + key)
    if parent["kind"] != "handcrafted" and rec["timeframe"] in TIMEFRAME_SWAPS:
        menu.append("timeframe")
    parts = parent["name"].rsplit(" ", 1)
    if len(parts) == 2 and parts[1] in SIBLING_STRATEGIES:
        menu.append("strategy")
    if len(rec["watchlist"]) > 1:
        menu.append("watchlist")
    rng.shuffle(menu)
    chosen = menu[:2]

    for m in chosen:
        if m.startswith("constant:"):
            key = m.split(":", 1)[1]
            params[key] = max(0.1, params[key] + rng.choice([-1, 1]) * (3 if "RSI" in key else .1))
            notes.append(f"{key} -> {params[key]}")
        elif m == "rsi":
            delta = rng.choice([-3, 3])
            params["rsi_threshold"] = params["rsi_threshold"] + delta
            notes.append(f"RSI threshold {params['rsi_threshold'] - delta} "
                         f"-> {params['rsi_threshold']}")
        elif m == "lookback":
            delta = rng.choice([-5, 5])
            params["lookback_days"] = max(
                5, params["lookback_days"] + delta)
            notes.append(f"lookback window -> {params['lookback_days']} days")
        elif m == "timeframe":
            old = rec["timeframe"]
            rec["timeframe"] = TIMEFRAME_SWAPS[old]
            notes.append(f"timeframe {old} -> {rec['timeframe']}")
        elif m == "strategy":
            sibs = [s for s in SIBLING_STRATEGIES if s != parts[1]]
            new = rng.choice(sibs)
            rec["strategy"] = SIBLING_STRATEGIES[new]
            rec["name"] = f"{parts[0]} {new} G{gen}{variant}"
            notes.append(f"strategy {parts[1]} -> {new} (sibling swap)")
        elif m == "watchlist":
            pnl = ticker_pnl(standings, parent["name"])
            ranked = sorted(rec["watchlist"],
                            key=lambda t: -pnl.get(t, 0.0))
            keep = max(1, math.ceil(len(ranked) / 2))
            rec["watchlist"] = sorted(ranked[:keep])
            notes.append("watchlist narrowed to its best half by its "
                         f"own call history: {', '.join(rec['watchlist'])}")
    rec["params"] = params
    if notes:
        rec["strategy"] = rec["strategy"] + " [offspring mutations: " \
            + "; ".join(notes) + "]"
    return rec, notes


def season_plan(registry, standings):
    ranked_calls = standings["_ranked_calls"]
    breeders, pool, elders = eligible_bots(registry, standings)
    by_name = {b["name"]: b for b in registry["bots"]}
    pnl = {n: standings.get(n, {}).get("pnl", 0.0) / max(1, standings.get(n, {}).get("calls", 0)) for n in pool}
    ordered = sorted(pool, key=lambda n: pnl[n])  # worst first
    q = max(1, math.ceil(len(ordered) * 0.25)) if ordered else 0
    bench = [n for n in ordered[:q] if pnl[n] < 0] if ordered else []
    top = [n for n in ordered[::-1] if n in breeders and pnl[n] > 0][:q] if ordered else []
    return {"ranked_calls": ranked_calls, "pool": pool,
            "breeders": breeders, "elders": elders, "bench": bench,
            "clone_parents": top, "by_name": by_name, "pnl": pnl}


FITNESS_PATH = os.path.join(HERE, "output", "fitness.json")
THERMO_PATH = os.path.join(HERE, "output", "thermometers.json")


def load_calls_for_season():
    from leaderboard import load_calls
    return load_calls(source="live")


def pick_standings(calls):
    """Only completed live paper evidence can select production offspring.

    Arena replays remain research; reusing a training window is not validation.
    """
    from leaderboard import STAFF, compute_standings, split_sources
    live, _ = split_sources(calls)
    st = compute_standings(live, price_fn=lambda symbol: None) if live else {}
    st["_ranked_calls"] = sum(v["calls"] for n,v in st.items() if n not in STAFF)
    return "live", st, live


def winning_causes(bot, calls):
    """The causes on a bot's profitable CLOSED trades: the rule
    firings that actually produced money. Offspring inherit
    these; mutations tune the thresholds around them."""
    from leaderboard import _ref_pnl
    opens = {}
    causes = []
    for c in calls:
        if c["bot"] != bot:
            continue
        key = c["ticker"]
        if c["side"] in ("buy", "short"):
            opens.setdefault(key, c)
        elif c["side"] == "exit":
            op = opens.pop(key, None)
            if op is not None:
                pnl = _ref_pnl(op, c["entry_price"])
                if pnl is not None and pnl > 0:
                    cause = op.get("cause") or op.get("reason", "")
                    if cause and cause not in causes:
                        causes.append(cause)
    return causes


def build_offspring(plan, standings, calls, mode):
    """Clone the plan's parents; stamp causes and origin."""
    offspring = []
    for parent_name in plan["clone_parents"]:
        parent = plan["by_name"][parent_name]
        causes = winning_causes(parent_name, calls)
        rng = random.Random(f"{parent_name}|{bot_gen(parent)}")
        for variant in ("A", "B"):
            rec, notes = mutate(parent, variant, standings, rng)
            if not notes:
                continue  # no executable mutation: never mint a decorative clone
            rec["born_equal"] = True
            rec["fitness"] = None
            rec["hold_style"] = parent.get("hold_style", "intraday")
            rec["inherited_causes"] = causes
            if mode == "arena":
                rec["arena_bred"] = True
            offspring.append(rec)
            print(f"    {parent_name} (${plan['pnl'][parent_name]:+,.0f}) "
                  f"-> {rec['name']}: " + "; ".join(notes))
            if causes:
                print(f"      inherits {len(causes)} winning cause(s), "
                      f"first: {causes[0][:90]}")
            if mode == "arena":
                print("      stamped ARENA_BRED (arena standings, "
                      "unproven live)")
    return offspring


def apply_plan(registry, plan, offspring):
    by_name = {b["name"]: b for b in registry["bots"]}
    for n in plan["bench"]:
        if n in by_name:
            by_name[n]["benched"] = True
    existing = set(by_name)
    born = 0
    for rec in offspring:
        if rec["name"] not in existing:
            registry["bots"].append(rec)
            born += 1
    save_registry(registry)
    return len(plan["bench"]), born


def print_plan(plan):
    for n in plan["elders"]:
        print(f"  ELDER {n}: gen {GEN_CAP}, cannot breed further")
    print(f"  eligible pool: {len(plan['pool'])} bots "
          f"({len(plan['breeders'])} can breed)")
    print("  BENCH (bottom quartile by paper P&L):")
    for n in plan["bench"]:
        print(f"    {n}: ${plan['pnl'][n]:+,.0f}")
    print("  CLONE (top quartile, 2 offspring each):")


# ------------------------------------------------------------- fitness

def _closed_series(calls):
    from leaderboard import STAFF, _ref_pnl
    opens = {}
    series = {}
    for c in calls:
        if c.get("source", "live") != "live" or c["bot"] in STAFF:
            continue
        key = (c["bot"], c["ticker"])
        if c["side"] in ("buy", "short"):
            opens.setdefault(key, c)
        elif c["side"] == "exit":
            op = opens.pop(key, None)
            if op is not None:
                pnl = _ref_pnl(op, c["entry_price"])
                if pnl is not None:
                    series.setdefault(c["bot"], []).append(pnl)
    return series


def _max_drawdown(pnls):
    peak = run = worst = 0.0
    for p in pnls:
        run += p
        peak = max(peak, run)
        worst = min(worst, run - peak)
    return abs(worst)


def fitness_snapshot(standings, calls):
    """One season's fitness record. FITNESS = net paper P&L per
    call (Aaron's pin: the scoreboard is money), with the
    population max drawdown tracked as the guard."""
    from leaderboard import STAFF
    avgs = {}
    total_pnl = total_calls = 0.0
    for name, s in standings.items():
        if name.startswith("_") or name in STAFF or not s["calls"]:
            continue
        avgs[name] = s["pnl"] / s["calls"]
        total_pnl += s["pnl"]
        total_calls += s["calls"]
    ordered = sorted(avgs.values())
    q = max(1, math.ceil(len(ordered) * 0.25)) if ordered else 0
    top_q = sum(ordered[-q:]) / q if q else 0.0
    bot_q = sum(ordered[:q]) / q if q else 0.0
    series = _closed_series(calls)
    max_dd = max((_max_drawdown(v) for v in series.values()),
                 default=0.0)
    best = max(avgs, key=avgs.get) if avgs else None
    worst = min(avgs, key=avgs.get) if avgs else None
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "ranked_calls": int(total_calls),
        "pop_avg_pnl_per_call": round(total_pnl / total_calls, 2)
        if total_calls else 0.0,
        "best_bot": best,
        "best_avg_pnl_per_call": round(avgs[best], 2) if best else 0.0,
        "worst_bot": worst,
        "worst_avg_pnl_per_call": round(avgs[worst], 2) if worst else 0.0,
        "top_quartile_avg": round(top_q, 2),
        "bottom_quartile_avg": round(bot_q, 2),
        "quartile_spread": round(top_q - bot_q, 2),
        "pop_max_drawdown": round(max_dd, 2),
        "benched": 0, "born": 0,
    }


def load_fitness():
    if os.path.exists(FITNESS_PATH):
        try:
            with open(FITNESS_PATH) as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            pass
    return {"optimized": False, "optimized_at_season": None,
            "regime_signature": None, "seasons": []}


def save_fitness(fit):
    os.makedirs(os.path.dirname(FITNESS_PATH), exist_ok=True)
    atomic_json(FITNESS_PATH, fit)


def regime_signature():
    """A fingerprint of the current thermometer states. Any flip
    changes it, which resets the OPTIMIZED flag (Conditioned
    Free Will: the population may act against its conditioning
    when the regime changes)."""
    if not os.path.exists(THERMO_PATH):
        return None
    import hashlib
    with open(THERMO_PATH) as f:
        states = {k:v.get("regime") for k,v in json.load(f).items()}
    return hashlib.sha256(json.dumps(states, sort_keys=True).encode()).hexdigest()[:16]


def _improvement(new, old):
    if old == 0:
        return 0.0 if new == 0 else 100.0
    return 100.0 * (new - old) / abs(old)


def run_seasons(n):
    from leaderboard import load_calls
    print(f"DARWIN - production loop: up to {n} season(s)")
    fit = load_fitness()
    fit["optimized"] = False  # a score plateau is never proof of market optimality
    sig = regime_signature()
    if (fit.get("regime_signature") is not None and sig is not None
            and fit["regime_signature"] != sig):
        fit["optimized"] = False
        fit["optimized_at_season"] = None
        print("  regime change detected (a THERMOMETER state flipped "
              "in the factory digest): OPTIMIZED flag reset, "
              "seasons resume.")
    fit["regime_signature"] = sig
    if fit.get("optimized"):
        print(f"  population is OPTIMIZED for this regime (declared "
              f"at season {fit.get('optimized_at_season')}); breeding "
              "paused until a regime change.")
        save_fitness(fit)
        return 0
    registry = load_registry()
    judge_review(apply=False)  # review evidence; never autonomously remove the risk gate
    for _ in range(n):
        calls = load_calls_for_season()
        mode, standings, subset = pick_standings(calls)
        closed = [r for n, v in standings.items() if not n.startswith("_") for r in v["scored"]]
        evidence = hashlib.sha256(json.dumps(closed, sort_keys=True).encode()).hexdigest()
        if fit.get("last_evidence") == evidence:
            print("  waiting for new completed live trades; unchanged data is not a new season")
            break
        fit["last_evidence"] = evidence
        snap = fitness_snapshot(standings, subset)
        snap["season"] = len(fit["seasons"]) + 1
        snap["board"] = mode
        fit["seasons"].append(snap)
        print(f"  season {snap['season']} ({mode} board): "
              f"{snap['ranked_calls']} ranked calls, population "
              f"${snap['pop_avg_pnl_per_call']:+,.2f} per call, best "
              f"{snap['best_bot']} ${snap['best_avg_pnl_per_call']:+,.2f}, "
              f"top quartile ${snap['top_quartile_avg']:+,.2f}, "
              f"max drawdown ${snap['pop_max_drawdown']:,.2f}")
        # STOP RULE, exactly as specified: two consecutive seasons
        # each improving the top quartile average by less than 2%
        # AND the population max drawdown not worsening.
        seasons = fit["seasons"]
        if (len(seasons) >= 3
                and snap["ranked_calls"] >= MIN_TOTAL_CALLS):
            a, b, c = seasons[-3], seasons[-2], seasons[-1]
            imp1 = _improvement(b["top_quartile_avg"],
                                a["top_quartile_avg"])
            imp2 = _improvement(c["top_quartile_avg"],
                                b["top_quartile_avg"])
            if (imp1 < 2.0 and imp2 < 2.0
                    and c["pop_max_drawdown"] <= b["pop_max_drawdown"]):
                fit["optimized"] = False
                fit["status"] = "observed plateau; unvalidated"
                fit["optimized_at_season"] = c["season"]
                save_fitness(fit)
                print(f"  OBSERVED PLATEAU (not optimality) at season {c['season']}: two "
                      f"consecutive seasons improved the top quartile "
                      f"by under 2% ({imp1:+.2f}%, {imp2:+.2f}%) and "
                      f"max drawdown did not worsen "
                      f"(${c['pop_max_drawdown']:,.2f}). Breeding "
                      "pauses until a regime change.")
                print(f"  fitness history: {len(seasons)} season(s) "
                      f"recorded in output/fitness.json")
                return 0
        if standings["_ranked_calls"] < MIN_TOTAL_CALLS:
            print(f"  cannot breed this season: "
                  f"{standings['_ranked_calls']} ranked calls on the "
                  f"{mode} board, {MIN_TOTAL_CALLS} needed. Production "
                  "first (live sessions or the arena).")
            save_fitness(fit)
            break
        plan = season_plan(registry, standings)
        if not plan["pool"]:
            print(f"  cannot breed this season: no bot has "
                  f"{MIN_BOT_CALLS} calls of its own yet.")
            save_fitness(fit)
            break
        print_plan(plan)
        offspring = build_offspring(plan, standings, subset, mode)
        benched, born = apply_plan(registry, plan, offspring)
        snap["benched"], snap["born"] = benched, born
        print(f"  season {snap['season']} applied: benched {benched}, "
              f"born {born}.")
        save_fitness(fit)
        registry = load_registry()
    save_fitness(fit)
    print(f"  production loop done: {len(fit['seasons'])} season(s) "
          "in output/fitness.json, optimized: "
          f"{fit.get('optimized')}")
    return 0


def judge_review(apply=False):
    """JUDGE REVIEW (Aaron, Sat Oct 31): there is exactly one
    JUDGE and it is judged on its logged decisions like everyone
    else. With at least 20 scored decisions, a negative net
    outcome prints a DELETE JUDGE verdict; deletion is final
    (record preserved as history, no bench, no reinstatement).
    A successor, if ever needed, is hand coded fresh from what
    algos are working at that time (see judge_scorecard.py)."""
    import judge_scorecard
    for line in judge_scorecard.judge_review_lines():
        print(line)
    if apply:
        sc = judge_scorecard.score_decisions()
        v, _why = judge_scorecard.verdict(sc)
        if v == "DELETE":
            print(judge_scorecard.delete_judge())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="run the season for real (default: dry run)")
    ap.add_argument("--seasons", type=int, default=0,
                    help="production loop: run up to N seasons, "
                         "tracking completed-trade evidence and observed plateaus")
    args = ap.parse_args(argv)
    if args.seasons:
        return run_seasons(args.seasons)
    if args.apply:
        return run_seasons(1)

    from leaderboard import load_calls
    calls = load_calls_for_season()
    mode, standings, subset = pick_standings(calls)
    ranked_calls = standings["_ranked_calls"]
    registry = load_registry()

    print("DARWIN - seasons and breeding engine "
          f"({'APPLY' if args.apply else 'dry run, nothing changes'})")
    print("  exempt from breeding and culling: staff bots only "
          "(infrastructure, unranked). Handcrafted bots breed and "
          "can be benched like everyone else.")
    print(f"  fitness: net paper P&L per call (the scoreboard is "
          f"money). Standings source: {mode.upper()}"
          + (" (live calls below threshold; offspring will be "
             "stamped ARENA_BRED)" if mode == "arena" else ""))

    judge_review(apply=args.apply)
    if ranked_calls < MIN_TOTAL_CALLS:
        print(f"  season not runnable yet: {ranked_calls} ranked "
              f"calls on file, {MIN_TOTAL_CALLS} needed "
              f"({MIN_TOTAL_CALLS - ranked_calls} short).")
        made = sorted({c['bot'] for c in subset})
        print("  bots with any ranked calls: "
              + (", ".join(made) if made else "none"))
        print(f"  no bot is eligible: eligibility also needs "
              f"{MIN_BOT_CALLS} calls per bot.")
        return 0

    plan = season_plan(registry, standings)
    if not plan["pool"]:
        print(f"  {ranked_calls} ranked calls on file, but no bot "
              f"has {MIN_BOT_CALLS} calls of its own yet, so nobody is "
              "eligible to breed or be culled.")
        return 0

    print_plan(plan)
    offspring = build_offspring(plan, standings, subset, mode)
    if not args.apply:
        print("  dry run: registry unchanged. Run with --apply to "
              "bench and register the offspring.")
        return 0

    benched, born = apply_plan(registry, plan, offspring)
    registry = load_registry()
    print(f"  APPLIED: benched {benched}, registered {born} "
          f"offspring. Registry now {registry['count']} bots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
