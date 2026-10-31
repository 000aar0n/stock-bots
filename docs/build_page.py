#!/usr/bin/env python3
"""build_page.py - generate the Bot City Monitor page (docs/index.html).

Reads the live registry (output/bots.json) and the sector patches in
specialists.py, assigns every bot to exactly one city zone, and writes
a cyber city HTML page whose hero is a real 3D rendered city
(Three.js via CDN, the only external reference allowed): one building
per bot in 13 sector districts. No account names, no credentials, no
portfolio values anywhere on the page.

Performance wiring (Aaron, Sat Oct 31, 2026): every bot row also shows
its record from the city's real stores, read at build time:
  - THE BOARD standings (leaderboard.py) over the calls log written by
    --log-calls at output/calls.jsonl, live source only for the
    official line; backtest source renders as a labeled ARENA badge,
    never as official standings.
  - output/bots.json fitness fields as a fallback (all null pre
    Monday; a bot with no ranked live calls shows "no calls yet",
    never invented numbers).
  - judge_scorecard.py output for JUDGE's own row.
Any missing store degrades to "no calls yet", never a build failure.

Fullscreen + tracked P/L (Aaron, Sat Oct 31, 2026): the 3D stage is a
100dvh hero with the header stats overlaid on the canvas and a
Fullscreen API button; the header carries a CITY P/L strip (total net
P/L, completed live trades, best and worst bot) computed from the same
live standings, per bot P/L renders as a signed green/red figure on
every card and panel row, and buildings of bots with completed trades
are tinted green (net profit) or red (net loss) in the 3D scene.
ARENA figures never enter the official strip.

Run: python3 docs/build_page.py
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REGISTRY = os.path.join(ROOT, "output", "bots.json")
OUT = os.path.join(HERE, "index.html")

sys.path.insert(0, ROOT)
try:
    from specialists import SPECIALISTS
except Exception:  # fallback: the patches as of build day
    SPECIALISTS = {
        "CIRCUIT": {"sector": "semiconductors", "tickers": [
            "NVDA", "AVGO", "AMD", "MU", "SMCI", "INTC", "MRVL", "QCOM",
            "TXN", "AMAT", "LRCX", "KLAC", "ADI", "TSM", "ARM", "ASML",
            "ANET", "CDNS", "SNPS", "SNDK", "LOGI", "CRSR"]},
        "STACK": {"sector": "big tech and software", "tickers": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "PLTR", "NOW", "CRM",
            "ORCL", "ADBE", "CSCO", "PANW", "CRWD", "SNOW", "NET", "DDOG",
            "IBM", "AKAM", "DIS", "NFLX", "T", "VZ", "TMUS", "CMCSA"]},
        "SATOSHI": {"sector": "crypto and fintech", "tickers": [
            "COIN", "MSTR", "RIOT", "HOOD", "SOFI", "MARA", "CLSK",
            "PYPL", "AFRM"]},
        "REACTOR": {"sector": "nuclear and energy", "tickers": [
            "OKLO", "SMR", "NNE", "CCJ", "UUUU", "DNN", "CEG", "VST",
            "BWXT", "XOM", "CVX", "LNG", "COP", "OXY", "SLB", "EOG",
            "WMB", "KMI", "FCX", "NEM", "AA", "STLD", "NUE"]},
        "PULSE": {"sector": "biotech and healthcare", "tickers": [
            "REGN", "LLY", "UNH", "MRNA", "ABBV", "AMGN", "GILD", "VRTX",
            "BIIB", "MRK", "PFE", "ISRG"]},
        "AEGIS": {"sector": "defense and industrials", "tickers": [
            "KTOS", "LMT", "RTX", "NOC", "GD", "BA", "AVAV", "HII",
            "CAT", "DE", "GE", "HON", "UPS", "FDX", "EMR", "ETN"]},
        "CART": {"sector": "consumer, retail and travel", "tickers": [
            "WMT", "COST", "CPRI", "CVNA", "HD", "LOW", "TGT", "NKE",
            "SBUX", "MCD", "CMG", "LULU", "KO", "PEP", "MNST", "DAL",
            "UAL", "AAL", "LUV", "MAR", "BKNG", "ABNB", "CCL", "RCL",
            "EXPE"]},
        "VAULT": {"sector": "banks and payments", "tickers": [
            "JPM", "BAC", "GPN", "WFC", "C", "GS", "MS", "SCHW", "USB",
            "V", "MA", "AXP", "FIS", "COF"]},
        "ROCKET": {"sector": "high beta momentum bench", "tickers": [
            "TSLA", "RKLB", "IONQ", "RDDT", "SNDK", "RBLX"]},
    }

# zone id -> (primary label = the real sector, subtitle, neon color)
ZONES = [
    ("circuit", "Semiconductors & Hardware", "CAPTAIN CIRCUIT · ZONE CIRCUIT", "#22d3ee"),
    ("stack", "Big Tech & Software", "CAPTAIN STACK · ZONE STACK", "#818cf8"),
    ("satoshi", "Crypto & Fintech", "CAPTAIN SATOSHI · ZONE SATOSHI", "#fbbf24"),
    ("reactor", "Energy & Nuclear", "CAPTAIN REACTOR · ZONE REACTOR", "#4ade80"),
    ("pulse", "Healthcare & Biotech", "CAPTAIN PULSE · ZONE PULSE", "#f472b6"),
    ("aegis", "Defense & Industrials", "CAPTAIN AEGIS · ZONE AEGIS", "#94a3b8"),
    ("cart", "Consumer, Retail & Travel", "CAPTAIN CART · ZONE CART", "#fb923c"),
    ("vault", "Banks & Payments", "CAPTAIN VAULT · ZONE VAULT", "#2dd4bf"),
    ("rocket", "High-Beta Growth", "CAPTAIN ROCKET · ZONE ROCKET", "#e879f9"),
    ("pairs", "Stat-Arb Pairs", "CAPTAIN PAIRS · THE PAIRS DISTRICT", "#a3e635"),
    ("civic", "City Operations", "CIVIC CENTER · THE STAFF", "#38bdf8"),
    ("thermo", "Market Thermometers", "THERMOMETER ROW · REGIME ONLY, NEVER TRADES", "#facc15"),
    ("artisan", "Handcrafted Artisans", "ARTISAN QUARTER · 100 HANDCRAFTED BOTS", "#c084fc"),
]
ZONE_IDS = [z[0] for z in ZONES]

# ticker -> zone id, first patch in specialists.py order wins
TICKER_ZONE = {}
for patch, cfg in SPECIALISTS.items():
    for t in cfg["tickers"]:
        TICKER_ZONE.setdefault(t, patch.lower())

PATCH_ZONE = {p.lower(): p.lower() for p in SPECIALISTS}


def judge_status():
    """Read JUDGE's scorecard if possible; static fallback otherwise."""
    try:
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "judge_scorecard.py")],
            capture_output=True, text=True, timeout=60, cwd=ROOT)
        m = re.search(r"(\d+)\s+scored,\s+(\d+)\s+needed", out.stdout or "")
        if m:
            return f"{m.group(1)} scored · {m.group(2)} needed"
    except Exception:
        pass
    return "0 scored · 20 needed"


