"""specialists.py - the sector specialists, one module, one config.

Each specialist owns a sector and a small watchlist, runs the same
WICK TA and FALCON data layer on only its names, and prints its own
sector report under its own name. With --log-calls, each logs paper
calls to output/calls.jsonl under its own name (buy on turning_up,
exit when a name it holds on paper turns falling_knife), so THE
BOARD ranks specialists against FALCON, JUDGE and SCALES on the
same $10k reference size.

Run: python3 specialists.py [--only CIRCUIT] [--log-calls]
Writes output/specialists-latest.txt and .json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import earnings_bot
import scanner
import ta

HERE = os.path.dirname(os.path.abspath(__file__))

SPECIALISTS = {
    "CIRCUIT": {"sector": "semiconductors",
                "tickers": ["NVDA", "AVGO", "AMD", "MU", "SMCI", "INTC",
                            "MRVL", "QCOM", "TXN", "AMAT", "LRCX", "KLAC",
                            "ADI", "TSM", "ARM", "ASML", "ANET", "CDNS",
                            "SNPS", "SNDK", "LOGI", "CRSR"]},
    "STACK": {"sector": "big tech and software",
              "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "PLTR",
                          "NOW", "CRM", "ORCL", "ADBE", "CSCO", "PANW",
                          "CRWD", "SNOW", "NET", "DDOG", "IBM", "AKAM",
                          "DIS", "NFLX", "T", "VZ", "TMUS", "CMCSA"]},
    "SATOSHI": {"sector": "crypto and fintech",
                "tickers": ["COIN", "MSTR", "RIOT", "HOOD", "SOFI", "MARA",
                            "CLSK", "PYPL", "AFRM"]},
    "REACTOR": {"sector": "nuclear and energy",
                "tickers": ["OKLO", "SMR", "NNE", "CCJ", "UUUU", "DNN",
                            "CEG", "VST", "BWXT", "XOM", "CVX", "LNG",
                            "COP", "OXY", "SLB", "EOG", "WMB", "KMI",
                            "FCX", "NEM", "AA", "STLD", "NUE"]},
    "PULSE": {"sector": "biotech and healthcare",
              "tickers": ["REGN", "LLY", "UNH", "MRNA", "ABBV", "AMGN",
                          "GILD", "VRTX", "BIIB", "MRK", "PFE", "ISRG"]},
    "AEGIS": {"sector": "defense and industrials",
              "tickers": ["KTOS", "LMT", "RTX", "NOC", "GD", "BA", "AVAV",
                          "HII", "CAT", "DE", "GE", "HON", "UPS", "FDX",
                          "EMR", "ETN"]},
    "CART": {"sector": "consumer, retail and travel",
             "tickers": ["WMT", "COST", "CPRI", "CVNA", "HD", "LOW", "TGT",
                         "NKE", "SBUX", "MCD", "CMG", "LULU", "KO", "PEP",
                         "MNST", "DAL", "UAL", "AAL", "LUV", "MAR", "BKNG",
                         "ABNB", "CCL", "RCL", "EXPE"]},
    "VAULT": {"sector": "banks and payments",
              "tickers": ["JPM", "BAC", "GPN", "WFC", "C", "GS", "MS",
                          "SCHW", "USB", "V", "MA", "AXP", "FIS", "COF"]},
    "ROCKET": {"sector": "high beta momentum bench",
               "tickers": ["TSLA", "RKLB", "IONQ", "RDDT", "SNDK", "RBLX"]},
}


def run_specialist(name, cfg, earnings_rows):
    rows, latency, errors = [], [], []
    for sym in cfg["tickers"]:
        try:
            candles = scanner.fetch_daily(sym)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{sym}: {e}")
            continue
        closes = [c["close"] for c in candles]
        sdata = {
            "last_close": round(closes[-1], 2),
            "chg_1d_pct": round(scanner.pct(closes[-1], closes[-2]), 2),
            "chg_5d_pct": round(scanner.pct(closes[-1], closes[-6]), 2),
            "ta": ta.analyze(candles),
        }
        lat = scanner.latency_check(sym, sdata)
        sdata["latency"] = lat
        if lat["candidate"]:
            latency.append(sym)
        sdata["next_earnings"] = earnings_rows.get(sym)
        rows.append((sym, sdata))
        time.sleep(0.1)
    return {"name": name, "sector": cfg["sector"], "rows": rows,
            "latency": latency, "errors": errors}


def build_section(res):
    lines = [f"{res['name']} - {res['sector']}"]
    for sym, s in res["rows"]:
        t = s["ta"]
        flags = []
        if t["turning_up"]:
            flags.append("TURNING_UP")
        if t["falling_knife"]:
            flags.append("FALLING_KNIFE")
        if s["latency"]["candidate"]:
            flags.append("LATENCY_CANDIDATE")
        line = (f"  {sym:<6} ${s['last_close']:>9}  1d {s['chg_1d_pct']:+.2f}%  "
                f"5d {s['chg_5d_pct']:+.2f}%  {t['trend']:<9} "
                f"RSI {t['rsi14'] if t['rsi14'] is not None else 'n/a'}  "
                f"{' '.join(flags)}")
        lines.append(line)
        if s.get("next_earnings"):
            e = s["next_earnings"]
            lines.append(f"         next earnings: {e['date']} ({e['when']}), "
                         f"{e['sessions_until']} session(s) away")
    if res["latency"]:
        lines.append("  latency candidates in sector: "
                     + ", ".join(res["latency"])
                     + " (stale price candidates, verify the HTMW "
                       "displayed price before any order)")
    if res["errors"]:
        lines.append("  fetch errors: " + "; ".join(res["errors"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None,
                    help="run one specialist by name, e.g. CIRCUIT")
    ap.add_argument("--log-calls", action="store_true")
    args = ap.parse_args(argv)
    names = [args.only] if args.only else list(SPECIALISTS)
    earnings_rows = {r["ticker"]: r for r in earnings_bot.evaluate()}
    sections, summary = [], {}
    open_map = {}
    if args.log_calls:
        from leaderboard import load_calls, open_positions
        open_map = open_positions(load_calls())
    for name in names:
        res = run_specialist(name, SPECIALISTS[name], earnings_rows)
        sections.append(build_section(res))
        summary[name] = {
            "turning_up": [s for s, d in res["rows"] if d["ta"]["turning_up"]],
            "falling_knife": [s for s, d in res["rows"]
                              if d["ta"]["falling_knife"]],
            "latency": res["latency"],
        }
        if args.log_calls:
            from leaderboard import log_call
            for sym, d in res["rows"]:
                t = d["ta"]
                if t["turning_up"] and not t["falling_knife"] \
                        and (name, sym) not in open_map:
                    log_call(name, sym, "buy", d["last_close"],
                             f"{name} specialist: turning_up in "
                             f"{res['sector']}")
                elif t["falling_knife"] and (name, sym) in open_map:
                    log_call(name, sym, "exit", d["last_close"],
                             f"{name} specialist: falling_knife, "
                             "paper exit")
    report = "\n\n".join(sections)
    print(report)
    out_dir = os.path.join(HERE, "output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "specialists-latest.txt"), "w") as f:
        f.write(report + "\n")
    with open(os.path.join(out_dir, "specialists-latest.json"), "w") as f:
        json.dump(summary, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
