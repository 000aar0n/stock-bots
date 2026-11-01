"""Publish only sanitized monitor data with the host's existing GitHub token.

No tracker secret is used. No trades, balances, environment variables or repo
settings are changed. Contents API SHA acts as a lease against concurrent edits.
"""
import base64
import json
import os
import requests
from monitor_data import build_snapshot

URL = 'https://api.github.com/repos/000aar0n/stock-bots/contents/docs/data.json'


def publish(root=None, session=None, token=None):
    token = token or os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise ValueError('Monitor publication needs the host existing GH_TOKEN or GITHUB_TOKEN')
    payload = build_snapshot(**({'root': root} if root is not None else {}))
    body = json.dumps(payload, separators=(',', ':'), allow_nan=False).encode()
    client = session or requests.Session()
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    response = client.get(URL + '?ref=main', headers=headers, timeout=20, allow_redirects=False)
    if response.status_code != 200:
        raise ValueError('Monitor publication read failed (HTTP ' + str(response.status_code) + ')')
    saved = response.json()
    if not saved.get('sha'):
        raise ValueError('Monitor publication missing source SHA')
    response = client.put(URL, headers=headers, timeout=20, allow_redirects=False, json={
        'message': 'Update sanitized Bot City telemetry', 'branch': 'main', 'sha': saved['sha'],
        'content': base64.b64encode(body).decode(),
    })
    if response.status_code not in (200, 201):
        raise ValueError('Monitor publication write failed (HTTP ' + str(response.status_code) + ')')
    # Public publication is verified from the committed contents, never from a
    # successful upload alone. Pages deployment is checked by the workflow.
    verify = client.get(URL + '?ref=main', headers=headers, timeout=20, allow_redirects=False)
    if verify.status_code != 200:
        raise ValueError('Monitor publication could not be verified')
    actual = json.loads(base64.b64decode(verify.json().get('content', '')))
    if actual != payload:
        raise ValueError('Monitor publication receipt differs from saved data')
    return {'published': True, 'snapshot_at': payload['generatedAt']}


if __name__ == '__main__':
    print(json.dumps(publish()))
