"""scanner.py - widened-universe scan for the HTMW sim book.

Data: Yahoo chart API (free, keyless), daily candles, 2y range.
(Stooq was the first choice but is unreachable from this VM - its
connections hang - so Yahoo is the working source; see README.)
For each symbol: last close, 1 day and 5 session percent change, and
a TA summary from ta.py (heuristics only). Also computes stat arb
pair gaps (5 session relative performance in points) for the
Protected Momentum pair list, flagging gaps of 10 points or more,
the style's entry threshold.

Latency edge: HTMW quotes are 15 minutes delayed while this scanner
reads live data. Any name whose live price moved sharply in the most
recent measurable window (last ~30 minutes of intraday bars, or the
latest session on the daily fallback) is flagged a
"latency_candidate": the sim may still be showing, and filling near,
the older price. Candidates always carry the note to verify against
the price HTMW displays before any order.

Two speeds by design: the wide universe is scanned on daily candles
for discovery. The CORE_INTRADAY names (a default 20 chosen for
liquidity and tradable volatility, not strict market cap rank) also
get TA computed on 5 minute candles for timing, and the output marks
which timeframe is driving each turning_up / falling_knife flag -
fast moves on liquid, volatile names are where latency candidates
matter most.

Writes output/scan-latest.txt (readable) and output/scan-latest.json.
Run: python3 scanner.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

import ta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output")

UNIVERSE = {
    "tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "PLTR", "NOW", "CRM",
             "ORCL", "ADBE", "CSCO", "PANW", "CRWD", "SNOW", "NET", "DDOG",
             "IBM", "AKAM", "LOGI", "CRSR"],
    "semis": ["NVDA", "AVGO", "AMD", "MU", "SMCI", "INTC", "MRVL", "QCOM",
              "TXN", "AMAT", "LRCX", "KLAC", "ADI", "TSM", "ARM", "ASML",
              "ANET", "CDNS", "SNPS", "SNDK"],
    "crypto_fintech": ["COIN", "MSTR", "RIOT", "HOOD", "SOFI", "MARA",
                       "CLSK", "PYPL", "AFRM"],
    "high_beta": ["TSLA", "RKLB", "IONQ", "RDDT", "RBLX", "CVNA"],
    "nuclear": ["OKLO", "SMR", "NNE", "CCJ", "UUUU", "DNN", "CEG", "VST", "BWXT"],
    "energy": ["XOM", "CVX", "LNG", "COP", "OXY", "SLB", "EOG", "WMB", "KMI"],
    "defense": ["KTOS", "LMT", "RTX", "NOC", "GD", "BA", "AVAV", "HII"],
    "banks": ["JPM", "BAC", "WFC", "C", "GS", "MS", "SCHW", "USB"],
    "payments": ["GPN", "V", "MA", "AXP", "FIS", "COF"],
    "healthcare_biotech": ["REGN", "LLY", "UNH", "MRNA", "ABBV", "AMGN",
                           "GILD", "VRTX", "BIIB", "MRK", "PFE", "ISRG"],
    "retail": ["WMT", "COST", "CPRI", "HD", "LOW", "TGT", "NKE", "SBUX",
               "MCD", "CMG", "LULU", "KO", "PEP", "MNST"],
    "travel": ["DAL", "UAL", "AAL", "LUV", "MAR", "BKNG", "ABNB", "CCL",
               "RCL", "EXPE"],
    "industrials": ["CAT", "DE", "GE", "HON", "UPS", "FDX", "EMR", "ETN"],
    "media_telecom": ["DIS", "NFLX", "T", "VZ", "TMUS", "CMCSA"],
    "materials": ["FCX", "NEM", "AA", "STLD", "NUE"],
    "pairs_watch": ["KO", "PEP"],
}

# PENNY STOCK FENCE (Aaron, Sat Oct 31, 2026): standing coverage is
# for real stocks only: price generally above $5 and real daily
# dollar volume. Microcap squeeze names are EXCLUDED from standing
# coverage (no watcher, shadow, rival or sniper minted on them);
# they stay visible to the marketwide big move scan and the capped
# day trade sleeve only. Excluded examples:
EXCLUDED_PENNY = ["UMAC", "ONDS", "AMPX", "NUWE", "BRAI"]

PAIRS = [("NVDA", "AVGO"), ("AMD", "INTC"), ("COIN", "MSTR"), ("SOFI", "HOOD"),
         ("XOM", "CVX"), ("JPM", "BAC"), ("KO", "PEP"), ("WMT", "COST")]

PAIR_GAP_FLAG = 10.0  # points of 5-session relative performance

# Default core list (Aaron, Sat Oct 31): 20 names kept for liquidity
# and tradable volatility, not strict market cap rank. These get TA
# on 5 minute candles as well as daily; everything else stays daily.
CORE_INTRADAY = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "AVGO",
                 "TSLA", "LLY", "JPM", "WMT", "V", "XOM", "COST", "AMD",
                 "PLTR", "MU", "COIN", "MSTR", "NOW"]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"})

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"


def fetch_daily(symbol, retries=2):
    """Daily OHLCV candles from Yahoo's chart API (2y, 1d), oldest
    first. Raises on failure. Handles HTTP 429 with a short backoff."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = SESSION.get(CHART_URL + symbol,
                            params={"range": "2y", "interval": "1d"},
                            timeout=20)
            if r.status_code == 429:
                raise RuntimeError("HTTP 429 (rate limited)")
            r.raise_for_status()
            result = (r.json().get("chart", {}).get("result") or [None])[0]
            if not result:
                raise ValueError(f"empty chart result for {symbol}")
            stamps = result.get("timestamp") or []
            quote = (result.get("indicators", {}).get("quote") or [{}])[0]
            opens, highs = quote.get("open") or [], quote.get("high") or []
            lows, closes = quote.get("low") or [], quote.get("close") or []
            vols = quote.get("volume") or []
            candles = []
            for i, ts in enumerate(stamps):
                vals = [opens[i] if i < len(opens) else None,
                        highs[i] if i < len(highs) else None,
                        lows[i] if i < len(lows) else None,
                        closes[i] if i < len(closes) else None]
                if any(v is None for v in vals):
                    continue  # Yahoo pads holidays with null rows
                day = datetime.fromtimestamp(ts, tz=timezone.utc)
                candles.append({
                    "date": day.strftime("%Y-%m-%d"),
                    "open": float(vals[0]), "high": float(vals[1]),
                    "low": float(vals[2]), "close": float(vals[3]),
                    "volume": float(vols[i]) if i < len(vols) and vols[i] else 0.0,
                })
            # Yahoo may include the current, unfinished daily candle.
            now = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
            candles = [c for c in candles if c["date"] < now.date().isoformat() or (c["date"] == now.date().isoformat() and now.hour >= 16)]
            candles.sort(key=lambda c: c["date"])
            if len(candles) < 6:
                raise ValueError(f"only {len(candles)} usable rows for {symbol}")
            return candles
        except Exception as e:  # noqa: BLE001 - report and move on per symbol
            last_err = e
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"{symbol}: {last_err}")


