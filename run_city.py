"""Single unattended coordinator for research, risk checks and verified sync.

Muse supplies --snapshot with a fresh verified account read. Missing inputs
produce NEEDS_DATA and an empty action list; they never trigger fixture fallback.
This process produces proposals. Muse's existing session executes/verifies HTMW
orders; HANDS remains an unwired dry-run client. No orders are submitted here.
"""
from __future__ import annotations
import argparse
import contextlib
import copy
import io
import json
import math
import os
import sys
import time
from datetime import datetime,timezone
from unittest.mock import patch
import allocator
import bot_factory
import earnings_bot
import evolution
import leaderboard
import odds
import risk_warden
import rules
import scanner
import sync_bot
from market_clock import session
from storage import atomic_json,locked

HERE=os.path.dirname(os.path.abspath(__file__))
OUT=os.path.join(HERE,'output')


def load_snapshot(path,now=None,max_age=300):
    now=now or datetime.now(timezone.utc)
    with open(path) as handle: data=json.load(handle)
    if data.get('verified') is not True: raise ValueError('account snapshot is not verified')
    at=datetime.fromisoformat(data['snapshot_at'].replace('Z','+00:00'))
    if at.tzinfo is None or not 0 <= (now-at).total_seconds() <= max_age:
        raise ValueError('account snapshot is stale or has no timezone')
    for key in ('portfolio_value','buying_power','day_change_pct','start_value','peak_gain'):
        if not sync_bot.finite(data.get(key)): raise ValueError('missing verified '+key)
    if not isinstance(data.get('positions'),dict): raise ValueError('missing complete positions')
    for symbol,pos in data['positions'].items():
        if not sync_bot.finite(pos.get('qty')) or not sync_bot.finite(pos.get('entry')) or pos['entry']<=0:
            raise ValueError('missing exact quantity/entry for '+symbol)
    return data


@contextlib.contextmanager
def shared_data():
    # One provider fetch per symbol per cycle, including cached failures.
    daily,intra=scanner.fetch_daily,scanner.fetch_intraday_candles
    caches=[{},{}]
    def cached(fn,cache):
        def fetch(symbol,*args,**kwargs):
            if symbol not in cache:
                try: cache[symbol]=fn(symbol,*args,**kwargs)
                except Exception as error: cache[symbol]=error
            if isinstance(cache[symbol],Exception): raise cache[symbol]
            return cache[symbol]
        return fetch
    with patch.object(scanner,'fetch_daily',cached(daily,caches[0])),patch.object(scanner,'fetch_intraday_candles',cached(intra,caches[1])):
        yield


def close_intraday(registry,cache):
    hold={r['name']:r.get('hold_style','intraday') for r in registry['bots']}
    calls=leaderboard.load_calls()
    for bot,symbol in leaderboard.open_positions(calls):
        if hold.get(bot,'intraday')!='intraday': continue
        bars=cache.intra(symbol)
        if not bars: continue
        leaderboard.log_call(bot,symbol,'exit',bars[-1]['close'],
                             'intraday paper close before session end',bar_id=str(bars[-1]['ts']))


