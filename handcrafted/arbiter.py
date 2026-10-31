"""arbiter.py - ARBITER. Timeframe agreement arbiter, whole universe.

WATCHER and SHADOW settled their fights by printing CONTESTED;
ARBITER trades only the fights that do not happen: a universe
name where the DAILY tape is turning_up AND the 5 MINUTE tape is
turning_up AND daily relative volume is over 1.0. Both clocks
agreeing is the whole signal. Exit when either timeframe prints
falling_knife, or the -8% rule. MOSAIC does this for NVDA alone
with a volume bar of 1.5; ARBITER runs the wide universe at 1.0
and pays for the breadth with the double agreement.

Run: python3 handcrafted/arbiter.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "ARBITER"


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
    print("ARBITER - daily and 5 minute agreement over the wide universe")
    hits = 0
    for sym in universe():
        try:
            daily = scanner.fetch_daily(sym)
            bars = scanner.fetch_intraday(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(bars) < 30:
            continue
        last = daily[-1]["close"]
        dd = ta.analyze(daily)
        ii = ta.analyze(bars)
        if sym in op:
            move = scanner.pct(last, op[sym]["entry_price"])
            if dd["falling_knife"] or ii["falling_knife"] or move <= -8.0:
                why = "a timeframe printed falling_knife" if (dd["falling_knife"] or ii["falling_knife"]) else "-8% rule"
                print(f"  CALL: EXIT {sym} @ ${last:.2f} ({why})")
                if log: log(BOT, sym, "exit", last, f"ARBITER exit: {why}")
            continue
        if (dd["turning_up"] and ii["turning_up"]
                and (dd["rel_volume"] or 0) > 1.0):
            hits += 1
            print(f"  CALL: BUY {sym} @ ${last:.2f} (both clocks agree, rel vol "
                  f"{dd['rel_volume']})")
            if log: log(BOT, sym, "buy", last, "ARBITER: daily and 5m turning_up agree")
    if not hits:
        print("  the clocks agree nowhere today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
