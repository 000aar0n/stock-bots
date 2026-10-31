"""sync_bot.py - COURIER. Tracker update packets, deduped by order ID.

COURIER carries packets to the tracker. Input is a JSON file a
session fills with VERIFIED Order History data:

  {"orders": [{"order_id", "date", "ticker", "side", "qty", "price",
               "fee", "status", "reasoning",
               "portfolio_value", "cash", "buying_power", "loan",
               "holdings"}, ...]}

A top level "post_trade" dict with any of those snapshot fields is
applied to every order that does not carry its own. COURIER builds
one packet per order, skips order IDs already in the seen file, and
writes the new packets to output/tracker-packet-latest.json. It
never talks to HTMW and never invents a field: missing values stay
null and are listed as missing.

Run: python3 sync_bot.py --input <orders.json>
     [--seen-file output/seen-orders.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIELDS = ["order_id", "date", "ticker", "side", "qty", "price", "fee",
          "status", "reasoning", "portfolio_value", "cash",
          "buying_power", "loan", "holdings"]


def load_seen(path):
    if os.path.exists(path):
        with open(path) as f:
            return set(json.load(f))
    return set()


def save_seen(path, seen):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(sorted(seen), f, indent=1)


def build_packets(payload, seen):
    post = payload.get("post_trade", {})
    packets, dupes, incomplete = [], [], []
    for raw in payload.get("orders", []):
        merged = {**post, **raw}
        pkt = {k: merged.get(k) for k in FIELDS}
        oid = pkt["order_id"]
        if oid is None:
            incomplete.append("(order with no order_id)")
            continue
        if oid in seen:
            dupes.append(oid)
            continue
        missing = [k for k in FIELDS if pkt[k] is None]
        packets.append(pkt)
        if missing:
            incomplete.append(f"{oid}: missing {', '.join(missing)}")
        seen.add(oid)
    return packets, dupes, incomplete


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--seen-file",
                    default=os.path.join(HERE, "output", "seen-orders.json"))
    args = ap.parse_args(argv)
    with open(args.input) as f:
        payload = json.load(f)
    seen = load_seen(args.seen_file)
    packets, dupes, incomplete = build_packets(payload, seen)
    save_seen(args.seen_file, seen)
    out = os.path.join(HERE, "output", "tracker-packet-latest.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(packets, f, indent=1)
    print("COURIER - tracker update packets")
    for p in packets:
        print(f"  NEW {p['order_id']}: {p['side']} {p['qty']} {p['ticker']} "
              f"@ {p['price']} ({p['status']})")
    for d in dupes:
        print(f"  DUPE skipped (already seen): {d}")
    for i in incomplete:
        print(f"  INCOMPLETE: {i}")
    print(f"  {len(packets)} new packet(s), {len(dupes)} duplicate(s), "
          f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