CALLS_LOG = os.path.join(ROOT, "output", "calls.jsonl")


def load_performance(bots):
    """THE BOARD standings from the real performance stores.

    Returns (live_standings, arena_standings, min_proven_calls,
    min_proven_sessions). Standings come from leaderboard.py over the
    --log-calls log (output/calls.jsonl), split by source: live calls
    are the official record, backtest calls are arena only. Open marks
    are excluded (price_fn returns None): THE BOARD ranks completed
    round trips only, so the build never fetches prices. Registry
    fitness fields are a fallback for bots with no standings entry.
    Any failure or missing store yields empty standings.
    """
    live_st, arena_st = {}, {}
    min_calls, min_sessions = 20, 5
    try:
        import leaderboard
        min_calls = getattr(leaderboard, "MIN_PROVEN_CALLS", min_calls)
        min_sessions = getattr(leaderboard, "MIN_PROVEN_SESSIONS",
                               min_sessions)
        if os.path.exists(CALLS_LOG):
            all_calls = leaderboard.load_calls(path=CALLS_LOG,
                                               source=None)
            live, arena = leaderboard.split_sources(all_calls)
            no_marks = lambda ticker: None  # noqa: E731
            if live:
                live_st = leaderboard.compute_standings(
                    live, price_fn=no_marks)
            if arena:
                arena_st = leaderboard.compute_standings(
                    arena, price_fn=no_marks)
    except Exception:
        live_st, arena_st = {}, {}
    for b in bots:
        fit = b.get("fitness")
        if isinstance(fit, dict) and b["name"] not in live_st:
            c = fit.get("calls") or fit.get("ranked_calls") or 0
            if c:
                live_st[b["name"]] = {
                    "calls": int(c), "alerts": int(c),
                    "pnl": float(fit.get("pnl") or fit.get("net_pnl")
                                 or 0.0),
                    "sessions": int(fit.get("sessions") or 0)}
    return live_st, arena_st, min_calls, min_sessions


def live_record(live_st, name):
    """(completed_live_calls, net_pnl) for a bot from THE BOARD live
    standings, or None when it has no completed live trades."""
    s = live_st.get(name)
    if s and s.get("calls", 0) > 0:
        return int(s["calls"]), float(s["pnl"])
    return None


def perf_html(bot, live_st, arena_st, min_calls, min_sessions,
              judge_stat):
    """One bot's performance lines, from the stores only. A bot with
    no ranked (completed) live calls reads 'no calls yet'; P&L figures
    are THE BOARD's paper P&L on the $10k reference size."""
    name = bot["name"]
    if name == "JUDGE":
        return ('<div class="perf judge">RECORD · JUDGE SCORECARD '
                f'{esc(judge_stat)} · no verdict until the evidence '
                "exists</div>")
    out = []
    s = live_st.get(name)
    if s and s.get("calls", 0) > 0:
        calls = int(s["calls"])
        pnl = float(s["pnl"])
        per = pnl / calls
        proven = (calls >= min_calls
                  and s.get("sessions", 0) >= min_sessions)
        status = "PROVEN" if proven else "UNPROVEN"
        cls = "proven" if proven else "unproven"
        sgn = "pos" if pnl >= 0 else "neg"
        out.append(
            f'<div class="perf {cls} haspl">PERF · {calls} live calls · '
            f'net <span class="pnl {sgn}">${pnl:+,.0f}</span> · '
            f'<span class="pnl {sgn}">${per:+,.0f}/call</span> · '
            f"{status}</div>")
    else:
        extra = ""
        if s and s.get("alerts", 0) > 0:
            extra = f' · {int(s["alerts"])} logged, none completed'
        out.append('<div class="perf unproven">PERF · no calls yet'
                   f"{extra} · UNPROVEN</div>")
    a = arena_st.get(name)
    if a and (a.get("alerts", 0) > 0 or a.get("calls", 0) > 0):
        if a.get("calls", 0) > 0:
            out.append(
                '<div class="perf arena">ARENA · backtest only, not '
                f'official · {int(a["calls"])} trades · '
                f'net ${float(a["pnl"]):+,.0f}</div>')
        else:
            out.append(
                '<div class="perf arena">ARENA · backtest only, not '
                f'official · {int(a.get("alerts", 0))} logged, '
                "0 completed</div>")
    return "".join(out)


def assign(bot):
    """Return (zone_id, artisan_subgroup_or_None). Every bot exactly once."""
    kind = bot["kind"]
    name = bot["name"]
    if kind == "staff":
        return "civic", None
    if kind == "thermometer":
        return "thermo", None
    if kind == "pair":
        return "pairs", None
    if kind == "captain":
        tail = name.replace("CAPTAIN ", "").strip().lower()
        return ("pairs" if tail == "pairs" else PATCH_ZONE.get(tail, "civic")), None
    if kind == "specialist":
        return PATCH_ZONE.get(name.lower(), "civic"), None
    if kind == "handcrafted":
        wl = bot.get("watchlist") or []
        first = wl[0] if wl else None
        sub = TICKER_ZONE.get(first) if first else None
        return "artisan", sub  # sub None -> Citywide Crew
    # watcher / shadow / rival / sniper / strategist: first ticker's zone
    wl = bot.get("watchlist") or []
    for t in wl:
        if t in TICKER_ZONE:
            return TICKER_ZONE[t], None
    return "civic", None


def esc(s):
    return html.escape(str(s), quote=True)


def bot_card(bot, idx, zone_id, perf=""):
    name = esc(bot["name"])
    kind = esc(bot["kind"])
    hold = esc(bot.get("hold_style") or "none")
    book = {"intraday": "DAY BOOK", "swing": "LONG BOOK"}.get(
        bot.get("hold_style") or "", "CITY STAFF" if hold == "none" else hold.upper())
    strat = esc(bot.get("strategy") or "")
    wl = bot.get("watchlist") or []
    if wl:
        shown = ", ".join(wl[:8])
        if len(wl) > 8:
            shown += f" +{len(wl) - 8} more"
        watch = f'<div class="watch">{esc(shown)}</div>'
    else:
        watch = ""
    return (
        f'<article class="bot" id="bot-{idx}" data-bot-name="{name}" '
        f'data-zone="{zone_id}">'
        f'<div class="bot-name">{name}</div>'
        f'<div class="badges"><span class="badge kind">{kind}</span>'
        f'<span class="badge hold-{esc(bot.get("hold_style") or "none")}">{book}</span></div>'
        f'<p class="strat">{strat}</p>{watch}{perf}</article>')



# ---------------------------------------------------------------------------
# 3D city layout (deterministic; recomputed from the registry every build)
# ---------------------------------------------------------------------------
import hashlib
import math

KIND_HEIGHT = {
    "staff": 30.0, "captain": 34.0, "specialist": 24.0,
    "thermometer": 20.0, "pair": 16.0, "strategist": 19.0,
    "sniper": 15.0, "watcher": 11.0, "shadow": 11.0, "rival": 12.0,
    "handcrafted": 20.0,
}
CITY_COLS, CITY_PITCH, CITY_PLOT = 4, 78.0, 64.0


