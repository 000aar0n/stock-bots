"""meridian.py - MERIDIAN. Style meridian on 20 session RS.

CROSSCURRENT rotates on five sessions; MERIDIAN is the slow
compass: it scores four style anchors on TWENTY session moves
(growth QQQ, value DIA, big SPY, small IWM), maps the strongest
style to its basket (growth: NVDA, MSFT; value: JPM, XOM;
defensive big: LLY, WMT; small: the top anchor itself skipped,
small maps to growth bench), and calls that basket's 20 session
leader. Exit when a different style takes the meridian, or -8%.

Run: python3 handcrafted/meridian.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "MERIDIAN"
STYLES = {"growth": ("QQQ", ["NVDA", "MSFT"]),
          "value": ("DIA", ["JPM", "XOM"]),
          "defensive": ("SPY", ["LLY", "WMT"]),
          "small": ("IWM", ["NVDA", "MSFT"])}


def chg(candles, n=20):
    closes = [c["close"] for c in candles]
    return scanner.pct(closes[-1], closes[-1 - n])


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
    scores = {}
    for style, (anchor, _b) in STYLES.items():
        scores[style] = chg(scanner.fetch_daily(anchor))
    best_style = max(scores, key=scores.get)
    basket = STYLES[best_style][1]
    op = opens()
    print("MERIDIAN - 20 session style scores: "
          + ", ".join(f"{s} {v:+.1f}%" for s, v in scores.items())
          + f"  strongest: {best_style}")
    for sym in list(op):
        candles = scanner.fetch_daily(sym)
        last = candles[-1]["close"]
        move = scanner.pct(last, op[sym]["entry_price"])
        if sym not in basket or move <= -8.0:
            why = "style meridian moved" if sym not in basket else "-8% rule"
            print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
            if log: log(BOT, sym, "exit", last, f"MERIDIAN exit: {why}")
    rows = []
    for sym in basket:
        candles = scanner.fetch_daily(sym)
        rows.append((chg(candles), sym, candles[-1]["close"]))
    rows.sort(reverse=True)
    chg20, sym, last = rows[0]
    if sym not in op:
        print(f"  CALL: BUY {sym} @ ${last:.2f} ({best_style} leader, 20d {chg20:+.2f}%)")
        if log: log(BOT, sym, "buy", last, f"MERIDIAN: {best_style} style leader on 20d RS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
