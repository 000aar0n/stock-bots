"""ballast.py - BALLAST. Small cap risk appetite craftsman.

BALLAST reads the market's appetite from IWM vs SPY: when small
caps beat the big index by over 2 points across five sessions,
risk appetite is real and BALLAST calls the top turning_up name
on the high beta bench (RKLB, IONQ, SNDK, CVNA). Exit when IWM
falls back behind SPY (appetite gone) or the -8% rule.

Run: python3 handcrafted/ballast.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "BALLAST"
BENCH = ["RKLB", "IONQ", "SNDK", "CVNA"]


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
    spread = chg5(scanner.fetch_daily("IWM")) - chg5(scanner.fetch_daily("SPY"))
    appetite = spread > 2
    op = opens()
    print(f"BALLAST - risk appetite  IWM minus SPY over 5 sessions: "
          f"{spread:+.2f} pts (appetite: {appetite})")
    rows = []
    for sym in BENCH:
        candles = scanner.fetch_daily(sym)
        rows.append((chg5(candles), sym, candles, ta.analyze(candles)))
    rows.sort(key=lambda r: r[0], reverse=True)
    for chg, sym, candles, _d in rows:
        if sym in op:
            last = candles[-1]["close"]
            move = scanner.pct(last, op[sym]["entry_price"])
            if not appetite or move <= -8.0:
                why = "appetite gone (IWM lagging again)" if not appetite else "-8% rule"
                print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
                if log: log(BOT, sym, "exit", last, f"BALLAST exit: {why}")
    if appetite:
        for chg, sym, candles, d in rows:
            if sym not in op and d["turning_up"]:
                last = candles[-1]["close"]
                print(f"  CALL: BUY {sym} @ ${last:.2f} (appetite on, top beta name turning up)")
                if log: log(BOT, sym, "buy", last, "BALLAST: IWM leading, beta bench turning_up")
                break
        else:
            print("  appetite on but the bench is not turning up, no call")
    else:
        print("  no appetite, ballast stays home")
    return 0


if __name__ == "__main__":
    sys.exit(main())
