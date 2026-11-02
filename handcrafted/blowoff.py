"""blowoff.py - BLOWOFF. RSI blowoff fade, whole universe.

A name runs 12% or more in 10 sessions with RSI printing 74 or
higher in the last 3 sessions, then cracks: a red day that closes
under the prior session's low, the first lower low of the run.
Short the crack, not the top. Cover at +4% against or on a new
20 session closing high, which means the blowoff resumed and
the fade was wrong. News unverified on every short; a human
clears shorts before anyone acts.

Run: python3 handcrafted/blowoff.py [--log-calls]
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner, ta

BOT = "BLOWOFF"
FLAG = "news unverified: BLOWOFF cannot check for fresh fundamental news"
RSI_HOT = 74.0
RUN_MIN = 12.0
STOP_PCT = 4.0


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
    print("BLOWOFF - RSI blowoff fades over the wide universe")
    hits = 0
    for sym in universe():
        try:
            candles = scanner.fetch_daily(sym)
        except Exception:  # noqa: BLE001
            continue
        if len(candles) < 40:
            continue
        closes = [c["close"] for c in candles]
        last = closes[-1]
        if sym in op:
            against = scanner.pct(last, op[sym]["entry_price"])
            if against >= STOP_PCT or last > max(closes[-21:-1]):
                print(f"  CALL: EXIT short {sym} @ ${last:.2f} (cover: stop or blowoff resumed)")
                if log: log(BOT, sym, "exit", last, "BLOWOFF cover")
            continue
        rsi_path = [ta.rsi(closes[:-2]), ta.rsi(closes[:-1]), ta.rsi(closes)]
        hot = any(r is not None and r >= RSI_HOT for r in rsi_path)
        run = scanner.pct(last, closes[-11])
        if (hot and run >= RUN_MIN and last < candles[-1]["open"]
                and last < candles[-2]["low"]):
            hits += 1
            print(f"  CALL: SHORT {sym} @ ${last:.2f} (ran {run:.1f}% in 10d, RSI peaked {max(r for r in rsi_path if r):.0f}, first lower low)  [{FLAG}]")
            if log: log(BOT, sym, "short", last, f"BLOWOFF fade on the first crack after an RSI blowoff; {FLAG}")
    if not hits:
        print("  no blowoff cracking today, no calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
