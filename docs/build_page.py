#!/usr/bin/env python3
"""Build the monitor shell and sanitized telemetry; no network/account writes."""
from pathlib import Path
import sys
import html
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from monitor_data import export_snapshot

def main():
    data = export_snapshot()
    shell = (ROOT / 'docs/monitor.html').read_text()
    fallback = ''.join('<li>' + html.escape(b['name']) + '</li>' for b in data['bots'])
    (ROOT / 'docs/index.html').write_text(shell.replace('<!-- NOSCRIPT_BOTS -->', fallback))
    print(f"Built monitor: {len(data['bots'])} bots; heartbeat: {data['runtime']['status']}")

if __name__ == '__main__':
    main()
