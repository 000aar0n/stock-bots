"""voyager.py - VOYAGER. Universe swing pullback craftsman. SWING.

Declared swing (hold_style "swing"): a pullback entry needs
days to pay. Rule: a universe name in an uptrend (over SMA50)
whose close sits within 2% over its EMA20, RSI in the calm 45
to 55 pocket, on a green day: the swing entry. Exit at +7% or a
close back under the EMA20, or the -8% rule.

Run: python3 handcrafted/voyager.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "VOYAGER"


def universe():
    out = []
    for names in scanner.UNIVERSE.values():
        for t in names:
            if t not in out:
                out.append(t)
    return out


def opens():
    from leaderboard import load_calls
    o = {}
    for c in load_calls():
        if c["bot"] != BOT:
            continue
        if c["side"] in ("buy", "short"):
            o.setdefault(c["ticker"], c)
        elif c["side"] == "exit":
            o.pop(c["ticker"], None)
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--log-calls", action="store_true")
    a = ap.parse_args(argv)
    log = None
    if a.log_calls:
        from leaderboard import log_call; log = log_call
    op = opens()
    print("VOYAGER - swing pullbacks over the wide universe (hold_style: swing)")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        closes = [c["close"] for c in candles]
        last, d = closes[-1], ta.analyze(candles)
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            under = d["ema20"] and last < d["ema20"]
            if move >= 7.0 or under or move <= -8.0:
                why = "+7% swing banked" if move >= 7 else ("under EMA20" if under else "-8% rule")
                print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
                if log: log(BOT, sym, "exit", last, f"VOYAGER exit: {why}")
            continue
        near = (d["ema20"] and last >= d["ema20"]
                and scanner.pct(last, d["ema20"]) <= 2.0)
        setup = bool(d["sma50"] and last > d["sma50"] and near
                     and d["rsi14"] is not None and 45 <= d["rsi14"] <= 55
                     and last > candles[-1]["open"])
        if setup:
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (uptrend pullback, RSI {d['rsi14']})")
            if log: log(BOT, sym, "buy", last, "VOYAGER: swing pullback at EMA20")
    if not hits:
        print("  no swing setups today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
