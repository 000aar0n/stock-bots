"""COURIER: verified executed orders -> durable outbox -> receipt + state check.

--input orders.json builds packets only. --deliver sends pending packets to
TRACKER_URL using the existing MUSE_UPDATE_KEY environment variable. Credentials
are never saved. No HTMW orders, balance overrides or estimated reports are sent.
Seen means verified in tracker state, never merely generated or attempted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from storage import atomic_json, locked

HERE = os.path.dirname(os.path.abspath(__file__))
FIELDS = ['order_id', 'date', 'ticker', 'side', 'qty', 'price', 'amount',
          'fee', 'status', 'reasoning', 'legacyId']
TRACKER_ORIGIN = 'https://muse-portfolio-aaron.jauntytrout2048.chatgpt.site'
ACTIONS = {'buy':'Buy', 'sell':'Sell', 'short':'Short', 'cover':'Cover'}


def finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('missing exact execution timestamp with timezone')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    if dt > datetime.now(timezone.utc):
        raise ValueError('future execution/report timestamp')
    return dt.astimezone(timezone.utc).isoformat()


def fingerprint(packet):
    execution = {k: packet.get(k) for k in ['order_id','date','ticker','side','qty','price','amount','fee','legacyId']}
    return hashlib.sha256(json.dumps(execution, sort_keys=True, allow_nan=False).encode()).hexdigest()


def load_seen(path):
    if not os.path.exists(path):
        return {}
    with open(path) as handle:
        old = json.load(handle)
    # Old lists had no delivery evidence. Do not silently trust them as receipts.
    return old if isinstance(old, dict) else {}


def save_seen(path, seen):
    atomic_json(path, seen)


def build_packets(payload, seen):
    packets, dupes, incomplete, within, conflicts = [], [], [], {}, set()
    for raw in payload.get('orders', []):
        oid = raw.get('order_id')
        try:
            if raw.get('verified', payload.get('verified')) is not True:
                raise ValueError('source execution not explicitly verified')
            if not isinstance(oid, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}', oid):
                raise ValueError('missing actual HTMW order_id (string)')
            if oid.upper().startswith(('SAMPLE', 'TEST', 'LEGACY', 'GENERATED')):
                raise ValueError('placeholder/generated order ID rejected')
            if str(raw.get('status', '')).lower() not in ('filled', 'executed'):
                raise ValueError('not a confirmed executed fill')
            if str(raw.get('side', '')).lower() not in ACTIONS:
                raise ValueError('invalid executed side')
            if not isinstance(raw.get('ticker'), str) or not re.fullmatch(r'[A-Z0-9.^=-]{1,20}', raw['ticker']):
                raise ValueError('invalid ticker')
            for key in ['qty', 'price', 'amount', 'fee']:
                if not finite(raw.get(key)):
                    raise ValueError(f'missing/unmasked numeric {key}')
            if raw['qty'] <= 0 or raw['price'] <= 0 or raw['fee'] < 0:
                raise ValueError('invalid quantity, price or fee')
            side = raw['side'].lower()
            expected = raw['qty'] * raw['price'] * (-1 if side in ('buy','cover') else 1) - raw['fee']
            if abs(expected - raw['amount']) > .02:
                raise ValueError('signed net amount disagrees with execution fields')
            pkt = {k:raw.get(k) for k in FIELDS}
            pkt.update(date=timestamp(raw.get('date')), side=side, status='Filled')
            digest = fingerprint(pkt)
            previous = within.get(oid) or (seen.get(oid, {}).get('fingerprint') if isinstance(seen, dict) else None)
            if previous and previous != digest:
                conflicts.add(oid)
                raise ValueError('order ID conflicts with previously recorded execution')
            if previous:
                dupes.append(oid)
                continue
            within[oid] = digest
            packets.append(pkt)
        except (ValueError, TypeError) as error:
            incomplete.append(f'{oid or "(no order ID)"}: {error}')
    # No mutation of seen: only deliver() may acknowledge an order.
    return [p for p in packets if p["order_id"] not in conflicts], dupes, incomplete


def tracker_payload(packets, report=None):
    rows = []
    for p in packets:
        row = {'orderId':p['order_id'], 'date':p['date'], 'symbol':p['ticker'],
               'action':ACTIONS[p['side']], 'qty':p['qty'], 'price':p['price'],
               'amount':p['amount'], 'note':p.get('reasoning') or ''}
        if p.get('legacyId'):
            row['legacyId'] = p['legacyId']
        rows.append(row)
    result = {'transactions':rows}
    if report is not None:
        if report.get('verified') is not True or not finite(report.get('portfolio_value')):
            raise ValueError('reported HTMW snapshot must be explicitly verified')
        result.update(portfolioValue=report['portfolio_value'],
                      snapshotAt=timestamp(report.get('snapshot_at')),
                      portfolioValueSource='HTMW via Muse/COURIER')
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('tracker redirect rejected; credentials stay at configured site')


def http(url, key, path, body=None):
    from urllib.parse import urlsplit
    if url.rstrip('/') != TRACKER_ORIGIN:
        raise ValueError('credentials may only be sent to the Muse tracker origin')
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.path not in ('','/') or parts.query or parts.fragment:
        raise ValueError('TRACKER_URL must be an exact HTTPS site origin')
    headers = {'Authorization':'Bearer '+key, 'Content-Type':'application/json'}
    req = urllib.request.Request(url.rstrip('/')+path, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
        return json.load(response)


def verify_state(state, packets, report=None):
    saved = {}
    for row in state.get('transactions', []):
        if row.get('orderId'):
            if row['orderId'] in saved:
                raise ValueError('tracker contains duplicate actual order ID')
            saved[row['orderId']] = row
    for p in packets:
        row = saved.get(p['order_id'])
        if row is None:
            raise ValueError(f'missing persisted order {p["order_id"]}')
        if row.get('symbol') != p['ticker'] or row.get('action') != ACTIONS[p['side']] or timestamp(row.get('date')) != p['date']:
            raise ValueError(f'execution fields disagree for {p["order_id"]}')
        for key in ['qty','price','amount']:
            if not finite(row.get(key)) or abs(row[key]-p[key]) > 1e-8:
                raise ValueError(f'{key} disagrees for {p["order_id"]}')
    if report is not None:
        actual = state.get('account', {}).get('portfolioSnapshot', {})
        if actual.get('amount') != report['portfolio_value'] or timestamp(actual.get('at')) != timestamp(report['snapshot_at']):
            raise ValueError('reported HTMW snapshot was not verified in saved state')


def deliver(outbox, seen, url, key, request=http):
    packets = list(outbox['orders'].values())
    report = outbox.get('report')
    if not packets and report is None:
        return None
    payload = tracker_payload(packets, report)
    receipt = request(url, key, '/api/import', {'text':json.dumps(payload), 'source':'COURIER verified execution packet'})
    if receipt.get('ok') is not True or not receipt.get('receipt'):
        raise ValueError('tracker did not return an import receipt')
    state = request(url, key, '/api/state')
    verify_state(state, packets, report)
    at = datetime.now(timezone.utc).isoformat()
    for p in packets:
        seen[p['order_id']] = {'fingerprint':fingerprint(p), 'receipt':receipt['receipt'], 'verified_at':at}
    return receipt


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--input')
    ap.add_argument('--seen-file', default=os.path.join(HERE,'output','seen-orders.json'))
    ap.add_argument('--outbox', default=os.path.join(HERE,'output','courier-outbox.json'))
    ap.add_argument('--deliver', action='store_true')
    args=ap.parse_args(argv)
    with locked(args.outbox):
        seen=load_seen(args.seen_file)
        outbox={'orders':{}, 'report':None}
        if os.path.exists(args.outbox):
            with open(args.outbox) as handle: outbox=json.load(handle)
        problems=[]
        if args.input:
            with open(args.input) as handle: payload=json.load(handle)
            packets, dupes, problems=build_packets(payload, seen)
            for p in packets:
                old=outbox['orders'].get(p['order_id'])
                if old and fingerprint(old)!=fingerprint(p):
                    problems.append(f'{p["order_id"]}: conflicts with queued execution')
                else: outbox['orders'][p['order_id']]=p
            if payload.get('post_trade') is not None:
                try:
                    report=payload['post_trade']
                    tracker_payload([], report)
                    previous=outbox.get('report')
                    if previous and timestamp(report['snapshot_at']) < timestamp(previous['snapshot_at']):
                        raise ValueError('report predates queued report')
                    outbox['report']=report
                except (ValueError, TypeError, KeyError) as error:
                    problems.append(f'HTMW report: {error}')
        atomic_json(args.outbox,outbox)
        atomic_json(os.path.join(HERE,'output','tracker-packet-latest.json'), list(outbox['orders'].values()))
        if problems:
            for problem in problems: print('COURIER REQUIRES SOURCE DATA: '+problem)
            print('COURIER: delivery blocked; valid queued packets retained, no acknowledgments advanced.')
            return 2
        if args.deliver:
            key=os.environ.get('MUSE_UPDATE_KEY')
            url=os.environ.get('TRACKER_URL')
            if not key or not url:
                print('COURIER: queued; TRACKER_URL / existing MUSE_UPDATE_KEY unavailable. No delivery attempted.')
                return 2
            try:
                receipt=deliver(outbox,seen,url,key)
                if receipt:
                    # Save ack before clearing outbox; crashes retry idempotently by order ID.
                    save_seen(args.seen_file,seen)
                    outbox={'orders':{},'report':None}
                    atomic_json(args.outbox,outbox)
                    print(f'COURIER: delivery verified; receipt {receipt["receipt"]}')
            except Exception as error:
                # Never stringify HTTP requests, credentials or response bodies.
                print(f'COURIER: delivery unverified ({type(error).__name__}); durable outbox retained.')
                return 2
        for problem in problems: print('COURIER REQUIRES SOURCE DATA: '+problem)
        print(f'COURIER: {len(outbox["orders"])} pending verified execution(s); no order submission.')
        return 2 if problems else 0

if __name__=='__main__':
    sys.exit(main())
