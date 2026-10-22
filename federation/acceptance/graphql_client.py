"""The GraphQL client of the router-neutral acceptance suite: one POST that keeps the HTTP status, a wait for an endpoint and the codes of an errors list.

Standard library only. Nothing here knows a router.
"""
import json
import time
import urllib.error
import urllib.request


def post(url, query, variables=None, timeout=60):
    """One GraphQL POST. Returns (HTTP status, parsed JSON body or None, seconds). A 4xx or 5xx is returned, not raised."""
    body = json.dumps({'query': query, 'variables': variables or {}}).encode('utf-8')
    request = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    try:
        parsed = json.loads(raw.decode('utf-8'))
    except ValueError:
        parsed = None
    return status, parsed, time.monotonic() - started


def wait_for_graphql(url, seconds=90):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            status, body, _ = post(url, '{ __typename }', timeout=5)
            if status == 200 and body and 'data' in body:
                return
        except (urllib.error.URLError, OSError) as error:
            last = error
        time.sleep(1)
    raise RuntimeError('Nothing answered GraphQL at ' + url + ': ' + str(last))


def codes(body):
    return [error.get('extensions', {}).get('code') for error in (body or {}).get('errors', [])]
