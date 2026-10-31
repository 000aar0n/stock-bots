#!/usr/bin/env python3
"""build_page.py - generate the Bot City Monitor page (docs/index.html).

Reads the live registry (output/bots.json) and the sector patches in
specialists.py, assigns every bot to exactly one city zone, and writes
a single self-contained cyber city HTML page: no external assets, no
account names, no credentials, no portfolio values.

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
        out.append(
            f'<div class="perf {cls}">PERF · {calls} live calls · '
            f"net ${pnl:+,.0f} · ${per:+,.0f}/call · {status}</div>")
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


CSS = """
:root{
  --bg:#05070f; --bg2:#0a0e1f; --panel:#0b1122; --line:#1c2a4a;
  --txt:#dbe7ff; --dim:#8494b8; --cyan:#22d3ee; --pink:#f472b6;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
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
.skyline{display:flex;align-items:flex-end;gap:3px;height:74px;margin:26px auto 0;max-width:900px;
  border-bottom:2px solid #1e3a5f}
.skyline i{flex:1;background:linear-gradient(180deg,#0d1836,#081026);border:1px solid #1c2f57;border-bottom:none;
  position:relative}
.skyline i::after{content:"";position:absolute;inset:4px 3px;
  background-image:radial-gradient(circle 1.6px at 4px 6px,rgba(250,204,21,.85) 98%,transparent),
                   radial-gradient(circle 1.6px at 10px 16px,rgba(34,211,238,.8) 98%,transparent),
                   radial-gradient(circle 1.6px at 6px 28px,rgba(244,114,182,.75) 98%,transparent);
  background-size:14px 22px;opacity:.8}
.stats{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin:22px 0 6px}
.chip{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:8px 16px;
  font-size:13px;letter-spacing:.06em}
.chip b{color:var(--cyan);font-size:15px}
.chip.live b{color:#4ade80}
.law{margin:16px auto 4px;max-width:900px;border:1px solid #3b2f63;border-radius:12px;
  background:linear-gradient(90deg,rgba(129,140,248,.13),rgba(232,121,249,.10));padding:13px 18px;
  text-align:center;font-size:14px;letter-spacing:.03em}
.law b{color:#e879f9}.law .day{color:#22d3ee}.law .long{color:#4ade80}
.searchbar{max-width:640px;margin:22px auto 6px;position:relative}
.searchbar input{width:100%;padding:13px 18px;border-radius:12px;border:1px solid var(--line);
  background:#0a1122;color:var(--txt);font-size:16px;outline:none}
.searchbar input:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(34,211,238,.18)}
#results{display:none;margin-top:8px;background:var(--panel);border:1px solid var(--line);
  border-radius:12px;overflow:hidden;max-height:330px;overflow-y:auto}
#results.open{display:block}
#results button{display:flex;justify-content:space-between;gap:10px;width:100%;text-align:left;
  background:none;border:none;border-bottom:1px solid #131e38;color:var(--txt);
  padding:10px 16px;font-size:14px;cursor:pointer}
#results button:hover{background:#101a33}
#results .z{color:var(--dim);font-size:12px;letter-spacing:.05em}
#results .none{padding:12px 16px;color:var(--dim);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(248px,1fr));gap:14px;margin-top:26px}
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
  .skyline{height:52px}
  header{padding-top:26px}
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
document.querySelectorAll('.tile').forEach(t=>t.addEventListener('click',()=>openZone(t.dataset.zone)));
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
  }));
});
document.addEventListener('click',e=>{if(!e.target.closest('.searchbar'))box.classList.remove('open');});
openZone('civic',false);
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

    zones = {zid: [] for zid in ZONE_IDS}          # zone -> [(idx, bot, sub)]
    artisan_subs = {}                                # sub zone id or None -> [...]
    for idx, bot in enumerate(bots):
        zid, sub = assign(bot)
        zones[zid].append((idx, bot))
        if zid == "artisan":
            artisan_subs.setdefault(sub, []).append((idx, bot))

    assert sum(len(v) for v in zones.values()) == total, "assignment leak"

    # skyline: deterministic pseudo-random building heights
    heights = [38, 62, 45, 70, 30, 55, 66, 41, 74, 35, 58, 48, 69, 33, 60,
               44, 71, 39, 52, 64, 36, 57, 68, 42, 50, 73, 31, 59, 47, 65]
    skyline = "".join(f'<i style="height:{h}%"></i>' for h in heights)

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

    index = [{"i": idx, "name": b["name"], "zone": assign(b)[0],
              "zoneLabel": zone_label[assign(b)[0]]}
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
<header>
<h1>BOT CITY</h1>
<div class="tagline">Cyber City Monitor · Every Bot Named · Every District On The Grid</div>
<div class="skyline">{skyline}</div>
<div class="stats">
<span class="chip"><b>{total}</b> BOTS IN THE CITY</span>
<span class="chip"><b>{names_under_watch}</b> NAMES UNDER WATCH</span>
<span class="chip">JUDGE SCORECARD · <b>{esc(judge_stat)}</b></span>
<span class="chip"><b>{live_completed}</b> LIVE TRADES COMPLETED CITYWIDE</span>
<span class="chip live"><b>MON NOV 2</b> LIVE TEST DAY</span>
</div>
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
</header>
<main>
<div class="grid">{''.join(tiles)}</div>
{''.join(panels)}
</main>
<footer>BOT CITY MONITOR · generated {esc(gen)} from the live registry ·
separate environments: LONG book and DAY book never mix · paper city, ranked by production</footer>
</div>
<script type="application/json" id="bot-index">{index_json}</script>
<script>{JS}</script>
</body>
</html>
"""
    with open(OUT, "w") as f:
        f.write(page)

    print(f"wrote {OUT} ({len(page):,} bytes)")
    print(f"performance: {live_completed} completed live trades across "
          f"{bots_with_calls} bots · arena bots with activity: "
          f"{len(arena_st)} · JUDGE {judge_stat}")
    print(f"total bots: {total} · names under watch: {names_under_watch}")
    for zid, label, _, _ in ZONES:
        print(f"  {label:<28} {len(zones[zid]):>4}")
    print(f"  {'TOTAL':<28} {sum(len(v) for v in zones.values()):>4}")


if __name__ == "__main__":
    main()
