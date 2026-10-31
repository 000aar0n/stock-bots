"""Execute registry offspring and handcrafted modules with their actual parameters."""
from __future__ import annotations
import ast
import contextlib
import importlib.util
import io
import inspect
import os
from unittest.mock import patch
import leaderboard
import scanner
import ta

HERE=os.path.dirname(os.path.abspath(__file__))
FACTORY_KINDS={'watcher','shadow','sniper','rival','strategist','specialist'}
TUNABLE_PREFIXES=('RSI_', 'RVOL_', 'LOOKBACK', 'GAP_MIN', 'RUN_MIN')


def module_for(rec,registry):
    import json
    with open(os.path.join(HERE,'handcrafted','roster.json')) as handle:
        roster={r['name']:r['file'] for r in json.load(handle)}
    by_name={b['name']:b for b in registry.get('bots',[])}
    while rec.get('parent') and rec['parent'] in by_name: rec=by_name[rec['parent']]
    return rec.get('module') or roster.get(rec['name'])


def supported(rec):
    return rec['kind'] in FACTORY_KINDS or rec['kind']=='handcrafted'


def handcrafted_params(rec,registry):
    name=module_for(rec,registry)
    if not name: return {}
    tree=ast.parse(open(os.path.join(HERE,'handcrafted',name)).read())
    params={}
    for n in tree.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            key=n.targets[0].id
            try: value=ast.literal_eval(n.value)
            except (ValueError,TypeError): continue
            if key.startswith(TUNABLE_PREFIXES) and isinstance(value,(int,float)) and not isinstance(value,bool):
                params[key]=value
    return params


def family(rec):
    text=(rec.get('strategy','')+' '+rec['name']).upper()
    for name in ['BREAKOUT','DIP','GHOST','RAIDER','ANCHOR','MOMENTUM']:
        if name in text: return name
    return 'MOMENTUM'


def signal(rec,candles):
    """Deterministic offspring kernel; every exposed parameter is consumed."""
    p=rec.get('params',{})
    d=ta.analyze(candles)
    closes=[c['close'] for c in candles]
    look=int(p.get('lookback_days',20))
    rsi=p.get('rsi_threshold',35)
    strat=family(rec)
    last=closes[-1]
    if strat in ('RAIDER','BREAKOUT'):
        hit=len(closes)>look and last>max(closes[-look-1:-1]) and (d['rel_volume'] or 0)>=1.3
    elif strat=='DIP':
        hit=d['rsi14'] is not None and d['rsi14']<=rsi and bool(set(d['patterns']) & ta.BULLISH_PATTERNS)
    elif strat=='ANCHOR':
        sma=ta.sma(closes,look)
        hit=sma and d['atr14'] and last<=sma-1.2*d['atr14'] and d['rsi14'] is not None and d['rsi14']<=rsi and last>closes[-2]
    elif strat=='GHOST':
        # A delayed-feed exploit requires observed fill mechanics; no daily proxy.
        hit=False
    else:
        sma=ta.sma(closes,look)
        hit=d['turning_up'] and sma and last>sma
    return bool(hit and not d['falling_knife']), bool(d['falling_knife'])


def run_handcrafted(rec,registry,cache,log_calls):
    filename=module_for(rec,registry)
    if not filename: return 'UNSUPPORTED: no source module'
    spec=importlib.util.spec_from_file_location('city_'+rec['name'].replace(' ','_'),os.path.join(HERE,'handcrafted',filename))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BOT=rec['name']
    if hasattr(mod,"OUT") and leaderboard.PAPER_CONTEXT.get().get("output_dir"):
        mod.OUT = os.path.join(leaderboard.PAPER_CONTEXT.get()["output_dir"],os.path.basename(mod.OUT))
    for key,value in rec.get('params',{}).items():
        if not hasattr(mod,key) or not key.startswith(TUNABLE_PREFIXES):
            raise ValueError(f'unsupported handcrafted parameter {key}')
        setattr(mod,key,value)
    allowed=set(rec.get('watchlist',[]))
    # Market benchmarks remain readable; logged trades must stay in the watchlist.
    benchmarks={'SPY','QQQ','IWM','DIA'}
    # Materialize before patching scanner: DataCache resolves its provider at call time.
    for sym in allowed|benchmarks:
        cache.daily(sym)
        cache.intra(sym)
    original_daily, original_intra = scanner.fetch_daily, scanner.fetch_intraday_candles
    daily, intra=cache.daily,cache.intra
    real_log=leaderboard.log_call
    def get_daily(sym, *args, **kwargs):
        if sym not in cache._daily: cache._daily[sym] = original_daily(sym)
        rows=daily(sym)
        if not rows: raise ValueError('no daily data')
        return rows
    def get_intra(sym, *args, **kwargs):
        if sym not in cache._intra: cache._intra[sym] = original_intra(sym)
        rows=intra(sym)
        if not rows: raise ValueError('no intraday data')
        return rows
    def guarded(bot,ticker,side,price,reason,*args,**kwargs):
        if ticker not in allowed: return None
        bars=intra(ticker)
        if not bars: return None
        # Paper entries use the latest observed intraday bar, not yesterday's close.
        return real_log(rec['name'],ticker,side,bars[-1]['close'],reason,*args,
                        bar_id=str(bars[-1]['ts']),**kwargs)
    buf=io.StringIO()
    with patch.object(scanner,'fetch_daily',get_daily),patch.object(scanner,'fetch_intraday_candles',get_intra),patch.object(leaderboard,'log_call',guarded),contextlib.redirect_stdout(buf):
        if inspect.signature(mod.main).parameters:
            mod.main(['--log-calls'] if log_calls else [])
        else:
            mod.main()
    return buf.getvalue()


def run_registered_extras(registry,cache,log_calls):
    lines=[]
    for rec in registry['bots']:
        if rec.get('benched'): continue
        try:
            if rec['kind']=='handcrafted':
                report=run_handcrafted(rec,registry,cache,log_calls)
                lines.append(f'{rec["name"]}: module executed'+(' (offspring parameters applied)' if rec.get('parent') else ''))
                if 'UNSUPPORTED' in report: lines[-1]+=' '+report
                lines.extend(rec["name"]+": "+line.strip() for line in report.splitlines() if "CALL:" in line)
            elif rec.get('parent') and supported(rec):
                for sym in rec['watchlist']:
                    rows=cache.intra(sym) if rec.get('timeframe') in ('5m','5m/daily','daily+5m') else cache.daily(sym)
                    bars=cache.intra(sym)
                    if not rows or not bars: continue
                    entry,exit_flag=signal(rec,rows)
                    own=[c for c in leaderboard.load_calls() if c['bot']==rec['name'] and c['ticker']==sym]
                    opened=next((c for c in reversed(own) if c['side'] in ('buy','short')),None) if (rec['name'],sym) in leaderboard.open_positions(own) else None
                    stop=opened and (bars[-1]['close']/opened['entry_price']-1)<=-.08
                    side='exit' if opened and (exit_flag or stop) else 'buy' if entry and not opened else None
                    if side and log_calls:
                        leaderboard.log_call(rec['name'],sym,side,bars[-1]['close'],
                                             f'offspring {family(rec)}; applied params {rec.get("params",{})}',bar_id=str(bars[-1]['ts']))
                lines.append(f'{rec["name"]}: offspring kernel executed with actual params')
        except Exception as error:
            lines.append(f'{rec["name"]}: STOOD DOWN ({type(error).__name__}: {str(error)[:160]})')
    return lines
