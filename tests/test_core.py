"""Regression tests use synthetic prices/orders only; no network or account writes."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import pytest
import allocator
import arena
import backtester
import bot_factory
import bot_runtime
import evolution
import leaderboard as board
import market_clock
import run_city
import scanner
import sync_bot as courier
import ta

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(scanner.SESSION,'get',Mock(side_effect=AssertionError('network prohibited in tests')))


def call(side,price,at='2026-10-26T15:00:00Z',**extra):
    return dict(bot='BOT',ticker='XYZ',side=side,entry_price=price,ts=at,source='live',**extra)


def order(**extra):
    return dict(order_id='1234567',date='2026-10-26T15:00:00Z',ticker='XYZ',side='buy',qty=10,price=100.,fee=10.,amount=-1010.,status='Filled',verified=True,**extra)


def test_orphan_exits_have_no_profit_or_eligibility():
    s=board.compute_standings([call('exit',100) for _ in range(50)],lambda _:90)['BOT']
    assert s['calls']==0 and s['pnl']==0 and s['wins']==0


def test_duplicates_do_not_multiply_a_completed_trade():
    entry=call('buy',100)
    exit=call('exit',110,'2026-10-26T16:00:00Z')
    s=board.compute_standings([entry,entry,exit,exit],lambda _:200)['BOT']
    assert s['calls']==1 and s['pnl']==pytest.approx(969.5)
    assert s['open_pnl']==0


def test_short_scoring_and_open_profit_separate():
    s=board.compute_standings([call('short',100),call('exit',90,'2026-10-26T16:00:00Z')],lambda _:90)['BOT']
    assert s['pnl']==pytest.approx(970.5)
    s=board.compute_standings([call('buy',100)],lambda _:110)['BOT']
    assert s['calls']==0 and s['pnl']==0 and s['open_pnl']>0


def test_append_dedupes_and_sources_do_not_close_each_other(tmp_path):
    p=str(tmp_path/'calls.jsonl')
    assert board.log_call('B','XYZ','buy',100,'signal',path=p,bar_id='bar1')
    assert board.log_call('B','XYZ','buy',100,'again',path=p,bar_id='bar1') is None
    assert board.log_call('B','XYZ','exit',110,'arena',source='backtest',path=p) is None
    assert board.log_call('B','XYZ','exit',110,'close',path=p,bar_id='bar2')
    assert board.log_call('B','XYZ','exit',110,'repeat',path=p,bar_id='bar2') is None
    assert len(board.load_calls(p))==2


def test_context_separates_replay_state(tmp_path):
    live=str(tmp_path/'live.jsonl'); replay=str(tmp_path/'replay.jsonl')
    board.log_call('B','XYZ','buy',100,'live',path=live)
    with board.paper_context(path=replay,source='backtest',ts='2020-01-02T16:00:00-05:00'):
        assert board.load_calls()==[]
        board.log_call('B','XYZ','buy',80,'historical')
        assert board.load_calls()[0]['source']=='backtest'
    assert len(board.load_calls(live))==1


@pytest.mark.parametrize('change',[{'status':'pending'}, {'price':None}, {'qty':0}, {'fee':None}, {'date':'2026-10-26'}, {'verified':False}, {'order_id':'SAMPLE-1'}, {'amount':-999}])
def test_courier_rejects_unverified_or_incomplete(change):
    raw=order();raw.update(change);seen={}
    packets,dupes,errors=courier.build_packets({'orders':[raw]},seen)
    assert not packets and errors and seen=={}


def test_build_does_not_ack_and_corrected_fill_survives():
    seen={};raw=order();raw['status']='pending'
    assert not courier.build_packets({'orders':[raw]},seen)[0]
    assert courier.build_packets({'orders':[order()]},seen)[0]
    assert seen=={}


def test_courier_conflicting_actual_ids_rejected():
    a=order();b=order();b.update(qty=11,amount=-1110)
    packets,_,errors=courier.build_packets({'orders':[a,b]}, {})
    assert not packets and 'conflicts' in errors[0]


def saved_state(p):
    return {'transactions':courier.tracker_payload([p])['transactions']}


def test_delivery_ack_only_after_state_verification():
    p=courier.build_packets({'orders':[order()]},{})[0][0]
    out={'orders':{p['order_id']:p},'report':None};seen={}
    def bad(url,key,path,body=None):
        return {'ok':True,'receipt':'receipt-1'} if path=='/api/import' else {'transactions':[]}
    with pytest.raises(ValueError): courier.deliver(out,seen,'https://example.test','not-real',bad)
    assert not seen and out['orders']
    def good(url,key,path,body=None):
        return {'ok':True,'receipt':'receipt-1'} if path=='/api/import' else saved_state(p)
    assert courier.deliver(out,seen,'https://example.test','not-real',good)['receipt']=='receipt-1'
    assert seen[p['order_id']]['receipt']=='receipt-1'
    assert courier.build_packets({'orders':[order()]},seen)[1]==[p['order_id']]


def test_courier_mismatched_persisted_fill_not_acked():
    p=courier.build_packets({'orders':[order()]},{})[0][0]
    state=saved_state(p);state['transactions'][0]['price']=101
    with pytest.raises(ValueError): courier.verify_state(state,[p])


def test_report_is_confirmed_and_no_balance_override():
    report={'verified':True,'portfolio_value':12345.,'snapshot_at':'2026-10-26T16:01:00Z','cash':99999,'loan':100}
    payload=courier.tracker_payload([],report)
    assert payload['portfolioValue']==12345
    assert not {'cashBalance','startingBalance','loan'} & payload.keys()
    with pytest.raises(ValueError): courier.tracker_payload([],dict(report,verified=False))


def test_arena_isolation_next_open_and_patch_restoration(tmp_path,monkeypatch):
    (tmp_path/'handcrafted').mkdir()
    (tmp_path/'handcrafted'/'roster.json').write_text(json.dumps([{'name':'DEMO','file':'demo.py','timeframe':'daily'}]))
    (tmp_path/'handcrafted'/'demo.py').write_text('''import scanner, leaderboard
BOT='DEMO'
def main(argv):
    rows=scanner.fetch_daily('XYZ')
    assert rows[-1]['date'] <= leaderboard.PAPER_CONTEXT.get()['ts'][:10]
    try:
        scanner.fetch_intraday_candles('XYZ')
        raise AssertionError('current intraday leaked')
    except RuntimeError: pass
    opened=leaderboard.open_positions(leaderboard.load_calls())
    leaderboard.log_call(BOT,'XYZ','exit' if opened else 'buy',rows[-1]['close'],'synthetic')
''')
    candles=[{'date':f'2026-10-{d:02}', 'open':o,'close':c} for d,o,c in [(26,100,110),(27,150,140),(28,80,90)]]
    daily=lambda _:candles
    intraday=Mock(side_effect=AssertionError('real intraday used'))
    monkeypatch.setattr(arena,'HERE',str(tmp_path))
    monkeypatch.setattr(scanner,'fetch_daily',daily)
    monkeypatch.setattr(scanner,'fetch_intraday_candles',intraday)
    assert arena.run_arena(3,['DEMO'])==0
    assert scanner.fetch_daily is daily and scanner.fetch_intraday_candles is intraday
    intraday.assert_not_called()
    files=list((tmp_path/'output'/'arena-runs').glob('*/calls.jsonl'))
    rows=board.load_calls(str(files[0]),source='backtest')
    assert [r['entry_price'] for r in rows]==[150,80]
    assert rows[0]['ts'].startswith('2026-10-27T09:30')


def test_backtest_cannot_fill_at_signal_close(monkeypatch):
    monkeypatch.setattr(backtester,'WARMUP',0)
    monkeypatch.setattr(ta,'analyze',lambda _: {'turning_up':True})
    bars=[{'date':'2026-10-26','open':100,'close':100}, {'date':'2026-10-27','open':150,'close':140}]
    r=backtester.backtest_symbol('XYZ',bars,0)
    assert r['open_position'] is True and r['trades']==0 and r['final_equity']<10000


def test_raw_alerts_cannot_breed():
    _,st,_=evolution.pick_standings([call('exit',100) for _ in range(100)])
    assert st['_ranked_calls']==0
    reg={'bots':[{'name':'BOT','kind':'watcher','ranked':True}]}
    assert evolution.eligible_bots(reg,st)==([],[],[])


def test_arena_cannot_breed_production():
    rows=[]
    for i in range(25):
        rows.extend([call('buy',100,id=f'a{i}'),call('exit',110,id=f'b{i}')])
    for r in rows: r['source']='backtest'
    mode,st,_=evolution.pick_standings(rows)
    assert mode=='live' and st['_ranked_calls']==0


def test_mutated_threshold_changes_executed_signal(monkeypatch):
    monkeypatch.setattr(ta,'analyze',lambda _: {'rsi14':34,'patterns':['hammer'],'falling_knife':False})
    a={'name':'DIP G2A','strategy':'DIP','params':{'rsi_threshold':32}}
    b=copy.deepcopy(a);b['params']['rsi_threshold']=38
    rows=[{'close':100}]
    assert bot_runtime.signal(a,rows)[0] is False
    assert bot_runtime.signal(b,rows)[0] is True


def test_market_clock_holidays_early_close_dst():
    assert market_clock.session(datetime(2026,10,31,16,tzinfo=timezone.utc))['open'] is False
    assert market_clock.session(datetime(2026,11,26,16,tzinfo=timezone.utc))['open'] is False
    assert market_clock.session(datetime(2026,11,27,18,1,tzinfo=timezone.utc))['open'] is False
    assert market_clock.session(datetime(2026,11,2,14,31,tzinfo=timezone.utc))['open'] is True


def test_missing_account_never_uses_friday_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(run_city,'OUT',str(tmp_path))
    now=datetime(2026,11,2,16,tzinfo=timezone.utc)
    result=run_city.run_cycle(str(tmp_path/'missing.json'),now)
    assert result['status']=='NEEDS_DATA' and not result['actions'] and result['reported_htmw'] is None


def test_snapshot_freshness(tmp_path):
    data={'verified':True,'snapshot_at':'2026-10-26T15:00:00Z','portfolio_value':100000.,'buying_power':20000.,'day_change_pct':0.,'positions':{},'start_value':100000.,'peak_gain':0.}
    p=tmp_path/'snapshot.json';p.write_text(json.dumps(data))
    with pytest.raises(ValueError): run_city.load_snapshot(p,datetime(2026,10,26,16,tzinfo=timezone.utc))
    assert run_city.load_snapshot(p,datetime(2026,10,26,15,1,tzinfo=timezone.utc))['verified']


def test_whole_roster_runs_with_shared_synthetic_data(tmp_path,monkeypatch):
    from datetime import timedelta
    monkeypatch.setattr(bot_factory,'REGISTRY_PATH',str(tmp_path/'bots.json'))
    monkeypatch.setattr(bot_factory,'THERMO_PATH',str(tmp_path/'thermos.json'))
    start=datetime(2025,1,1,tzinfo=timezone.utc)
    daily=[{'date':(start+timedelta(days=i)).date().isoformat(),'open':100+i*.1,'close':100+i*.1+.03,'high':100+i*.1+.2,'low':100+i*.1-.2,'volume':1000000} for i in range(300)]
    intra=[{**daily[-1],'ts':1793629800+i*300,'date':'2026-11-02T15:00:00+00:00','close':130+i*.001} for i in range(78)]
    monkeypatch.setattr(scanner,'fetch_daily',lambda _:copy.deepcopy(daily))
    monkeypatch.setattr(scanner,'fetch_intraday_candles',lambda _:copy.deepcopy(intra))
    registry=bot_factory.build_registry()
    assert registry['count']==802
    with board.paper_context(path=str(tmp_path/'calls.jsonl'),output_dir=str(tmp_path)):
        digest=bot_factory.run_digest(registry,log_calls=False)
    failures=[line for line in digest.splitlines() if 'STOOD DOWN' in line]
    assert failures==[], failures
    assert digest.count(': module executed')==100


def test_unchanged_evidence_does_not_create_new_seasons(tmp_path,monkeypatch):
    monkeypatch.setattr(evolution,'FITNESS_PATH',str(tmp_path/'fitness.json'))
    monkeypatch.setattr(evolution,'REGISTRY_PATH',str(tmp_path/'bots.json'))
    monkeypatch.setattr(evolution,'THERMO_PATH',str(tmp_path/'thermos.json'))
    (tmp_path/'bots.json').write_text(json.dumps({'bots':[]}))
    monkeypatch.setattr(evolution,'load_calls_for_season',lambda:[])
    monkeypatch.setattr(evolution,'judge_review',lambda **kwargs:None)
    evolution.run_seasons(3)
    evolution.run_seasons(3)
    result=json.loads((tmp_path/'fitness.json').read_text())
    assert len(result['seasons'])==1 and result['optimized'] is False


def test_malformed_batch_blocks_delivery_without_changing_acks(tmp_path,monkeypatch):
    monkeypatch.setattr(courier,'HERE',str(tmp_path))
    (tmp_path/'input.json').write_text(json.dumps({'orders':[dict(order(),status='pending')]}))
    monkeypatch.setattr(courier,'deliver',Mock(side_effect=AssertionError('invalid input delivered')))
    ack=tmp_path/'seen.json'
    assert courier.main(['--input',str(tmp_path/'input.json'),'--seen-file',str(ack),'--outbox',str(tmp_path/'outbox.json'),'--deliver'])==2
    assert not ack.exists()


def test_unknown_risk_inputs_block_candidates():
    import rules
    snapshot={'portfolio_value':100000,'start_value':100000,'peak_gain':0,'buying_power':20000,'positions':{}}
    scan={'symbols':{'XYZ':{'last_close':100,'ta':{'turning_up':True,'falling_knife':False}}}}
    result=rules.evaluate(snapshot,scan)
    assert result['buy_candidates'][0]['blocked'] is True


def test_budget_never_allocates_unknown_score_or_failed_verification():
    snap={'portfolio_value':100000,'buying_power':50000,'positions':{}}
    decisions={'buy_candidates':[{'symbol':'XYZ','blocked':False}]}
    sheet=allocator.build_sheet(snap,decisions,[],False)
    assert sheet['per_name']=={}


def test_delivery_timeout_keeps_unacknowledged_orders():
    p=courier.build_packets({'orders':[order()]},{})[0][0]
    out={'orders':{p['order_id']:p},'report':None};seen={}
    def timeout(*args,**kwargs): raise TimeoutError('synthetic timeout')
    with pytest.raises(TimeoutError): courier.deliver(out,seen,'https://example.test','not-real',timeout)
    assert out['orders'] and seen=={}


def test_coordinator_complete_proposal_cycle(tmp_path,monkeypatch):
    import judge_scorecard
    moment=datetime(2026,11,2,16,tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return moment
    monkeypatch.setattr(run_city,'datetime',Clock)
    monkeypatch.setattr(run_city,'OUT',str(tmp_path))
    snapshot={'verified':True,'snapshot_at':moment.isoformat(),'portfolio_value':100000.,'buying_power':50000.,'day_change_pct':0.,'positions':{},'start_value':100000.,'peak_gain':0.}
    path=tmp_path/'snapshot.json';path.write_text(json.dumps(snapshot))
    scan={'symbols':{'XYZ':{'last_close':100.,'chg_5d_pct':1.,'closes_tail':[98.,99.,100.],'ta':{'turning_up':True,'falling_knife':False}}},'pairs':[]}
    monkeypatch.setattr(scanner,'run_scan',lambda:scan)
    monkeypatch.setattr(earnings_bot:=__import__('earnings_bot'),'evaluate',lambda:[])
    monkeypatch.setattr(__import__('odds'),'build_odds',lambda _: [{'ticker':'XYZ','ev_score':1.}])
    monkeypatch.setattr(bot_factory,'build_registry',lambda:{'bots':[]})
    monkeypatch.setattr(bot_factory,'run_digest',lambda *args,**kwargs:'synthetic full-cycle digest')
    monkeypatch.setattr(evolution,'run_seasons',lambda _:0)
    monkeypatch.setattr(judge_scorecard,'log_decision',lambda *args,**kwargs:None)
    monkeypatch.setattr(judge_scorecard,'resolve_pending',lambda:None)
    # BOUNCER compares the exact file produced during this cycle.
    real_compare=__import__('risk_warden').compare
    monkeypatch.setattr(__import__('risk_warden'),'compare',lambda w:real_compare(w,str(tmp_path/'rules-latest.json')))
    result=run_city.run_cycle(str(path),moment)
    assert result['status']=='READY',result
    assert result['actions'][0]['symbol']=='XYZ'
    assert result['reported_htmw']['amount']==100000.
    assert json.loads((tmp_path/'city-status.json').read_text())['at']==moment.isoformat()


def test_judge_outcomes_lock_once_at_known_close(tmp_path,monkeypatch):
    import judge_scorecard as judge
    monkeypatch.setattr(judge,'OUT_DIR',str(tmp_path))
    monkeypatch.setattr(judge,'DECISIONS_PATH',str(tmp_path/'decisions.jsonl'))
    monkeypatch.setattr(judge,'OUTCOMES_PATH',str(tmp_path/'outcomes.jsonl'))
    row={'id':'one','ts':'2026-10-26T15:00:00Z','bot':'JUDGE','ticker':'XYZ','side':'buy','entry_price':100,'action':'approved'}
    Path(judge.DECISIONS_PATH).write_text(json.dumps(row)+'\n')
    judge.resolve_pending(lambda _: [{'date':'2026-10-26','close':110}])
    first=Path(judge.OUTCOMES_PATH).read_text()
    judge.resolve_pending(lambda _: [{'date':'2026-10-26','close':500}])
    assert Path(judge.OUTCOMES_PATH).read_text()==first
    assert judge.score_decisions()['approved']['pnl']==pytest.approx(969.5)