LATENCY_WINDOW_SECS = 30 * 60   # most recent window we can measure
LATENCY_MOVE_PCT = 2.0          # sharp move inside that window, percent
LATENCY_FALLBACK_DAY_PCT = 4.0  # sharp full-session move, daily fallback
STALE_NOTE = ("Stale price candidate: HTMW quotes are 15 min delayed, "
              "so verify against the price HTMW displays before any order.")


def fetch_intraday_candles(symbol, retries=2):
    """OHLCV candle dicts (plus a 'ts' epoch key) from Yahoo 5m bars
    for the latest session, oldest first. Raises on failure."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = SESSION.get(CHART_URL + symbol,
                            params={"range": "1d", "interval": "5m"},
                            timeout=20)
            if r.status_code == 429:
                raise RuntimeError("HTTP 429 (rate limited)")
            r.raise_for_status()
            result = (r.json().get("chart", {}).get("result") or [None])[0]
            if not result:
                raise ValueError(f"empty intraday result for {symbol}")
            stamps = result.get("timestamp") or []
            quote = (result.get("indicators", {}).get("quote") or [{}])[0]
            opens, highs = quote.get("open") or [], quote.get("high") or []
            lows, closes = quote.get("low") or [], quote.get("close") or []
            vols = quote.get("volume") or []
            candles = []
            for i, ts in enumerate(stamps):
                vals = [opens[i] if i < len(opens) else None,
                        highs[i] if i < len(highs) else None,
                        lows[i] if i < len(lows) else None,
                        closes[i] if i < len(closes) else None]
                if any(v is None for v in vals):
                    continue
                candles.append({
                    "ts": ts, "date": datetime.fromtimestamp(
                        ts, tz=timezone.utc).isoformat(timespec="minutes"),
                    "open": float(vals[0]), "high": float(vals[1]),
                    "low": float(vals[2]), "close": float(vals[3]),
                    "volume": float(vols[i]) if i < len(vols) and vols[i] else 0.0,
                })
            # Five-minute bars are usable only after their interval completes.
            now_ts = datetime.now(timezone.utc).timestamp()
            candles = [c for c in candles if c["ts"] + 300 <= now_ts]
            if len(candles) < 2:
                raise ValueError(f"only {len(candles)} completed intraday bars for {symbol}")
            return candles
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"{symbol} intraday: {last_err}")


def fetch_intraday(symbol, retries=2):
    """Compatibility name used by handcrafted bots; honors replay/cache patches."""
    return fetch_intraday_candles(symbol, retries=retries)


def _flag_driver(daily_flag, intraday_flag):
    """Which timeframe is driving a flag: 'daily', 'intraday_5m',
    'both', or None when neither timeframe raises it."""
    if daily_flag and intraday_flag:
        return "both"
    if intraday_flag:
        return "intraday_5m"
    if daily_flag:
        return "daily"
    return None


def latency_check(symbol, sdata, candles=None):
    """Flag a latency candidate: live price moved sharply in the most
    recent window, so the sim's 15 min delayed feed may be stale.
    Uses intraday bars when available, else the daily move."""
    lat = {"candidate": False, "basis": None, "window": None,
           "move_pct": None, "live_price": sdata["last_close"], "note": None}
    try:
        if candles is None:
            candles = fetch_intraday_candles(symbol)
        bars = [(c["ts"], c["close"]) for c in candles]
        last_ts, last_close = bars[-1]
        target = last_ts - LATENCY_WINDOW_SECS
        earlier = [b for b in bars if b[0] <= target]
        ref_close = earlier[-1][1] if earlier else bars[0][1]
        move = pct(last_close, ref_close)
        lat.update({"basis": "intraday_30m",
                    "window": "last ~30 min of latest session",
                    "move_pct": None if move is None else round(move, 2),
                    "live_price": round(last_close, 2)})
        lat["candidate"] = move is not None and abs(move) >= LATENCY_MOVE_PCT
    except Exception:  # noqa: BLE001 - fall back to the daily move
        move = sdata["chg_1d_pct"]
        lat.update({"basis": "daily_fallback",
                    "window": "latest session vs prior close",
                    "move_pct": move})
        lat["candidate"] = move is not None and abs(move) >= LATENCY_FALLBACK_DAY_PCT
    if lat["candidate"]:
        lat["note"] = STALE_NOTE
    return lat


def probe_yahoo_intraday(symbol="NVDA"):
    """Probe Yahoo's keyless chart API for intraday (15m) candles.
    Returns a status string; the scan itself runs on daily candles."""
    try:
        r = SESSION.get(CHART_URL + symbol,
                        params={"interval": "15m", "range": "1d"}, timeout=15)
        if r.status_code != 200:
            return f"unavailable (HTTP {r.status_code})"
        result = (r.json().get("chart", {}).get("result") or [None])[0]
        if not result:
            return "unavailable (empty result)"
        ts = result.get("timestamp") or []
        return f"available ({len(ts)} intraday bars for {symbol})"
    except Exception as e:  # noqa: BLE001
        return f"unavailable ({type(e).__name__})"


def pct(new, old):
    if old in (None, 0) or new is None:
        return None
    return (new / old - 1.0) * 100.0


def run_scan():
    symbols = {}
    errors = {}
    data_date = None
    intraday_bars = {}  # CORE_INTRADAY candles, reused by the latency pass
    for group, tickers in UNIVERSE.items():
        for sym in tickers:
            try:
                candles = fetch_daily(sym)
            except Exception as e:  # noqa: BLE001
                errors[sym] = str(e)
                continue
            closes = [c["close"] for c in candles]
            last = candles[-1]
            if data_date is None or last["date"] > data_date:
                data_date = last["date"]
            daily_ta = ta.analyze(candles)
            symbols[sym] = {
                "group": group,
                "date": last["date"],
                "last_close": round(last["close"], 2),
                "chg_1d_pct": round(pct(closes[-1], closes[-2]), 2),
                "chg_5d_pct": round(pct(closes[-1], closes[-6]), 2),
                "closes_tail": [round(c, 2) for c in closes[-3:]],
                "ta": daily_ta,
            }
            if sym in CORE_INTRADAY:
                sdata = symbols[sym]
                try:
                    icandles = fetch_intraday_candles(sym)
                    intraday_bars[sym] = icandles
                    ita = ta.analyze(icandles)
                    sdata["ta_intraday"] = ita
                    sdata["flag_drivers"] = {
                        "turning_up": _flag_driver(daily_ta["turning_up"],
                                                   ita["turning_up"]),
                        "falling_knife": _flag_driver(daily_ta["falling_knife"],
                                                      ita["falling_knife"]),
                    }
                    sdata["intraday_status"] = (
                        f"ok ({len(icandles)} x 5m bars)")
                except Exception as e:  # noqa: BLE001
                    sdata["ta_intraday"] = None
                    sdata["flag_drivers"] = {
                        "turning_up": _flag_driver(daily_ta["turning_up"], False),
                        "falling_knife": _flag_driver(daily_ta["falling_knife"],
                                                      False),
                    }
                    sdata["intraday_status"] = f"unavailable ({e})"
            time.sleep(0.1)

    pairs = []
    for a, b in PAIRS:
        if a in symbols and b in symbols:
            gap = round(symbols[a]["chg_5d_pct"] - symbols[b]["chg_5d_pct"], 2)
            pairs.append({
                "pair": f"{a}/{b}",
                "gap_points": gap,
                "abs_gap": abs(gap),
                "flagged": abs(gap) >= PAIR_GAP_FLAG,
                # The 5-session laggard is the "cheap" (long) leg per the style.
                "long_leg": a if gap < 0 else b,
                "short_leg": b if gap < 0 else a,
            })
        else:
            pairs.append({"pair": f"{a}/{b}", "gap_points": None,
                          "abs_gap": None, "flagged": False,
                          "long_leg": None, "short_leg": None,
                          "note": "missing data for one leg"})
    pairs.sort(key=lambda p: -(p["abs_gap"] or 0))

    latency_candidates = []
    for sym, sdata in symbols.items():
        lat = latency_check(sym, sdata, candles=intraday_bars.get(sym))
        sdata["latency"] = lat
        if lat["candidate"]:
            latency_candidates.append({"symbol": sym, **lat})
        time.sleep(0.1)
    latency_candidates.sort(key=lambda c: -abs(c["move_pct"] or 0))

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_date": data_date,
        "yahoo_intraday": probe_yahoo_intraday(),
        "core_intraday": CORE_INTRADAY,
        "symbols": symbols,
        "pairs": pairs,
        "latency_candidates": latency_candidates,
        "errors": errors,
    }


def _fmt(x, suffix=""):
    return "n/a" if x is None else f"{x:+.2f}{suffix}" if suffix == "%" else f"{x}{suffix}"


def build_report(data):
    syms = data["symbols"]
    lines = []
    lines.append(f"FALCON - HTMW SCAN  generated {data['generated_at']}  "
                 f"data through {data['data_date']} (Yahoo daily closes)")
    lines.append(f"Yahoo intraday probe: {data['yahoo_intraday']}")
    lines.append("TA flags are heuristics from ta.py, not predictions.")
    lines.append("")
    ranked = sorted(syms.items(), key=lambda kv: -(kv[1]["chg_5d_pct"] or 0))
    lines.append("TOP 10 BY 5-SESSION CHANGE")
    for sym, s in ranked[:10]:
        t = s["ta"]
        flags = []
        if t["turning_up"]:
            flags.append("TURNING_UP")
        if t["falling_knife"]:
            flags.append("FALLING_KNIFE")
        if t["patterns"]:
            flags.append(",".join(t["patterns"]))
        lines.append(f"  {sym:<6} ${s['last_close']:>9}  1d {_fmt(s['chg_1d_pct'],'%'):>7}  "
                     f"5d {_fmt(s['chg_5d_pct'],'%'):>7}  {t['trend']:<9} RSI {_fmt(t['rsi14']):>6}  "
                     f"{' '.join(flags)}")
    lines.append("")
    lines.append("BOTTOM 10 BY 5-SESSION CHANGE")
    for sym, s in ranked[-10:][::-1]:
        t = s["ta"]
        flags = []
        if t["turning_up"]:
            flags.append("TURNING_UP")
        if t["falling_knife"]:
            flags.append("FALLING_KNIFE")
        if t["patterns"]:
            flags.append(",".join(t["patterns"]))
        lines.append(f"  {sym:<6} ${s['last_close']:>9}  1d {_fmt(s['chg_1d_pct'],'%'):>7}  "
                     f"5d {_fmt(s['chg_5d_pct'],'%'):>7}  {t['trend']:<9} RSI {_fmt(t['rsi14']):>6}  "
                     f"{' '.join(flags)}")
    lines.append("")
    lines.append("STAT ARB PAIR GAPS (5-session relative performance, points; "
                 f"flag at >= {PAIR_GAP_FLAG:.0f})")
    for p in data["pairs"]:
        if p["gap_points"] is None:
            lines.append(f"  {p['pair']:<10} n/a  ({p.get('note','')})")
        else:
            mark = "  <-- AT/OVER ENTRY THRESHOLD" if p["flagged"] else ""
            lines.append(f"  {p['pair']:<10} gap {p['gap_points']:+.2f} pts  "
                         f"long {p['long_leg']} / short {p['short_leg']}{mark}")
    lines.append("")
    lines.append("LATENCY CANDIDATES (live price moved sharply in the most "
                 "recent window; the sim feed is 15 min delayed)")
    if data.get("latency_candidates"):
        for c in data["latency_candidates"]:
            lines.append(f"  {c['symbol']:<6} live ${c['live_price']:>9}  "
                         f"move {_fmt(c['move_pct'], '%'):>7} over "
                         f"{c['window']}  [{c['basis']}]")
            lines.append(f"         {c['note']}")
    else:
        lines.append("  none this scan")
    lines.append("")
    lines.append("CORE INTRADAY (core 20, liquidity and volatility picks: "
                 "TA on daily AND 5 minute candles; driver = timeframe "
                 "behind the flag)")
    for sym in data.get("core_intraday", []):
        s = syms.get(sym)
        if s is None:
            lines.append(f"  {sym:<6} no daily data this scan")
            continue
        d = s["ta"]
        dflags = []
        if d["turning_up"]:
            dflags.append("TURNING_UP")
        if d["falling_knife"]:
            dflags.append("FALLING_KNIFE")
        line = (f"  {sym:<6} daily[{d['trend']} RSI {_fmt(d['rsi14'])}"
                f"{' ' + ','.join(dflags) if dflags else ''}]")
        ita = s.get("ta_intraday")
        if ita:
            iflags = []
            if ita["turning_up"]:
                iflags.append("TURNING_UP")
            if ita["falling_knife"]:
                iflags.append("FALLING_KNIFE")
            if ita["patterns"]:
                iflags.append(",".join(ita["patterns"]))
            line += (f"  5m[{ita['trend']} RSI {_fmt(ita['rsi14'])}"
                     f"{' ' + ' '.join(iflags) if iflags else ''}]")
        else:
            line += f"  5m[{s.get('intraday_status', 'unavailable')}]"
        drv = s.get("flag_drivers") or {}
        driven = [f"{k} <- {v}" for k, v in drv.items() if v]
        line += "  drivers: " + (", ".join(driven) if driven else "no flags")
        lines.append(line)
    lines.append("")
    lines.append("NOTE: a flagged gap is only a candidate. The style also "
                 "requires NO fundamental news behind the stretch; earnings "
                 "or guidance shocks disqualify a pair for 2 sessions. That "
                 "news check is not automated here.")
    if data["errors"]:
        lines.append("")
        lines.append(f"FETCH ERRORS ({len(data['errors'])}): "
                     + ", ".join(sorted(data["errors"])))
    return "\n".join(lines)


def log_falcon_calls(data):
    """Log FALCON paper calls for THE BOARD: buy calls on turning_up
    names (top 10 by 5 session change), skipping names FALCON already
    has open. Latency candidates are noted in the reason when they
    apply; a latency flag alone is not a buy call."""
    from leaderboard import load_calls, log_call, open_positions
    opens = open_positions(load_calls())
    latency_syms = {c["symbol"] for c in data.get("latency_candidates", [])}
    ranked = sorted(data["symbols"].items(),
                    key=lambda kv: -(kv[1]["chg_5d_pct"] or 0))
    logged = 0
    for sym, s in ranked:
        if logged >= 10:
            break
        t = s["ta"]
        if not t.get("turning_up") or t.get("falling_knife"):
            continue
        if ("FALCON", sym) in opens:
            continue
        reason = "turning_up on daily candles"
        if sym in latency_syms:
            reason += "; also a latency candidate, stale price possible"
        log_call("FALCON", sym, "buy", s["last_close"], reason)
        logged += 1
    return logged


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-calls", action="store_true",
                    help="also log FALCON paper calls to output/calls.jsonl "
                         "(Monday shadow mode; off for tests)")
    args = ap.parse_args(argv)
    data = run_scan()
    report = build_report(data)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "scan-latest.txt"), "w") as f:
        f.write(report + "\n")
    with open(os.path.join(OUT_DIR, "scan-latest.json"), "w") as f:
        json.dump(data, f, indent=1)
    print(report)
    if args.log_calls:
        n = log_falcon_calls(data)
        print(f"[FALCON] logged {n} paper call(s) to output/calls.jsonl",
              file=sys.stderr)
    print(f"\n[{len(data['symbols'])} symbols scanned, "
          f"{len(data['errors'])} errors; wrote output/scan-latest.txt and .json]",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
