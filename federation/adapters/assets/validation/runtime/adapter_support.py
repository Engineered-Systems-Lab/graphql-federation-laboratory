"""Helpers of the Assets adapter gates: Docker calls, a free port, a GraphQL POST and the adapter's own image build.

Everything a gate creates is disposable and uniquely named; a gate removes only what it created. Missing Docker is a failure.
"""
from pathlib import Path
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request

COMPONENT = Path(__file__).resolve().parents[2]
FEDERATION = COMPONENT.parents[1]
ROOT = FEDERATION.parent
COMPOSE_FILE = COMPONENT / 'compose.yaml'
START = COMPONENT / 'start.sh'
MAVEN_BASE = 'maven:3.9-eclipse-temurin-21@sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320'
JRE_BASE = 'eclipse-temurin:21-jre@sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef'


def bash():
    """The bash of Git for Windows when there is one (the WSL launcher on the PATH fails on every call)."""
    for candidate in ('bash', r'C:\Program Files\Git\bin\bash.exe'):
        try:
            if subprocess.run([candidate, '-c', 'echo ok'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30).stdout.strip() == b'ok':
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError('No working bash was found; the gate runs from Git Bash')


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def run(argv, env=None, timeout=300, cwd=None):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env, cwd=cwd)
    result.stdout, result.stderr = result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace')
    return result


def docker(args, timeout=300, check=True):
    result = run(['docker'] + args, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('docker ' + ' '.join(args[:3]) + ' failed: ' + (result.stderr or result.stdout)[-1500:])
    return result.stdout


def graphql(port, query, variables=None, timeout=30):
    body = json.dumps({'query': query, 'variables': variables or {}}).encode('utf-8')
    request = urllib.request.Request(f'http://127.0.0.1:{port}/graphql', data=body, headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def wait_for_graphql(port, seconds=90):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            if 'data' in graphql(port, '{ __typename }', timeout=5):
                return
        except (urllib.error.URLError, OSError, ValueError) as error:
            last = error
        time.sleep(1)
    raise RuntimeError('The adapter did not answer GraphQL on port ' + str(port) + ': ' + str(last))


REFERENCES = ('query($r: [_Any!]!) { _entities(representations: $r) { ... on AssetReference '
              '{ localRef assetId mappingOutcome resolution asset { assetId kind category name description status parentAssetId } } } }')


def reference(local_ref, asset_id, release='1.0'):
    return {'__typename': 'AssetReference', 'localRef': local_ref, 'release': release, 'assetId': asset_id,
            'mappingOutcome': 'NO_ENTRY' if asset_id is None else 'MAPPED'}
