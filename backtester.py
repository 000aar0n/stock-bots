"""backtester.py - REWIND. Replays old tape through the signal rules.

REWIND runs a simple long only replay over historical daily candles:
enter at the close when WICK's turning_up heuristic fires, exit at
the close on the Protected Momentum exit rules (down 8% from entry,
or red at two straight closes), $10 commission per order (the HTMW
rate), starting equity $10,000 per symbol, fractional shares.

Data: the shared data layer (scanner.fetch_daily). The original
brief said Stooq; Stooq is unreachable from this VM, so the replay
runs on Yahoo daily candles like everything else here.

LIMITS (printed with every run): daily candles only, fills assumed
at the close, no slippage beyond the $10 per order commission, the
symbol list is chosen by us (survivorship), fractional shares, and
the signals are heuristics. A good replay proves nothing about the
next six months.

Run: python3 backtester.py [SYMBOL ...] [--days 182]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

import scanner
import ta

COMMISSION = 10.0
START_EQUITY = 10_000.0
WARMUP = 60  # bars before signals are trusted


def backtest_symbol(symbol, candles, start_idx):
    cash, shares, entry = START_EQUITY, 0.0, None
    trades, curve = [], []
    open_trade, equity_at_entry = None, None
    for i, cd in enumerate(candles):
        price = cd["close"]
        if i >= WARMUP:
            sig = ta.analyze(candles[:i + 1])
            if shares == 0 and i >= start_idx and sig.get("turning_up"):
                equity_at_entry = cash
                shares = (cash - COMMISSION) / price
                cash, entry = 0.0, price
                open_trade = {"entry_date": cd["date"], "entry": price}
            elif shares > 0:
                two_red = (i >= 2 and candles[i]["close"] < candles[i - 1]["close"]
                           < candles[i - 2]["close"])
                if price <= entry * 0.92 or two_red:
                    cash = shares * price - COMMISSION
                    trades.append({**open_trade, "exit_date": cd["date"],
                                   "exit": price,
                                   "pnl": cash - equity_at_entry})
                    shares, entry, open_trade = 0.0, None, None
        curve.append(cash + shares * price)
    if shares > 0:
        price = candles[-1]["close"]
        cash = shares * price - COMMISSION
        trades.append({**open_trade, "exit_date": candles[-1]["date"],
                       "exit": price, "pnl": cash - equity_at_entry})
        curve[-1] = cash
    peak, max_dd = curve[0], 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak * 100.0)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    return {
        "symbol": symbol, "trades": len(trades),
        "final_equity": cash,
        "total_return_pct": (cash / START_EQUITY - 1.0) * 100.0,
        "max_drawdown_pct": max_dd,
        "win_rate_pct": (100.0 * wins / len(trades)) if trades else None,
        "trade_list": trades,
    }


LIMITS = ("LIMITS: daily candles only, fills assumed at the close, no "
          "slippage beyond the $10 per order commission, symbol list "
          "chosen by us (survivorship), fractional shares, heuristic "
          "signals. History, not a promise.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="*", default=["NVDA", "CVNA"])
    ap.add_argument("--days", type=int, default=182,
                    help="replay window in days (default about 6 months)")
    args = ap.parse_args(argv)
    symbols = args.symbols or ["NVDA", "CVNA"]
    print(f"REWIND - backtest, last ~{args.days} days, $10 commission "
          "per order, $10,000 start per symbol")
    results = []
    for sym in symbols:
        try:
            candles = scanner.fetch_daily(sym)
        except Exception as e:  # noqa: BLE001
            print(f"  {sym}: data error: {e}")
            continue
        cutoff = (date.fromisoformat(candles[-1]["date"])
                  - timedelta(days=args.days)).isoformat()
        start_idx = next((i for i, c in enumerate(candles)
                          if c["date"] >= cutoff), len(candles) - 1)
        r = backtest_symbol(sym, candles, start_idx)
        r["from"] = candles[start_idx]["date"]
        r["to"] = candles[-1]["date"]
        results.append(r)
        wr = "n/a" if r["win_rate_pct"] is None else f"{r['win_rate_pct']:.0f}%"
        print(f"  {sym:<6} {r['from']} to {r['to']}: "
              f"return {r['total_return_pct']:+.1f}%, "
              f"max drawdown {r['max_drawdown_pct']:.1f}%, "
              f"win rate {wr}, trades {r['trades']}, "
              f"final ${r['final_equity']:,.0f}")
    if len(results) > 1:
        tot_ret = (sum(r["final_equity"] for r in results)
                   / (START_EQUITY * len(results)) - 1.0) * 100.0
        tot_trades = sum(r["trades"] for r in results)
        all_trades = [t for r in results for t in r["trade_list"]]
        wins = sum(1 for t in all_trades if t["pnl"] > 0)
        wr = f"{100.0 * wins / len(all_trades):.0f}%" if all_trades else "n/a"
        print(f"  OVERALL: return {tot_ret:+.1f}%, win rate {wr}, "
              f"trades {tot_trades}")
    print(LIMITS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
