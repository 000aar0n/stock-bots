"""compass.py - COMPASS. Tech relative strength vs QQQ craftsman.

COMPASS ranks the liquid tech bench by five session relative
strength against QQQ and calls ONLY the top name, and only when
it beats the index by 5+ points AND is turning_up (leadership
with a pulse, not a fading spike). Exit when the held name's RS
drops under zero, or the -8% rule.

Run: python3 handcrafted/compass.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "COMPASS"
BENCH = ["AAPL", "NVDA", "AVGO", "AMD", "MSFT", "GOOGL", "AMZN", "META",
         "PLTR", "TSLA", "COIN", "MSTR", "HOOD", "SOFI", "NOW", "INTC",
         "RBLX", "MU", "SMCI", "IONQ", "RKLB", "CVNA", "RDDT", "SNDK",
         "MRVL", "RIOT", "AKAM"]


def chg5(candles):
    closes = [c["close"] for c in candles]
    return scanner.pct(closes[-1], closes[-6])


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
    bench5 = chg5(scanner.fetch_daily("QQQ"))
    rows = []
    for sym in BENCH:
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        rows.append((chg5(candles) - bench5, sym, candles))
    rows.sort(reverse=True)
    op = opens()
    print(f"COMPASS - tech RS vs QQQ (QQQ 5d {bench5:+.2f}%)")
    for rs, sym, candles in rows[:3]:
        print(f"  {sym}: RS {rs:+.2f} pts")
    for rs, sym, candles in rows:
        last = candles[-1]["close"]
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            if rs < 0 or move <= -8.0:
                why = "RS went negative" if rs < 0 else "-8% rule"
                print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
                if log: log(BOT, sym, "exit", last, f"COMPASS exit: {why}")
    top_rs, top_sym, top_c = rows[0]
    if top_sym not in op and top_rs > 5 and ta.analyze(top_c)["turning_up"]:
        last = top_c[-1]["close"]
        print(f"  CALL: BUY {top_sym} @ ${last:.2f} (RS leader at {top_rs:+.2f} pts, turning up)")
        if log: log(BOT, top_sym, "buy", last, f"COMPASS: top RS vs QQQ at {top_rs:+.1f} pts")
    elif top_sym not in op:
        print("  leader lacks the margin or the pulse, no call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
