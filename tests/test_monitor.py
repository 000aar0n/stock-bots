import base64
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import pytest
import monitor_data as monitor
import monitor_publish

NOW = datetime(2026, 11, 1, 13, tzinfo=timezone.utc)


@pytest.fixture
def city(tmp_path):
    (tmp_path / 'output').mkdir()
    (tmp_path / 'output/bots.json').write_text(json.dumps({'bots': [
        {'name': 'TEST', 'kind': 'watcher', 'watchlist': ['NVDA'], 'hold_style': 'intraday',
         'strategy': 'test strategy', 'fitness': {'calls': 900, 'pnl': 1000000}}
    ]}))
    return tmp_path


def write_calls(city, calls):
    (city / 'output/calls.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in calls))


def call(side, price, source='live', ts='2026-10-30T15:00:00Z'):
    return dict(bot='TEST',ticker='NVDA',side=side,entry_price=price,source=source,ts=ts)


def test_no_performance_invented_from_registry_fitness(city):
    result = monitor.build_snapshot(city, NOW)
    assert result['summary']['pnl'] is None
    assert result['summary']['completed'] == 0
    assert result['runtime'] == {'at': None, 'status': 'UNCONNECTED'}


def test_completed_shadow_only_not_arena_or_open_marks(city):
    write_calls(city, [call('buy',100), call('exit',110,ts='2026-10-30T16:00:00Z'),
                       call('buy',100,'backtest'), call('exit',200,'backtest','2026-10-30T16:00:00Z'),
                       call('buy',100,ts='2026-10-30T17:00:00Z')])
    result=monitor.build_snapshot(city,NOW)
    assert result['summary']['completed']==1
    assert result['summary']['pnl']==pytest.approx(969.5)
    assert result['bots'][0]['arenaPnl']>result['summary']['pnl']
    assert not result['bots'][0]['eligible']


def test_heartbeat_and_sensitive_data_never_refreshed_or_exported(city):
    original={'at':'2026-10-30T16:00:00Z','status':'NEEDS_DATA','actions':[{'symbol':'PRIVATE'}],
              'reported_htmw':{'amount':123456},'budget':{'private':'SECRET'},'error':'TOKEN_VALUE'}
    p=city/'output/city-status.json';p.write_text(json.dumps(original))
    result=monitor.build_snapshot(city,NOW)
    assert result['runtime']['at']=='2026-10-30T16:00:00+00:00'
    assert result['generatedAt']==NOW.isoformat()
    assert json.loads(p.read_text())==original
    assert not any(s in json.dumps(result) for s in ['PRIVATE','SECRET','TOKEN_VALUE','123456','reported_htmw','budget'])


def test_corrupt_call_log_leaves_explicit_gap(city):
    (city/'output/calls.jsonl').write_text('not json\n')
    data=monitor.build_snapshot(city,NOW)
    assert data['warnings'] and data['summary']['pnl'] is None


def test_duplicate_registry_names_rejected(city):
    p=city/'output/bots.json';d=json.loads(p.read_text());d['bots']*=2;p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='duplicate'):monitor.build_snapshot(city,NOW)


def test_future_heartbeat_cannot_claim_runtime(city):
    (city/'output/city-status.json').write_text(json.dumps({'at':'2027-01-01T00:00:00Z','status':'READY'}))
    data=monitor.build_snapshot(city,NOW)
    assert data['runtime']['at'] is None and data['warnings']


def test_publisher_targets_only_allowlisted_public_file(city,monkeypatch):
    payload=monitor.build_snapshot(city,NOW)
    monkeypatch.setattr(monitor_publish,'build_snapshot',lambda **_:copy.deepcopy(payload))
    client=Mock();client.get.side_effect=[Mock(status_code=200,json=lambda:{'sha':'source-sha'}),Mock(status_code=200,json=lambda:{'content':base64.b64encode(json.dumps(payload).encode()).decode()})]
    client.put.return_value=Mock(status_code=200)
    assert monitor_publish.publish(root=city,session=client,token='test-token')['published']
    for invocation in [*client.get.call_args_list,*client.put.call_args_list]:
        assert invocation.args[0].startswith(monitor_publish.URL)
        assert invocation.kwargs['allow_redirects'] is False
    body=client.put.call_args.kwargs['json']
    assert body['sha']=='source-sha' and body['branch']=='main'
    assert 'test-token' not in json.dumps(body)


def test_publisher_refuses_failed_receipt(city,monkeypatch):
    monkeypatch.setattr(monitor_publish,'build_snapshot',lambda **_:monitor.build_snapshot(city,NOW))
    client=Mock();client.get.side_effect=[Mock(status_code=200,json=lambda:{'sha':'source-sha'}),Mock(status_code=200,json=lambda:{'content':'e30='})]
    client.put.return_value=Mock(status_code=200)
    with pytest.raises(ValueError,match='differs'):monitor_publish.publish(root=city,session=client,token='test-token')


def test_real_registry_complete_and_deterministic():
    a=monitor.build_snapshot(now=NOW);b=monitor.build_snapshot(now=NOW)
    assert a==b
    assert len(a['bots'])==len(json.loads((monitor.ROOT/'output/bots.json').read_text())['bots']) and len(a['districts'])==13
    assert sum(d['count'] for d in a['districts'])==len(a['bots'])
    assert a['summary']['symbols']==len({t for b in a['bots'] for t in b['tickers']})
