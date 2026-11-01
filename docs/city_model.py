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
100dvh hero with a Fullscreen API button; the stats panel carries a
CITY P/L strip (total net P/L, completed live trades, best and worst
bot) computed from the same live standings, per bot P/L renders as a
signed green/red figure on every card and panel row, and buildings of
bots with completed trades are tinted green (net profit) or red (net
loss) in the 3D scene. ARENA figures never enter the official strip.

Slim chrome (Aaron, Sat Oct 31, 2026, "I can't see shit"): the default
stage shows only a slim top bar (wordmark, condensed CITY P/L, SEARCH /
STATS / FULLSCREEN buttons). SEARCH expands the bot search inline in
the bar; STATS slides down a glass panel holding the old header
content (chips, full CITY P/L strip, performance note, two book law),
closed by default. The city stays clean and fully visible.

Run: python3 docs/build_page.py
"""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REGISTRY = os.path.join(ROOT, "output", "bots.json")
OUT = os.path.join(HERE, "index.html")

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
