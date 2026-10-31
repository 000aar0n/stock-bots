"""THE ARENA: isolated daily replay with next-session-open paper fills.

Each run has its own append-only log. Bots see only daily bars through the
replay close; historical intraday data is unavailable and fails closed.
Pending signals fill at the following session open, never the signal close.
No arena run can read or write the live paper log or influence live eligibility.
"""
from __future__ import annotations
import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo
from unittest.mock import patch
import leaderboard
import scanner

HERE=os.path.dirname(os.path.abspath(__file__))


def load_roster():
    with open(os.path.join(HERE,'handcrafted','roster.json')) as handle:
        return json.load(handle)


class Replay:
    def __init__(self, fetch=None):
        self.cache={}
        self.cutoff=None
        self.fetch=fetch or scanner.fetch_daily

    def full(self,sym):
        if sym not in self.cache: self.cache[sym]=self.fetch(sym)
        return self.cache[sym]

    def daily(self,sym):
        return [c for c in self.full(sym) if self.cutoff is None or c['date']<=self.cutoff]

    def intraday(self,*args,**kwargs):
        raise RuntimeError('historical intraday tape unavailable; replay stands down')


def run_arena(days,bot_names):
    if days<=0: raise ValueError('days must be positive')
    roster={e['name']:e for e in load_roster()}
    names=bot_names or list(roster)
    if set(names)-set(roster): raise ValueError('unknown handcrafted bot')
    replay=Replay()
    dates=[c['date'] for c in replay.full('SPY')][-days:]
    if not dates: raise ValueError('no historical sessions')
    run_id=str(uuid.uuid4())
    log_path=os.path.join(HERE,'output','arena-runs',run_id,'calls.jsonl')
    os.makedirs(os.path.dirname(log_path),exist_ok=True)
    pending={}
    real_log=leaderboard.log_call
    errors=[]
    written=0

    def queue(bot,ticker,side,price,reason,cause='',**kwargs):
        # Price is a signal observation; it is NOT an executable fill.
        pending[(bot,ticker)]={'bot':bot,'ticker':ticker,'side':side,
                              'reason':reason,'cause':cause,'signal_at':replay.cutoff}

    def fill(day):
        nonlocal written
        for key,order in list(pending.items()):
            bar=next((c for c in replay.full(order['ticker']) if c['date']==day),None)
            if bar is None: continue  # do not invent missing prices
            if day<=order['signal_at']: continue
            at=datetime.combine(datetime.fromisoformat(day).date(),time(9,30),ZoneInfo('America/New_York')).isoformat()
            row=real_log(order['bot'],order['ticker'],order['side'],bar['open'],
                         order['reason'],cause=order['cause'],source='backtest',
                         path=log_path,ts=at,bar_id=order['signal_at'])
            written+=int(row is not None)
            del pending[key]

    # All patches restore even if data loading/import/bot execution fails.
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(scanner,'fetch_daily',replay.daily))
        stack.enter_context(patch.object(scanner,'fetch_intraday_candles',replay.intraday))
        stack.enter_context(patch.object(leaderboard,'log_call',queue))
        for day in dates:
            replay.cutoff=day
            fill(day)
            at=day+'T16:00:00'+datetime.fromisoformat(day+'T16:00:00').replace(tzinfo=ZoneInfo('America/New_York')).strftime('%z')
            with leaderboard.paper_context(source='backtest',path=log_path,ts=at,bar_id=day):
                for name in names:
                    entry=roster[name]
                    # Calendar-dependent and intraday bots need actual point-in-time
                    # data. No present-day substitute is permitted in this replay.
                    if any(x in entry.get('timeframe','').lower() for x in ('5m','intraday')):
                        errors.append({'bot':name,'day':day,'error':'historical intraday tape unavailable'})
                        continue
                    spec=importlib.util.spec_from_file_location('arena_'+entry['file'][:-3],os.path.join(HERE,'handcrafted',entry['file']))
                    mod=importlib.util.module_from_spec(spec)
                    try:
                        spec.loader.exec_module(mod)
                        with contextlib.redirect_stdout(io.StringIO()): mod.main(['--log-calls'])
                    except Exception as error:
                        errors.append({'bot':name,'day':day,'error':type(error).__name__})
    from storage import atomic_json
    atomic_json(os.path.join(os.path.dirname(log_path),'manifest.json'),{
        'run_id':run_id,'from':dates[0],'to':dates[-1],'fills':written,
        'errors':errors,'pending_signals':list(pending.values()),
        'limits':['daily-only; no intraday execution simulation',
                  'current universe/survivorship; calendar knowledge not point-in-time',
                  'research only; not eligible for live breeding or official rank']})
    calls=leaderboard.load_calls(path=log_path,source='backtest')
    standings=leaderboard.compute_standings(calls,price_fn=lambda s:None)
    print(f'ARENA: {written} next-open paper fills; {len(errors)} bot-days stood down. Log: {log_path}')
    print(leaderboard.build_report([],{},standings))
    return 0


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--days',type=int,default=20)
    ap.add_argument('--bots',default='')
    args=ap.parse_args(argv)
    return run_arena(args.days,[n.strip().upper() for n in args.bots.split(',') if n.strip()])

if __name__=='__main__': sys.exit(main())