def _hash01(name, salt=""):
    digest = hashlib.md5((salt + name).encode()).hexdigest()
    return (int(digest[:8], 16) % 1000) / 1000.0


def book_label(bot):
    hold = bot.get("hold_style") or ""
    return {"intraday": "DAY BOOK", "swing": "LONG BOOK"}.get(
        hold, "CITY STAFF" if hold in ("", "none") else hold.upper())


def watch_str(bot):
    wl = bot.get("watchlist") or []
    if not wl:
        return ""
    shown = ", ".join(wl[:8])
    if len(wl) > 8:
        shown += f" +{len(wl) - 8} more"
    return shown


def city_layout(zones):
    """Place the 13 districts on a 4x4 block grid and give every bot a
    building: position inside its district plot, footprint, height by
    kind with a per name hash variation, and a color shade factor.
    Returns (districts, placements) with placements keyed by bot idx."""
    districts, placements = [], {}
    for k, (zid, _label, _sub, _color) in enumerate(ZONES):
        cx = (k % CITY_COLS - (CITY_COLS - 1) / 2) * CITY_PITCH
        cz = (k // CITY_COLS - (CITY_COLS - 1) / 2) * CITY_PITCH
        members = sorted(zones[zid], key=lambda x: x[1]["name"])
        n = len(members)
        grid = max(1, math.ceil(math.sqrt(n)))
        cell = (CITY_PLOT - 8) / grid
        footprint = round(cell * 0.66, 2)
        for j, (idx, bot) in enumerate(members):
            gx, gz = j % grid, j // grid
            x = (cx - (CITY_PLOT - 8) / 2 + cell * (gx + 0.5)
                 + (_hash01(bot["name"], "x") - 0.5) * cell * 0.16)
            z = (cz - (CITY_PLOT - 8) / 2 + cell * (gz + 0.5)
                 + (_hash01(bot["name"], "z") - 0.5) * cell * 0.16)
            base = KIND_HEIGHT.get(bot["kind"], 12.0)
            placements[idx] = {
                "x": round(x, 2), "z": round(z, 2), "w": footprint,
                "h": round(base * (0.72 + 0.75 * _hash01(bot["name"], "h")), 1),
                "s": round(0.72 + 0.5 * _hash01(bot["name"], "s"), 3),
            }
        districts.append({"id": zid, "cx": cx, "cz": cz,
                          "pw": CITY_PLOT, "count": n})
    return districts, placements


CSS = """
:root{
  --bg:#05070f; --bg2:#0a0e1f; --panel:#0b1122; --line:#1c2a4a;
  --txt:#dbe7ff; --dim:#8494b8; --cyan:#22d3ee; --pink:#f472b6;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;overflow-x:hidden}
body{background:radial-gradient(1200px 600px at 50% -10%,#12204a 0%,var(--bg) 55%) fixed,var(--bg);
  color:var(--txt);font-family:"Avenir Next","Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
  line-height:1.45;padding:0 16px 64px}
.wrap{max-width:1180px;margin:0 auto}
header{padding:38px 0 8px;text-align:center}
h1{font-size:clamp(34px,6vw,58px);letter-spacing:.14em;font-weight:800;
  background:linear-gradient(90deg,#22d3ee,#818cf8,#e879f9,#22d3ee);
  -webkit-background-clip:text;background-clip:text;color:transparent;
  filter:drop-shadow(0 0 14px rgba(34,211,238,.35))}
.tagline{color:var(--dim);letter-spacing:.32em;font-size:12px;text-transform:uppercase;margin-top:6px}
.stats{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin:22px 0 6px}
.chip{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:8px 16px;
  font-size:13px;letter-spacing:.06em}
.chip b{color:var(--cyan);font-size:15px}
.chip.live b{color:#4ade80}
.law{margin:16px auto 4px;max-width:900px;border:1px solid #3b2f63;border-radius:12px;
  background:linear-gradient(90deg,rgba(129,140,248,.13),rgba(232,121,249,.10));padding:13px 18px;
  text-align:center;font-size:14px;letter-spacing:.03em}
.law b{color:#e879f9}.law .day{color:#22d3ee}.law .long{color:#4ade80}
.searchbar{max-width:640px;margin:22px auto 6px;position:relative;z-index:20}
.searchbar input{width:100%;padding:13px 18px;border-radius:12px;border:1px solid var(--line);
  background:#0a1122;color:var(--txt);font-size:16px;outline:none}
.searchbar input:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(34,211,238,.18)}
#results{display:none;margin-top:8px;background:var(--panel);border:1px solid var(--line);
  border-radius:12px;overflow:hidden;max-height:330px;overflow-y:auto;text-align:left}
#results.open{display:block}
#results button{display:flex;justify-content:space-between;gap:10px;width:100%;text-align:left;
  background:none;border:none;border-bottom:1px solid #131e38;color:var(--txt);
  padding:10px 16px;font-size:14px;cursor:pointer}
#results button:hover{background:#101a33}
#results .z{color:var(--dim);font-size:12px;letter-spacing:.05em}
#results .none{padding:12px 16px;color:var(--dim);font-size:14px}
/* --- 3D city stage: fullscreen hero, header overlaid on the canvas --- */
#stage{position:relative;height:100vh;height:100dvh;min-height:440px;
  width:100vw;margin-left:calc(50% - 50vw);
  border-top:1px solid var(--line);border-bottom:1px solid var(--line);
  overflow:hidden;background:#04060d;
  box-shadow:0 18px 50px rgba(0,0,0,.55),0 0 42px -12px rgba(34,211,238,.25)}
#stage:fullscreen{width:100%;height:100%;margin:0;border:none}
#stagehead{position:absolute;top:0;left:0;right:0;z-index:5;pointer-events:none;
  text-align:center;padding:16px 14px 12px;
  background:linear-gradient(180deg,rgba(3,5,12,.88) 55%,rgba(3,5,12,0))}
#stagehead h1{font-size:clamp(28px,4.6vw,44px)}
#stagehead .tagline{margin-top:2px}
#stagehead .stats{margin:12px 0 4px}
#stagehead .chip{background:rgba(11,17,34,.88)}
#stagehead .perf-note{margin-top:8px;text-shadow:0 1px 4px #000}
#stagehead .law{margin:10px auto 2px;padding:9px 14px;font-size:12.5px;
  background:rgba(10,13,30,.75)}
#stagehead .searchbar{pointer-events:auto;margin:12px auto 4px}
.plstrip{display:inline-block;margin-top:10px;background:rgba(7,12,26,.9);
  border:1px solid var(--line);border-radius:999px;padding:8px 18px;
  font-size:13px;letter-spacing:.08em}
.plstrip .pnl{font-size:14px}
.pnl{font-weight:800;color:var(--txt)}
.pnl.pos{color:#4ade80}
.pnl.neg{color:#f87171}
.perf.haspl{border-color:#2b4470;color:#c6d6f5}
#fsbtn{position:absolute;top:14px;right:14px;z-index:7;
  background:rgba(7,12,26,.92);color:var(--cyan);border:1px solid var(--cyan);
  border-radius:10px;padding:10px 16px;font-size:12.5px;font-weight:700;
  letter-spacing:.16em;cursor:pointer;box-shadow:0 0 16px -4px var(--cyan)}
#fsbtn:hover{background:rgba(34,211,238,.16);color:#eaf2ff}
#legend{position:absolute;right:14px;bottom:12px;z-index:4;pointer-events:none;
  background:rgba(6,10,24,.88);border:1px solid var(--line);border-radius:10px;
  padding:8px 12px;font-size:11.5px;letter-spacing:.05em;color:var(--dim);
  text-shadow:0 1px 4px #000}
#legend .sw{display:inline-block;width:10px;height:10px;border-radius:3px;
  margin:0 5px 0 10px;vertical-align:-1px}
#legend .sw:first-child{margin-left:0}
.sw-district{background:#3d5a80}.sw-pos{background:#2bff6a}.sw-neg{background:#ff3b30}
#stage canvas{display:block}
#cityhint{position:absolute;left:14px;bottom:12px;z-index:4;color:#a9bcdf;font-size:12px;
  letter-spacing:.1em;text-transform:uppercase;text-shadow:0 1px 6px #000;pointer-events:none}
#tooltip{position:absolute;display:none;z-index:8;pointer-events:none;background:rgba(6,10,24,.94);
  border:1px solid var(--cyan);border-radius:8px;padding:5px 10px;font-size:12.5px;
  letter-spacing:.04em;color:var(--txt);white-space:nowrap;box-shadow:0 4px 18px rgba(0,0,0,.6)}
#tooltip .tz{color:var(--dim);font-size:11px;margin-left:6px}
#cityfallback{position:absolute;inset:0;display:none;align-items:center;justify-content:center;
  text-align:center;padding:24px;color:var(--dim);font-size:14px;letter-spacing:.06em;
  background:rgba(4,6,13,.6);z-index:3}
#sidepanel{position:absolute;top:0;right:0;z-index:6;width:min(372px,94%);height:100%;
  background:rgba(7,11,24,.94);backdrop-filter:blur(8px);border-left:1px solid var(--line);
  transform:translateX(106%);transition:transform .32s ease;display:flex;flex-direction:column}
#sidepanel.open{transform:none}
.sp-head{padding:16px 18px 10px;border-bottom:1px solid var(--line)}
.sp-head h2{font-size:21px;line-height:1.25}
.sp-head .sub{font-size:11px;letter-spacing:.18em;text-transform:uppercase;margin-top:4px}
.sp-head .meta{color:var(--dim);font-size:12.5px;margin-top:6px}
#spclose{position:absolute;top:10px;right:12px;background:none;border:1px solid var(--line);
  color:var(--txt);border-radius:8px;width:32px;height:32px;font-size:16px;cursor:pointer;line-height:1}
#spclose:hover{border-color:var(--cyan)}
#botdetail{padding:12px 18px 0}
#botlist{overflow-y:auto;padding:12px 14px 18px;display:flex;flex-direction:column;gap:8px}
.prow{background:#0a1226;border:1px solid #16233f;border-radius:10px;padding:10px 12px;cursor:pointer}
.prow:hover{border-color:#2b4470}
.prow.flash{border-color:#facc15;box-shadow:0 0 0 2px #facc15,0 0 22px -2px #facc15}
.prow .bot-name{font-size:14px}
.prow .strat{font-size:12.5px}
.prow .perf{font-size:11px}
/* --- plain HTML directory (fallback + full listing) --- */
.dirhead{margin:38px 0 4px;font-size:15px;letter-spacing:.26em;color:var(--dim);
  text-transform:uppercase;text-align:center}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(248px,1fr));gap:14px;margin-top:18px}
.tile{--zc:#22d3ee;background:linear-gradient(160deg,#0c1428,#080d1c);border:1px solid var(--line);
  border-top:3px solid var(--zc);border-radius:14px;padding:18px;cursor:pointer;text-align:left;
  color:var(--txt);font:inherit;transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease;width:100%}
.tile:hover{transform:translateY(-3px);border-color:var(--zc);
  box-shadow:0 8px 28px rgba(0,0,0,.5),0 0 18px -4px var(--zc)}
.tile.active{border-color:var(--zc);box-shadow:0 0 0 2px var(--zc),0 10px 30px rgba(0,0,0,.5)}
.tile h2{font-size:19px;line-height:1.25;letter-spacing:.02em}
.tile .sub{color:var(--zc);font-size:11px;letter-spacing:.18em;margin-top:5px;text-transform:uppercase}
.tile .count{margin-top:14px;font-size:13px;color:var(--dim)}
.tile .count b{color:var(--txt);font-size:22px;margin-right:4px}
.tile .bars{display:flex;align-items:flex-end;gap:2px;height:26px;margin-top:12px}
.tile .bars i{flex:1;background:var(--zc);opacity:.35;border-radius:1px 1px 0 0}
.panel{display:none;margin-top:18px;background:var(--panel);border:1px solid var(--line);
  border-radius:16px;padding:22px;animation:open .25s ease}
.panel.open{display:block}
@keyframes open{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.panel-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 16px;margin-bottom:6px}
.panel-head h2{font-size:26px}
.panel-head .sub{color:var(--zc,#22d3ee);font-size:12px;letter-spacing:.18em;text-transform:uppercase}
.panel .meta{color:var(--dim);font-size:13px;margin-bottom:16px}
.subgroup{margin:20px 0 10px;font-size:13px;letter-spacing:.22em;color:#c084fc;text-transform:uppercase}
.bots{display:grid;grid-template-columns:repeat(auto-fill,minmax(258px,1fr));gap:10px}
.bot{background:#0a1226;border:1px solid #16233f;border-radius:12px;padding:13px 14px;transition:border-color .2s,box-shadow .2s}
.bot:hover{border-color:#2b4470}
.bot.flash{border-color:#facc15;box-shadow:0 0 0 2px #facc15,0 0 22px -2px #facc15}
.bot-name{font-weight:700;letter-spacing:.04em;font-size:15px;word-break:break-word}
.badges{display:flex;gap:6px;margin:7px 0 8px;flex-wrap:wrap}
.badge{font-size:10px;letter-spacing:.12em;padding:3px 8px;border-radius:999px;border:1px solid #2b3d63;color:#a9bcdf;text-transform:uppercase}
.badge.hold-intraday{border-color:#155e75;color:#67e8f9}
.badge.hold-swing{border-color:#166534;color:#86efac}
.badge.hold-none{border-color:#3f3f46;color:#a1a1aa}
.strat{font-size:13px;color:#b9c8e8}
.watch{margin-top:8px;font-size:11px;color:var(--dim);letter-spacing:.05em;word-break:break-word}
.perf{margin-top:9px;font-size:11.5px;letter-spacing:.04em;padding:6px 8px;border-radius:8px;
  background:#0d1730;border:1px solid #1a2a4d;color:#9fb4da;word-break:break-word}
.perf.proven{border-color:#166534;color:#86efac}
.perf.unproven{color:#8494b8}
.perf.arena{border-color:#92600a;color:#fcd34d;background:#171106}
.perf.judge{border-color:#3b2f63;color:#c4b5fd}
.perf-note{margin:10px auto 0;max-width:900px;color:var(--dim);font-size:12.5px;
  letter-spacing:.05em;text-align:center}
.perf-note b{color:#facc15}
footer{margin-top:44px;text-align:center;color:var(--dim);font-size:12px;letter-spacing:.08em}
@media (max-width:640px){
  .grid{grid-template-columns:1fr}
  .bots{grid-template-columns:1fr}
  #stage{min-height:420px}
  #stagehead{padding-top:10px}
  #stagehead .tagline{display:none}
  #fsbtn{top:10px;right:10px;padding:8px 12px;font-size:11.5px}
  #legend{font-size:10.5px;right:10px;bottom:10px}
  #sidepanel{width:100%;height:58%;top:auto;bottom:0;transform:translateY(106%);
    border-left:none;border-top:1px solid var(--line)}
  #sidepanel.open{transform:none}
}
"""


JS = """
const panels={};document.querySelectorAll('.panel').forEach(p=>panels[p.id]=p);
let current=null;
function openZone(id,scroll){
  if(current===id){panels[id].classList.remove('open');
    document.querySelectorAll('.tile').forEach(t=>t.classList.remove('active'));
    current=null;return;}
  Object.values(panels).forEach(p=>p.classList.remove('open'));
  document.querySelectorAll('.tile').forEach(t=>t.classList.toggle('active',t.dataset.zone===id));
  panels[id].classList.add('open');current=id;
  if(scroll!==false)panels[id].scrollIntoView({behavior:'smooth',block:'start'});
}
document.querySelectorAll('.tile').forEach(t=>t.addEventListener('click',()=>{
  openZone(t.dataset.zone);
  if(window.__selectDistrict)window.__selectDistrict(t.dataset.zone);
}));
const idx=JSON.parse(document.getElementById('bot-index').textContent);
const input=document.getElementById('q'),box=document.getElementById('results');
input.addEventListener('input',()=>{
  const q=input.value.trim().toLowerCase();
  if(q.length<2){box.classList.remove('open');box.innerHTML='';return;}
  const hits=idx.filter(b=>b.name.toLowerCase().includes(q)).slice(0,60);
  box.innerHTML=hits.length?hits.map(h=>
    `<button data-bot="${h.i}"><span>${h.name}</span><span class="z">${h.zoneLabel}</span></button>`).join('')
    :'<div class="none">No bot in the city matches that name.</div>';
  box.classList.add('open');
  box.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>{
    const b=idx.find(x=>x.i===+btn.dataset.bot);if(!b)return;
    box.classList.remove('open');input.value='';
    openZone(b.zone,false);
    const el=document.getElementById('bot-'+b.i);
    setTimeout(()=>{el.scrollIntoView({behavior:'smooth',block:'center'});
      el.classList.add('flash');setTimeout(()=>el.classList.remove('flash'),2600);},80);
    if(window.__flyToBot)window.__flyToBot(b.i);
  }));
});
document.addEventListener('click',e=>{if(!e.target.closest('.searchbar'))box.classList.remove('open');});
openZone('civic',false);
/* Fullscreen: the button toggles the Fullscreen API on the stage
   container, so the side panel, search and tooltip (all positioned
   inside the stage) keep working while fullscreen. Esc exits via the
   browser default. */
const fsBtn=document.getElementById('fsbtn'),stageEl=document.getElementById('stage');
if(fsBtn&&stageEl){
  fsBtn.addEventListener('click',()=>{
    if(document.fullscreenElement){document.exitFullscreen();}
    else if(stageEl.requestFullscreen){stageEl.requestFullscreen();}
  });
  document.addEventListener('fullscreenchange',()=>{
    fsBtn.textContent=document.fullscreenElement?'EXIT FULLSCREEN':'FULLSCREEN';});
}
"""

# The 3D city. Three.js and OrbitControls load from the jsDelivr CDN;
# those two module URLs are the only external references on the page.
THREE_JS = r'''
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const DATA = JSON.parse(document.getElementById('city-data').textContent);
const stage = document.getElementById('stage');
const tooltip = document.getElementById('tooltip');
const panel = document.getElementById('sidepanel');
const botlist = document.getElementById('botlist');
const botdetail = document.getElementById('botdetail');
const ZONE = {}; DATA.districts.forEach(d => { ZONE[d.id] = d; });
const BOT = {}; DATA.bots.forEach(b => { BOT[b.i] = b; });

function esc(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function cardHTML(b){
  return '<article class="prow" data-i="' + b.i + '">' +
    '<div class="bot-name">' + esc(b.name) + '</div>' +
    '<div class="badges"><span class="badge kind">' + esc(b.kind) + '</span>' +
    '<span class="badge hold-' + esc(b.hold) + '">' + esc(b.book) + '</span></div>' +
    '<p class="strat">' + esc(b.strat) + '</p>' +
    (b.watch ? '<div class="watch">' + esc(b.watch) + '</div>' : '') +
    b.perf + '</article>';
}

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias:true, powerPreference:'high-performance' });
} catch(e) {
  document.getElementById('cityfallback').style.display = 'flex';
  throw e;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(stage.clientWidth, stage.clientHeight);
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x04060d);
scene.fog = new THREE.FogExp2(0x05070f, 0.0013);

const camera = new THREE.PerspectiveCamera(46, stage.clientWidth / stage.clientHeight, 0.5, 3000);
camera.position.set(172, 150, 214);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 2, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.maxPolarAngle = 1.45;
controls.minDistance = 14;
controls.maxDistance = 640;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.55;

/* --- textures --- */
function makeWindowTexture(){
  const c = document.createElement('canvas'); c.width = 96; c.height = 192;
  const g = c.getContext('2d');
  g.fillStyle = '#070b1a'; g.fillRect(0, 0, 96, 192);
  let seed = 987654321;
  const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  for (let y = 0; y < 16; y++) for (let x = 0; x < 6; x++) {
    const r = rnd();
    if (r < 0.52) g.fillStyle = rnd() < 0.6 ? 'rgba(255,214,140,0.95)' : 'rgba(170,225,255,0.95)';
    else g.fillStyle = 'rgba(15,23,46,1)';
    g.fillRect(6 + x * 15, 8 + y * 11.5, 9, 6.5);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
function makeGlowTexture(){
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  const gr = g.createRadialGradient(64, 64, 2, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,0.85)');
  gr.addColorStop(0.4, 'rgba(255,255,255,0.26)');
  gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}
function makeLabelSprite(d){
  const c = document.createElement('canvas'); c.width = 640; c.height = 160;
  const g = c.getContext('2d');
  g.beginPath();
  if (g.roundRect) g.roundRect(12, 28, 616, 104, 26); else g.rect(12, 28, 616, 104);
  g.fillStyle = 'rgba(4,8,20,0.78)'; g.fill();
  g.lineWidth = 3; g.strokeStyle = d.color; g.stroke();
  g.textAlign = 'center';
  let fs = 46;
  g.font = '700 ' + fs + 'px "Avenir Next","Segoe UI",sans-serif';
  while (g.measureText(d.label).width > 580 && fs > 22) { fs -= 2; g.font = '700 ' + fs + 'px "Avenir Next","Segoe UI",sans-serif'; }
  g.fillStyle = '#eaf2ff';
  g.fillText(d.label, 320, 84);
  g.font = '600 29px "Avenir Next","Segoe UI",sans-serif';
  g.fillStyle = d.color;
  g.fillText(d.count + ' BOTS', 320, 121);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map:t, transparent:true, depthWrite:false }));
  sp.scale.set(42, 10.5, 1);
  sp.position.set(d.cx, 58, d.cz);
  sp.userData.zone = d.id;
  return sp;
}

const winTex = makeWindowTexture();
const glowTex = makeGlowTexture();

/* --- ground, streets grid, stars --- */
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(760, 760),
  new THREE.MeshBasicMaterial({ color: 0x04060d }));
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.05;
scene.add(ground);
const grid = new THREE.GridHelper(624, 78, 0x1e3a5f, 0x0c1730);
grid.position.y = 0.02;
grid.material.transparent = true;
grid.material.opacity = 0.5;
scene.add(grid);
(function addStars(){
  const pts = [];
  for (let i = 0; i < 700; i++) {
    const a = Math.random() * Math.PI * 2, e = Math.random() * Math.PI * 0.48 + 0.05, r = 640;
    pts.push(Math.cos(a) * Math.cos(e) * r, Math.sin(e) * r, Math.sin(a) * Math.cos(e) * r);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  const stars = new THREE.Points(geo, new THREE.PointsMaterial({
    color: 0x8fb8ff, size: 1.7, sizeAttenuation: false,
    transparent: true, opacity: 0.75, fog: false }));
  scene.add(stars);
})();

/* --- districts: plots, borders, glow, labels, buildings --- */
const pickMeshes = [];    // InstancedMesh per district (raycast: buildings)
const pickTargets = [];   // buildings + plots + labels (raycast: clicks)
DATA.districts.forEach(d => {
  const plot = new THREE.Mesh(
    new THREE.PlaneGeometry(d.pw + 6, d.pw + 6),
    new THREE.MeshBasicMaterial({ color: d.color, transparent: true, opacity: 0.09, depthWrite: false }));
  plot.rotation.x = -Math.PI / 2;
  plot.position.set(d.cx, 0.05, d.cz);
  plot.userData.zone = d.id;
  scene.add(plot); pickTargets.push(plot);

  const h = d.pw / 2 + 3;
  const borderPts = [
    new THREE.Vector3(-h, 0, -h), new THREE.Vector3(h, 0, -h),
    new THREE.Vector3(h, 0, h), new THREE.Vector3(-h, 0, h)];
  const border = new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(borderPts),
    new THREE.LineBasicMaterial({ color: d.color, transparent: true, opacity: 0.85 }));
  border.position.set(d.cx, 0.08, d.cz);
  scene.add(border);

  const glow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTex, color: d.color, transparent: true, opacity: 0.15, depthWrite: false }));
  glow.scale.set(d.pw * 1.7, d.pw * 1.7, 1);
  glow.position.set(d.cx, 3, d.cz);
  scene.add(glow);

  const label = makeLabelSprite(d);
  scene.add(label); pickTargets.push(label);

  const bots = DATA.bots.filter(b => b.zone === d.id);
  const geo = new THREE.BoxGeometry(1, 1, 1);
  geo.translate(0, 0.5, 0);
  const im = new THREE.InstancedMesh(geo, new THREE.MeshBasicMaterial({ map: winTex }), bots.length);
  const m4 = new THREE.Matrix4(), pv = new THREE.Vector3(),
        q = new THREE.Quaternion(), sc = new THREE.Vector3();
  const base = new THREE.Color(d.color);
  bots.forEach((b, j) => {
    pv.set(b.x, 0, b.z); sc.set(b.w, b.h, b.w);
    m4.compose(pv, q, sc);
    im.setMatrixAt(j, m4);
    b._base = base.clone().multiplyScalar(b.s);
    /* P/L tint: a bot with completed live trades shifts its building
       toward green (net profit) or red (net loss); no trades yet
       keeps the neutral district color. */
    if (b.pnl != null && b.calls > 0) {
      b._base.lerp(new THREE.Color(b.pnl >= 0 ? 0x2bff6a : 0xff3b30), 0.62);
    }
    im.setColorAt(j, b._base);
    b._mesh = im; b._inst = j;
  });
  im.instanceMatrix.needsUpdate = true;
  if (im.instanceColor) im.instanceColor.needsUpdate = true;
  im.userData.zone = d.id;
  im.userData.bots = bots;
  scene.add(im); pickMeshes.push(im); pickTargets.push(im);
});

/* --- camera flight + selection --- */
let tween = null;
function flyTo(px, py, pz, tx, ty, tz, dur){
  tween = { p0: camera.position.clone(), p1: new THREE.Vector3(px, py, pz),
            t0: controls.target.clone(), t1: new THREE.Vector3(tx, ty, tz),
            start: performance.now(), dur: dur || 1100 };
}
controls.addEventListener('start', () => { controls.autoRotate = false; tween = null; });

let flash = null;
const tmpC = new THREE.Color(), whiteC = new THREE.Color(0xffffff);
function setInstColor(b, col){
  b._mesh.setColorAt(b._inst, col);
  if (b._mesh.instanceColor) b._mesh.instanceColor.needsUpdate = true;
}
function flashBot(b){
  if (flash) setInstColor(flash.bot, flash.bot._base);
  flash = { bot: b, until: performance.now() + 2600 };
}

let selectedZone = null;
function selectZone(zoneId, focusIdx){
  selectedZone = zoneId;
  const d = ZONE[zoneId];
  document.getElementById('sp-title').textContent = d.label;
  const sub = document.getElementById('sp-sub');
  sub.textContent = d.sub; sub.style.color = d.color;
  document.getElementById('sp-meta').textContent =
    d.count + ' bots in this district · click a building or a row for the bot card';
  const bots = DATA.bots.filter(b => b.zone === zoneId)
    .sort((a, b) => a.name < b.name ? -1 : 1);
  botlist.innerHTML = bots.map(cardHTML).join('');
  botdetail.innerHTML = '';
  panel.classList.add('open');
  const len = Math.hypot(d.cx, d.cz) || 1;
  const ux = d.cx / len, uz = d.cz / len;
  flyTo(d.cx + ux * 92, 72, d.cz + uz * 92, d.cx, 4, d.cz, 1150);
  if (focusIdx != null) showBot(focusIdx, false);
}
function showBot(i, fly){
  const b = BOT[i]; if (!b) return;
  if (b.zone !== selectedZone) { selectZone(b.zone, i); return; }
  botdetail.innerHTML = cardHTML(b);
  botlist.querySelectorAll('.prow').forEach(r => r.classList.remove('flash'));
  const row = botlist.querySelector('[data-i="' + i + '"]');
  if (row) {
    row.classList.add('flash');
    row.scrollIntoView({ block: 'center' });
    setTimeout(() => row.classList.remove('flash'), 2600);
  }
  flashBot(b);
  if (fly !== false) flyTo(b.x + 30, 30, b.z + 30, b.x, b.h * 0.55, b.z, 1000);
}
botlist.addEventListener('click', e => {
  const row = e.target.closest('.prow'); if (!row) return;
  showBot(+row.dataset.i);
});
botdetail.addEventListener('click', e => {
  const row = e.target.closest('.prow'); if (!row) return;
  showBot(+row.dataset.i);
});
document.getElementById('spclose').addEventListener('click', () => panel.classList.remove('open'));

/* --- picking: click a building, a plot, or a label; hover tooltip --- */
const ray = new THREE.Raycaster();
const ndc = new THREE.Vector2();
function setNDC(e){
  const r = renderer.domElement.getBoundingClientRect();
  ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
}
let downX = 0, downY = 0;
renderer.domElement.addEventListener('pointerdown', e => { downX = e.clientX; downY = e.clientY; });
renderer.domElement.addEventListener('pointerup', e => {
  if (Math.hypot(e.clientX - downX, e.clientY - downY) > 6) return;
  setNDC(e);
  ray.setFromCamera(ndc, camera);
  const hits = ray.intersectObjects(pickTargets, false);
  if (!hits.length) return;
  const h = hits[0];
  if (h.object.isInstancedMesh && h.instanceId !== undefined) {
    const b = h.object.userData.bots[h.instanceId];
    selectZone(b.zone);
    showBot(b.i);
  } else if (h.object.userData && h.object.userData.zone) {
    controls.autoRotate = false;
    selectZone(h.object.userData.zone);
  }
});
let hoverEvt = null;
renderer.domElement.addEventListener('pointermove', e => {
  hoverEvt = e;
  const r = stage.getBoundingClientRect();
  tooltip.style.left = (e.clientX - r.left + 14) + 'px';
  tooltip.style.top = (e.clientY - r.top + 12) + 'px';
});
renderer.domElement.addEventListener('pointerleave', () => { hoverEvt = null; tooltip.style.display = 'none'; });

function fitRenderer(){
  const w = stage.clientWidth, hgt = stage.clientHeight;
  if (!w || !hgt) return;
  camera.aspect = w / hgt;
  camera.updateProjectionMatrix();
  renderer.setSize(w, hgt);
}
window.addEventListener('resize', fitRenderer);
document.addEventListener('fullscreenchange', () => setTimeout(fitRenderer, 60));

/* --- main loop --- */
function animate(){
  requestAnimationFrame(animate);
  const now = performance.now();
  if (tween) {
    let k = (now - tween.start) / tween.dur; if (k > 1) k = 1;
    const e = 1 - Math.pow(1 - k, 3);
    camera.position.lerpVectors(tween.p0, tween.p1, e);
    controls.target.lerpVectors(tween.t0, tween.t1, e);
    if (k === 1) tween = null;
  }
  if (flash) {
    if (now > flash.until) { setInstColor(flash.bot, flash.bot._base); flash = null; }
    else {
      const p = 0.5 + 0.5 * Math.sin(now / 160);
      tmpC.setHex(0xfacc15).lerp(whiteC, p * 0.45);
      setInstColor(flash.bot, tmpC);
    }
  }
  if (hoverEvt) {
    setNDC(hoverEvt);
    ray.setFromCamera(ndc, camera);
    const hits = ray.intersectObjects(pickMeshes, false);
    if (hits.length && hits[0].instanceId !== undefined) {
      const b = hits[0].object.userData.bots[hits[0].instanceId];
      tooltip.innerHTML = esc(b.name) + '<span class="tz">' + esc(ZONE[b.zone].label) + '</span>';
      tooltip.style.display = 'block';
      renderer.domElement.style.cursor = 'pointer';
    } else {
      tooltip.style.display = 'none';
      renderer.domElement.style.cursor = '';
    }
    hoverEvt = null;
  }
  controls.update();
  renderer.render(scene, camera);
}
animate();
window.__cityReady = true;
window.__flyToBot = function(i){
  const b = BOT[i]; if (!b) return;
  controls.autoRotate = false;
  selectZone(b.zone);
  showBot(i);
};
window.__selectDistrict = function(z){
  if (!ZONE[z]) return;
  controls.autoRotate = false;
  selectZone(z);
};
'''

IMPORTMAP = """
<script type="importmap">
{"imports":{
  "three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
}}
</script>
"""


def main():
    with open(REGISTRY) as f:
        reg = json.load(f)
    bots = reg["bots"]
    total = len(bots)
    names_under_watch = len(TICKER_ZONE)

    judge_stat = judge_status()
    live_st, arena_st, min_calls, min_sessions = load_performance(bots)
    perf_by_idx = {
        idx: perf_html(b, live_st, arena_st, min_calls, min_sessions,
                       judge_stat)
        for idx, b in enumerate(bots)}
    live_completed = sum(int(s.get("calls", 0)) for s in live_st.values())
    bots_with_calls = sum(1 for s in live_st.values()
                          if s.get("calls", 0) > 0)

    # --- CITY P/L strip: live standings only, ARENA never counted ---
    traded = []
    for b in bots:
        rec = live_record(live_st, b["name"])
        if rec is not None:
            traded.append((b["name"], rec[0], rec[1]))
    city_pnl = sum(t[2] for t in traded)
    if traded:
        best = max(traded, key=lambda t: t[2])
        worst = min(traded, key=lambda t: t[2])
        tot_cls = "pos" if city_pnl >= 0 else "neg"
        best_cls = "pos" if best[2] >= 0 else "neg"
        worst_cls = "pos" if worst[2] >= 0 else "neg"
        plstrip = (
            f'TOTAL NET <span class="pnl {tot_cls}">'
            f"${city_pnl:+,.0f}</span> · {live_completed} COMPLETED "
            f'LIVE TRADES · BEST <span class="pnl {best_cls}">'
            f"{esc(best[0])} ${best[2]:+,.0f}</span> · WORST "
            f'<span class="pnl {worst_cls}">{esc(worst[0])} '
            f"${worst[2]:+,.0f}</span>")
    else:
        plstrip = ('TOTAL NET <span class="pnl">$0</span> · NO COMPLETED '
                   "LIVE TRADES YET · DAY ONE IS MON NOV 2")

    zones = {zid: [] for zid in ZONE_IDS}          # zone -> [(idx, bot)]
    zone_of = {}
    artisan_subs = {}                                # sub zone id or None -> [...]
    for idx, bot in enumerate(bots):
        zid, sub = assign(bot)
        zones[zid].append((idx, bot))
        zone_of[idx] = zid
        if zid == "artisan":
            artisan_subs.setdefault(sub, []).append((idx, bot))

    assert sum(len(v) for v in zones.values()) == total, "assignment leak"

    # --- 3D city data ---
    districts_geo, placements = city_layout(zones)
    zone_meta = {zid: (label, sub, color) for zid, label, sub, color in ZONES}
    city_districts = []
    for d in districts_geo:
        label, sub, color = zone_meta[d["id"]]
        city_districts.append({
            "id": d["id"], "label": label, "sub": sub, "color": color,
            "cx": d["cx"], "cz": d["cz"], "pw": d["pw"],
            "count": d["count"]})
    city_bots = []
    for idx, bot in enumerate(bots):
        rec = live_record(live_st, bot["name"])
        city_bots.append({
            "i": idx, "name": bot["name"], "kind": bot["kind"],
            "hold": bot.get("hold_style") or "none",
            "book": book_label(bot),
            "strat": bot.get("strategy") or "",
            "watch": watch_str(bot),
            "zone": zone_of[idx],
            "perf": perf_by_idx[idx],
            "calls": rec[0] if rec else 0,
            "pnl": rec[1] if rec else None,
            **placements[idx]})
    city_json = json.dumps({"districts": city_districts, "bots": city_bots}
                           ).replace("</", "<\\/")

    # --- plain HTML directory (fallback) ---
    tiles = []
    for zid, label, sub, color in ZONES:
        n = len(zones[zid])
        bars = "".join(
            f'<i style="height:{10 + ((i * 37 + n) % 16)}px"></i>'
            for i in range(14))
        tiles.append(
            f'<button class="tile" data-zone="{zid}" style="--zc:{color}">'
            f"<h2>{esc(label)}</h2><div class=\"sub\">{esc(sub)}</div>"
            f'<div class="count"><b>{n}</b>bots on duty</div>'
            f'<div class="bars">{bars}</div></button>')

    zone_label = {zid: label for zid, label, _, _ in ZONES}
    panels = []
    for zid, label, sub, color in ZONES:
        members = zones[zid]
        head = (
            f'<section class="panel" id="{zid}" style="--zc:{color}">'
            f'<div class="panel-head"><h2>{esc(label)}</h2>'
            f'<span class="sub">{esc(sub)}</span></div>'
            f'<div class="meta">{len(members)} bots in this district · '
            f"click any other district tile to walk the city</div>")
        if zid == "artisan":
            body = []
            order = [z for z in ZONE_IDS if z in artisan_subs] + \
                    ([None] if None in artisan_subs else [])
            for sub_key in order:
                sub_name = (zone_label[sub_key].upper()
                            if sub_key else "CITYWIDE CREW")
                body.append(f'<h3 class="subgroup">{esc(sub_name)}</h3>')
                cards = "".join(
                    bot_card(b, i, zid, perf_by_idx[i])
                    for i, b in sorted(artisan_subs[sub_key],
                                       key=lambda x: x[1]["name"]))
                body.append(f'<div class="bots">{cards}</div>')
            panels.append(head + "".join(body) + "</section>")
        else:
            cards = "".join(
                bot_card(b, i, zid, perf_by_idx[i])
                for i, b in sorted(members, key=lambda x: x[1]["name"]))
            panels.append(head + f'<div class="bots">{cards}</div></section>')

    index = [{"i": idx, "name": b["name"], "zone": zone_of[idx],
              "zoneLabel": zone_label[zone_of[idx]]}
             for idx, b in enumerate(bots)]
    index_json = json.dumps(index).replace("</", "<\\/")

    gen = datetime.now().strftime("%a %b %d, %Y %I:%M %p")
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot City Monitor</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<main>
<section id="stage">
<div id="stagehead">
<h1>BOT CITY</h1>
<div class="tagline">Cyber City Monitor · Every Bot Named · Every District On The Grid</div>
<div class="stats">
<span class="chip"><b>{total}</b> BOTS IN THE CITY</span>
<span class="chip"><b>{names_under_watch}</b> NAMES UNDER WATCH</span>
<span class="chip">JUDGE SCORECARD · <b>{esc(judge_stat)}</b></span>
<span class="chip"><b>{live_completed}</b> LIVE TRADES COMPLETED CITYWIDE</span>
<span class="chip live"><b>MON NOV 2</b> LIVE TEST DAY</span>
</div>
<div><span class="plstrip">CITY P/L · {plstrip}</span></div>
<div class="perf-note">PERFORMANCE · official standings come only from
<b>live calls</b> · Monday Nov 2 is day one, so most rows honestly read
zero today · {bots_with_calls} of {total} bots have a completed live
trade · ARENA marks are backtest, never official</div>
<div class="law">THE TWO BOOK LAW · budget split <b>50 / 50</b> between
<span class="long"><b>LONG HOLD</b></span> and <span class="day"><b>DAY TRADING</b></span> ·
the <span class="day"><b>DAY</b></span> book is fully liquid by the close, every day ·
<span class="long"><b>LONG</b></span> decisions are Muse's calls</div>
<div class="searchbar">
<input id="q" type="search" placeholder="Search any bot by name across the whole city..." autocomplete="off">
<div id="results"></div>
</div>
</div>
<button id="fsbtn" type="button">FULLSCREEN</button>
<div id="legend"><span class="sw sw-district"></span>district color · no completed trades yet<span class="sw sw-pos"></span>net profit<span class="sw sw-neg"></span>net loss</div>
<div id="cityhint">Drag to orbit · Scroll to zoom · Click a district or a building</div>
<div id="cityfallback">3D CITY UNAVAILABLE · WEBGL OR THE THREE.JS CDN IS
BLOCKED ON THIS DEVICE · THE FULL DIRECTORY BELOW LISTS EVERY ONE OF
THE {total} BOTS BY NAME</div>
<div id="tooltip"></div>
<aside id="sidepanel">
<button id="spclose" aria-label="Close panel">&times;</button>
<div class="sp-head"><h2 id="sp-title">District</h2>
<div class="sub" id="sp-sub"></div>
<div class="meta" id="sp-meta"></div></div>
<div id="botdetail"></div>
<div id="botlist"></div>
</aside>
</section>
<h2 class="dirhead">Full City Directory · Every Bot In Plain HTML</h2>
<div class="grid">{''.join(tiles)}</div>
{''.join(panels)}
</main>
<footer>BOT CITY MONITOR · generated {esc(gen)} from the live registry ·
separate environments: LONG book and DAY book never mix · paper city, ranked by production</footer>
</div>
<script type="application/json" id="bot-index">{index_json}</script>
<script type="application/json" id="city-data">{city_json}</script>
<script>setTimeout(function(){{if(!window.__cityReady){{var f=document.getElementById('cityfallback');if(f)f.style.display='flex';}}}},9000);</script>
<script>{JS}</script>
{IMPORTMAP}
<script type="module">{THREE_JS}</script>
</body>
</html>
"""
    with open(OUT, "w") as f:
        f.write(page)

    print(f"wrote {OUT} ({len(page):,} bytes)")
    print(f"performance: {live_completed} completed live trades across "
          f"{bots_with_calls} bots · arena bots with activity: "
          f"{len(arena_st)} · JUDGE {judge_stat}")
    print(f"city P/L strip: total net ${city_pnl:+,.2f} · "
          f"{len(traded)} bots with completed live trades")
    print(f"total bots: {total} · names under watch: {names_under_watch}")
    for zid, label, _, _ in ZONES:
        print(f"  {label:<28} {len(zones[zid]):>4}")
    print(f"  {'TOTAL':<28} {sum(len(v) for v in zones.values()):>4}")


if __name__ == "__main__":
    main()
