"""Public, read-only telemetry. Deliberately excludes accounts, fills and secrets.

The runner's heartbeat is copied from its actual status file. Exporting or
deploying a page must never manufacture evidence that the runner is alive.
"""
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import leaderboard
from storage import atomic_json
from docs.city_model import ZONES, TICKER_ZONE, assign, city_layout, book_label, watch_str

ROOT = Path(__file__).resolve().parent


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def build_snapshot(root=ROOT, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    bots = json.loads((root / 'output/bots.json').read_text())['bots']
    if len({b['name'] for b in bots}) != len(bots):
        raise ValueError('duplicate bot names in registry')
    warnings = []
    calls = []
    try:
        calls = leaderboard.load_calls(path=str(root / 'output/calls.jsonl'), source=None)
    except (ValueError, TypeError, KeyError, OSError):
        warnings.append('Paper call history could not be verified. Performance is unavailable.')
    live, arena = leaderboard.split_sources(calls)
    try:
        standings = leaderboard.compute_standings(live, price_fn=lambda _: None)
        replay = leaderboard.compute_standings(arena, price_fn=lambda _: None)
    except (ValueError, TypeError, KeyError, OSError):
        standings, replay = {}, {}
        warnings.append('Paper performance could not be calculated from saved calls.')
    # Fitness is not a source of executions: never promote cached/arena fitness
    # into the production shadow scoreboard.
    zones = {z[0]: [] for z in ZONES}
    assigned = {}
    for i, bot in enumerate(bots):
        zone, _ = assign(bot)
        zones[zone].append((i, bot))
        assigned[i] = zone
    districts, placements = city_layout(zones)
    meta = {z[0]: z for z in ZONES}
    for d in districts:
        _, d['label'], d['sub'], d['color'] = meta[d['id']]
    rows = []
    for i, bot in enumerate(bots):
        s = standings.get(bot['name'], {})
        a = replay.get(bot['name'], {})
        count = int(s.get('calls', 0))
        pnl = s.get('pnl') if count else None
        if pnl is not None and not finite(pnl):
            raise ValueError('non-finite paper performance')
        sessions = int(s.get('sessions', 0))
        eligible = count >= leaderboard.MIN_PROVEN_CALLS and sessions >= leaderboard.MIN_PROVEN_SESSIONS
        perf = ('<div class="perf">' + str(count) + ' completed shadow trades · net $' +
                f'{pnl:+,.2f}' + '</div>') if pnl is not None else '<div class="perf">No completed shadow trades</div>'
        rows.append({
            'i': i, 'name': str(bot['name']), 'kind': str(bot['kind']),
            'hold': str(bot.get('hold_style') or 'none'), 'book': book_label(bot),
            'strat': str(bot.get('strategy') or ''), 'watch': watch_str(bot),
            'tickers': [str(t) for t in (bot.get('watchlist') or [])],
            'zone': assigned[i], 'ranked': bool(bot.get('ranked', bot['kind'] not in ('staff','thermometer'))), 'calls': count, 'pnl': pnl,
            'sessions': sessions, 'eligible': eligible,
            'state': 'benched' if bot.get('benched') else 'registered',
            'arenaCalls': int(a.get('calls', 0)),
            'arenaPnl': a.get('pnl') if a.get('calls', 0) else None,
            'perf': perf, **placements[i],
        })
    runtime = {'at': None, 'status': 'UNCONNECTED'}
    status_file = root / 'output/city-status.json'
    if status_file.exists():
        try:
            raw = json.loads(status_file.read_text())
            stamp = datetime.fromisoformat(raw['at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None or stamp > now:
                raise ValueError('invalid heartbeat')
            allowed = {'READY', 'MARKET_CLOSED', 'NEEDS_DATA', 'CLOSING_INTRADAY_PAPER'}
            runtime = {'at': stamp.isoformat(), 'status': raw['status'] if raw.get('status') in allowed else 'UNKNOWN'}
        except (ValueError, TypeError, KeyError, OSError):
            warnings.append('Runner heartbeat could not be verified.')
    tracked = [b for b in rows if b['calls']]
    judge = None
    try:
        from judge_scorecard import score_decisions
        sc = score_decisions(decisions_path=str(root/'output/judge_decisions.jsonl'),
                             outcomes_path=str(root/'output/judge_outcomes.jsonl'))
        judge = {'scored': sc['scored'], 'unscored': sc['unscored'],
                 'sessions': sc['sessions'], 'net': sc['net'] if sc['scored'] else None}
    except (ValueError, KeyError, TypeError, OSError):
        warnings.append('JUDGE decision scorecard could not be verified.')
    return {
        'schemaVersion': 1, 'generatedAt': now.isoformat(),
        'lastCallAt': max((c['ts'] for c in live), default=None),
        'runtime': runtime, 'warnings': warnings, 'judge': judge,
        'basis': 'Completed shadow round trips; $10,000 reference per strategy; modeled $10/order and 5 bps/side. Not HTMW account P/L. Strategies may overlap.',
        'evidence': {'trades': leaderboard.MIN_PROVEN_CALLS, 'sessions': leaderboard.MIN_PROVEN_SESSIONS},
        'summary': {'bots': len(rows), 'symbols': len({t for b in rows for t in b['tickers']}),
                    'completed': sum(b['calls'] for b in rows), 'ranked': len(tracked),
                    'rankable': sum(b['ranked'] for b in rows),
                    'eligible': sum(b['eligible'] and b['ranked'] for b in rows),
                    'pnl': sum(b['pnl'] for b in tracked) if tracked else None},
        'districts': districts, 'bots': rows,
    }


def export_snapshot(path=None, root=ROOT, now=None):
    payload = build_snapshot(root, now)
    atomic_json(str(path or Path(root) / 'docs/data.json'), payload, indent=None)
    return payload


if __name__ == '__main__':
    export_snapshot()