def run_cycle(snapshot_path,now=None):
    now=now or datetime.now(timezone.utc)
    summary={'at':now.isoformat(),'status':'NEEDS_DATA','actions':[],
             'mode':'shadow proposals; Muse session executes and verifies',
             'reported_htmw':None}
    try:
        market=session(now)
        if not market['open']:
            summary['status']='MARKET_CLOSED'
            return summary
        snapshot=load_snapshot(snapshot_path,now)
        summary['reported_htmw']={'amount':snapshot['portfolio_value'],'at':snapshot['snapshot_at']}
        with shared_data():
            scan=scanner.run_scan()
            from judge_scorecard import resolve_pending
            resolve_pending()
            # Do not mix an old cache with a fresh account. Missing held prices
            # leave the action list empty even if other names scanned successfully.
            missing=set(snapshot['positions'])-set(scan['symbols'])
            if missing: raise ValueError('held symbols missing quotes: '+','.join(sorted(missing)))
            risk_scan=copy.deepcopy(scan)
            for symbol in snapshot["positions"]:
                bars=scanner.fetch_intraday_candles(symbol)
                if not bars or not 0 <= now.timestamp()-(bars[-1]["ts"]+300) <= 1200:
                    raise ValueError("missing fresh completed intraday quote for "+symbol)
                risk_scan["symbols"][symbol]["last_close"]=bars[-1]["close"]
            decisions=rules.evaluate(snapshot,risk_scan,snapshot['day_change_pct'])
            warden=risk_warden.check(snapshot,risk_scan,snapshot['day_change_pct'])
            atomic_json(os.path.join(OUT,'rules-latest.json'),decisions)
            disagreements=risk_warden.compare(warden)
            atomic_json(os.path.join(OUT,'warden-latest.json'),{**warden,'disagreements':disagreements})
            if disagreements: raise ValueError('risk engines disagree')
            # Earnings exposure must be read from THIS snapshot, not calendar fixtures.
            earnings=earnings_bot.evaluate()
            for row in earnings:
                pos=snapshot['positions'].get(row['ticker'],{})
                row['held_qty']=pos.get('qty',0)
                row['exposure']=abs(row['held_qty']*scan['symbols'].get(row['ticker'],{}).get('last_close',0))
            scores=odds.build_odds(scan)
            budget=allocator.build_sheet(snapshot,decisions,earnings,False,odds_rows=scores)
            if not budget['agreement']: raise ValueError('budget engines disagree')
            atomic_json(os.path.join(OUT,'budget.json'),budget)
            registry=bot_factory.build_registry()
            cutoff=(market['close_at']-now).total_seconds()<=600
            with leaderboard.paper_context(account_snapshot=snapshot):
                digest=bot_factory.run_digest(registry,log_calls=not cutoff)
            if cutoff: close_intraday(registry,bot_factory.DataCache())
            with open(os.path.join(OUT,'city-digest-latest.txt'),'w') as handle: handle.write(digest+'\n')
            # These are candidates, never executions. Financial import receives no
            # proposals and no paper P&L under any code path.
            # A long scan cannot turn an expired account read into an action list.
            load_snapshot(snapshot_path, datetime.now(timezone.utc))
            from judge_scorecard import log_decision
            for candidate in decisions["buy_candidates"]:
                log_decision("JUDGE", candidate["symbol"], "buy", candidate["last_close"],
                             "blocked" if candidate["blocked"] else "approved",
                             reason="; ".join(candidate["blocked_reasons"]), bar_id=market["date"])
            summary.update(status='CLOSING_INTRADAY_PAPER' if cutoff else 'READY',
                           actions=[] if cutoff else [c for c in decisions['buy_candidates'] if not c['blocked'] and budget['per_name'].get(c['symbol'],{}).get('budget',0)>0],
                           budget=budget,coverage=len(scan['symbols']))
        # Same evidence cannot cause multiple seasons; no automatic deletion of JUDGE.
        with contextlib.redirect_stdout(io.StringIO()): evolution.run_seasons(1)
    except Exception as error:
        summary.update(status='NEEDS_DATA',actions=[],error=str(error))
    finally:
        atomic_json(os.path.join(OUT,'city-status.json'),summary)
    return summary


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--snapshot',required=True)
    ap.add_argument('--loop',action='store_true')
    ap.add_argument('--interval',type=int,default=60)
    ap.add_argument('--sync-input',help='optional Muse verified execution file; never paper calls')
    ap.add_argument('--deliver',action='store_true')
    ap.add_argument('--publish-monitor',action='store_true',help='publish sanitized monitor JSON with existing GitHub host credentials')
    args=ap.parse_args(argv)
    if args.interval<30: ap.error('interval must be at least 30 seconds')
    try:
        with locked(os.path.join(OUT,'city-runner'),blocking=False):
            last_monitor_publish=0
            while True:
                summary=run_cycle(args.snapshot)
                print(json.dumps(summary),flush=True)
                # A publication failure cannot stop risk checks or verified
                # COURIER delivery. Export errors never erase the last snapshot.
                try:
                    from monitor_data import export_snapshot
                    export_snapshot()
                    if args.publish_monitor and time.monotonic()-last_monitor_publish>=300:
                        from monitor_publish import publish
                        print(json.dumps(publish()),flush=True)
                        last_monitor_publish=time.monotonic()
                except Exception as error:
                    # Avoid echoing HTTP request bodies, auth or account fields.
                    print(json.dumps({'monitor':'publication unavailable','error_type':type(error).__name__}),flush=True)
                if args.sync_input or args.deliver:
                    params=(['--input',args.sync_input] if args.sync_input else [])+(['--deliver'] if args.deliver else [])
                    sync_bot.main(params)
                if not args.loop: return 0 if summary['status']!='NEEDS_DATA' else 2
                time.sleep(args.interval)
    except BlockingIOError:
        print('Another city coordinator holds the lock; no second writer started.')
        return 2
    except KeyboardInterrupt:
        return 0

if __name__=='__main__': sys.exit(main())
