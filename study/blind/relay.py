"""The request relay: the guide author's requests to the live services, run through the raw MCP server's own code, in rounds.

    python -B study/blind/relay.py run --dir <the author's relay folder> --round <n> --missions real|simulated [--dry-run]
    python -B study/blind/relay.py verify --dir <the author's relay folder>

The author writes `round-<nnn>.requests.json` in the relay folder of its repository: {"round": n, "requests": [...]}, each request
{"tool", "arguments"} with an optional "id", the tool one of http_request, soap_request and read_mapping_release, the arguments those of
the agents' tool. `run` refuses a file of any other shape, or a round that is not the next one, and runs nothing then. Otherwise it builds
the raw MCP server in this process with the arguments the study's launch kit gives it (study/launch/make_config.py: the default allow-list
of the three legacy services, the lab's mapping release folder, the default timeout and size limit) and sends every request, in order,
through the MCP client to that server: the same tool code, sandbox, argument checks and refusals as the agents, no other tool, and nothing
edited. Each answer is the text the agent would see and whether the tool reported an error (as study/harness/mcp_client.py reads them), a
refused or failed request included. The answers go to `round-<nnn>.answers.json` beside the requests, with the round, the start and end
times, the dataset fingerprint read before and after the round (study/launch/launch.py fingerprint, read only), the Missions backend that
serves the server's Missions address before and after the round, the relay's version and hash, the lab commit and the hashes of the
server's code. `LEDGER.json` keeps every round whole: the SHA-256 of both files and a chain hash
over all rounds, so the freeze can record exactly what the author saw. A round is run once; its files are never rewritten.

`--missions` names the backend the round must reach, and the relay checks it rather than trusting it: before the first request it reads
docker ps (read only) and requires exactly one container to publish the Missions host port of the launch kit, and that container to be
the one of the named mode (the real service's container, or the federation stack's missions-stub); the fingerprint must name the same
mode. Otherwise nothing runs. Both readings are taken again after the round and recorded with the answers.

A run holds `relay.lock`, created exclusively in the relay folder, from the check that the round is the next one until the ledger is
written, so two runs of one folder can never both run a round; the second is refused and runs nothing. A lock left by a run that died is
not removed by the relay: the lead developer checks that no relay runs, looks at the folder (verify) and deletes the lock.

`--dry-run` checks the request file and prints the requests, and runs nothing: the lead developer reads it before the go for the round.
`verify` checks the folder against its ledger. A live round needs the stack of the scenario and the real Missions service up, the
interpreter named by STUDY_MCP_PYTHON (the `mcp` package) and the lead developer's go for that round; this script starts nothing.
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MCP = ROOT / 'study' / 'mcp'
LAUNCH = ROOT / 'study' / 'launch' / 'launch.py'
MAPPING_RELEASES = ROOT / 'federation' / 'mapping-releases'
TOOLS = ('http_request', 'soap_request', 'read_mapping_release')
LEDGER = 'LEDGER.json'
LOCK = 'relay.lock'
SERVER_CODE = ('study/mcp/raw_server.py', 'study/mcp/mcp_core.py')
COMMITTED = ('study/blind', 'study/mcp', 'study/launch', 'federation/mapping-releases')
NAME = re.compile(r'round-([0-9]{3})\.(requests|answers)\.json')


class Refused(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def requests_name(n):
    return 'round-%03d.requests.json' % n


def answers_name(n):
    return 'round-%03d.answers.json' % n


# ------------------------------------------------------------------------------------------------------------- the request file

def parse_requests(data, expected_round):
    """The requests of a round file, or Refused naming every problem. Only the shape is checked: the arguments go to the tool unchanged."""
    try:
        value = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as error:
        raise Refused('the request file is not UTF-8 JSON: %s' % error)
    problems = []
    if not isinstance(value, dict) or set(value) != {'round', 'requests'}:
        raise Refused('the request file must be an object with exactly the keys "round" and "requests"')
    if value['round'] != expected_round or isinstance(value['round'], bool):
        problems.append('"round" is %r; this file is round %d' % (value['round'], expected_round))
    items = value['requests']
    if not isinstance(items, list) or not items:
        problems.append('"requests" must be a non-empty list')
        items = []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict) or not {'tool', 'arguments'} <= set(item) or set(item) - {'tool', 'arguments', 'id'}:
            problems.append('request %d must hold "tool" and "arguments", and optionally "id", and nothing else' % i)
            continue
        if item['tool'] not in TOOLS:
            problems.append('request %d names the tool %r; the tools are %s' % (i, item['tool'], ', '.join(TOOLS)))
        if not isinstance(item['arguments'], dict):
            problems.append('request %d: "arguments" must be an object' % i)
        if 'id' in item and not isinstance(item['id'], str):
            problems.append('request %d: "id" must be a string' % i)
    if problems:
        raise Refused('the request file of round %d was not run: %s' % (expected_round, '; '.join(problems)))
    return items


# ------------------------------------------------------------------------------------------------------------------ the ledger

def read_ledger(folder):
    path = Path(folder) / LEDGER
    if not path.exists():
        return {'version': 1, 'rounds': []}
    return json.loads(path.read_text(encoding='utf-8'))


def chain(previous, requests_sha, answers_sha):
    return sha256(('%s:%s:%s' % (previous or '', requests_sha, answers_sha)).encode('ascii'))


def verify(folder):
    """The problems of a relay folder against its ledger (an empty list when it is whole)."""
    folder = Path(folder)
    problems = []
    try:
        ledger = read_ledger(folder)
    except (OSError, ValueError) as error:
        return ['%s cannot be read: %s' % (LEDGER, error)]
    previous = None
    for i, entry in enumerate(ledger.get('rounds', []), 1):
        if entry.get('round') != i:
            problems.append('the ledger\'s entry %d is round %r' % (i, entry.get('round')))
        for kind, name in (('requests', requests_name(i)), ('answers', answers_name(i))):
            path = folder / name
            if entry.get(kind, {}).get('file') != name:
                problems.append('round %d: the ledger names %r for the %s' % (i, entry.get(kind, {}).get('file'), kind))
            elif not path.is_file():
                problems.append('round %d: %s is missing' % (i, name))
            elif sha256(path.read_bytes()) != entry[kind].get('sha256'):
                problems.append('round %d: %s changed since the round' % (i, name))
        expected = chain(previous, entry.get('requests', {}).get('sha256'), entry.get('answers', {}).get('sha256'))
        if entry.get('chain') != expected:
            problems.append('round %d: the chain hash does not match' % i)
        previous = entry.get('chain')
    done = len(ledger.get('rounds', []))
    for path in sorted(folder.iterdir()) if folder.is_dir() else []:
        match = NAME.fullmatch(path.name)
        if match and int(match.group(1)) > done and not (int(match.group(1)) == done + 1 and match.group(2) == 'requests'):
            problems.append('%s is not in the ledger' % path.name)
    return problems


# ------------------------------------------------------------------------------------------------------------- the MCP session

class ServerSession:
    """The raw MCP server built in this process, reached through the MCP client. `call` returns (text, is_error), read as the harness's
    McpSession reads a tool result: the text parts joined by newlines, and the result's error flag."""

    def __init__(self, server):
        self.server = server

    def call(self, name, arguments):
        from mcp import Client

        async def run():
            async with Client(self.server) as client:
                return await client.call_tool(name, arguments)
        result = asyncio.run(run())
        text = '\n'.join(part.text for part in result.content if getattr(part, 'text', None) is not None)
        return text, bool(result.is_error)


def live_server():
    """The raw MCP server as the launch kit starts it for the scenarios that use it, and the facts recorded about it."""
    sys.path.insert(0, str(MCP))
    import mcp_core
    import raw_server
    allow = list(raw_server.DEFAULT_ALLOW)
    server = raw_server.build(allow, str(MAPPING_RELEASES), mcp_core.CallLog('relay'))
    return server, {'allow': allow, 'mappingDir': 'federation/mapping-releases', 'timeoutSeconds': mcp_core.DEFAULT_TIMEOUT_SECONDS,
                    'maxChars': mcp_core.DEFAULT_MAX_CHARS}


def live_fingerprint(missions):
    """The dataset fingerprint of the scenario's Missions backend: launch.py fingerprint (read only). Raises Refused when it fails or
    names another mode."""
    done = subprocess.run([sys.executable, '-B', str(LAUNCH), 'fingerprint', '--missions', missions], capture_output=True, text=True,
                          encoding='utf-8', cwd=str(ROOT))
    if done.returncode != 0:
        raise Refused('the dataset fingerprint could not be read: %s' % (done.stderr.strip() or 'exit %d' % done.returncode))
    value = json.loads(done.stdout)
    mode = value.get('missions') if isinstance(value, dict) else None
    if mode != missions:
        raise Refused('the dataset fingerprint names the Missions mode %r, not %r' % (mode, missions))
    return value


def launch_kit():
    """study/launch/launch.py as a module, for its names of the Missions backends (it imports only the standard library)."""
    sys.path.insert(0, str(LAUNCH.parent))
    import launch
    return launch


def docker_read(argv):
    done = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8')
    return done.returncode, (done.stdout or '').strip()


PS_FORMAT = '{{.ID}}\t{{.Names}}\t{{.Label "com.docker.compose.project"}}\t{{.Label "com.docker.compose.service"}}\t{{.Ports}}'


def serving_backend(missions, read=None):
    """The container that publishes the Missions host port, checked against the mode (see the module text); Refused otherwise."""
    kit = launch_kit()
    port = kit.MISSIONS_HOST_PORT
    code, out = (read or docker_read)(['docker', 'ps', '--no-trunc', '--format', PS_FORMAT])
    if code != 0:
        raise Refused('docker ps failed (exit %d), so the backend on port %d cannot be checked' % (code, port))
    binds = re.compile(r'(?:^|,\s*)(?:[0-9.]*|\[[0-9a-fA-F:]*\]):%d->' % port)
    serving = []
    for line in out.splitlines():
        fields = (line.split('\t') + [''] * 5)[:5]
        if binds.search(fields[4]):
            serving.append({'container': fields[0], 'name': fields[1], 'project': fields[2], 'service': fields[3], 'ports': fields[4]})
    if len(serving) != 1:
        raise Refused('%d containers publish the Missions port %d (%s); exactly one must' % (
            len(serving), port, ', '.join(s['name'] for s in serving) or 'none'))
    found = serving[0]
    if missions == 'real':
        ok = found['name'] == kit.MISSIONS_CONTAINER
        wanted = 'the real Missions service (%s)' % kit.MISSIONS_CONTAINER
    else:
        ok = found['project'] == kit.STACK_PROJECT and found['service'] == kit.SIMULATOR_SERVICE
        wanted = 'the Missions simulator (%s of %s)' % (kit.SIMULATOR_SERVICE, kit.STACK_PROJECT)
    if not ok:
        raise Refused('port %d is served by %s (compose %s/%s), not by %s' % (port, found['name'], found['project'] or '-',
                                                                          found['service'] or '-', wanted))
    return dict(found, missions=missions, port=port)


def lab_state(root=ROOT):
    """The lab commit and the hashes of the relay's and the server's code; Refused when that code or the mapping files are not committed."""
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_') or k == 'GIT_PAGER'}

    def git(*args):
        return subprocess.run(['git', *args], cwd=str(root), capture_output=True, text=True, env=env, check=True).stdout.strip()
    dirty = git('status', '--porcelain', '--', *COMMITTED)
    if dirty:
        raise Refused('the relay runs committed code only; these paths differ from the commit: %s' % ' '.join(dirty.split()))
    code = {path: sha256((Path(root) / path).read_bytes()) for path in ('study/blind/relay.py', 'study/launch/launch.py') + SERVER_CODE}
    return {'labCommit': git('rev-parse', 'HEAD'), 'code': code}


# ------------------------------------------------------------------------------------------------------------------- the round

def relay_folder(folder):
    folder = Path(folder).resolve()
    if folder == ROOT or ROOT in folder.parents:
        raise Refused('the relay folder %s is inside the lab checkout; give the relay folder of the author\'s repository' % folder)
    if not folder.is_dir():
        raise Refused('the relay folder %s does not exist' % folder)
    return folder


def pending(folder, n):
    """The bytes and requests of round n, checked against the ledger: n must be the next round and must not have been run."""
    folder = Path(folder)
    problems = verify(folder)
    if problems:
        raise Refused('the relay folder does not match its ledger: %s' % '; '.join(problems))
    done = len(read_ledger(folder)['rounds'])
    if n != done + 1:
        raise Refused('round %d is not the next round; %d round(s) were run, so the next is %d' % (n, done, done + 1))
    if (folder / answers_name(n)).exists():
        raise Refused('%s exists already; a round is run once' % answers_name(n))
    path = folder / requests_name(n)
    if not path.is_file():
        raise Refused('there is no %s in %s' % (requests_name(n), folder))
    data = path.read_bytes()
    return data, parse_requests(data, n)


class RoundLock:
    """relay.lock in the relay folder, created exclusively: held from the eligibility check until the ledger is written."""

    def __init__(self, folder, n):
        self.path = Path(folder) / LOCK
        self.text = json.dumps({'round': n, 'pid': os.getpid(), 'at': utc_now()}) + '\n'

    def __enter__(self):
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise Refused('%s exists: another relay run holds this folder, or one died; nothing was run (once no relay runs, check the '
                          'folder with verify and delete the lock)' % self.path)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(self.text)
        return self

    def __exit__(self, *exc):
        self.path.unlink()
        return False


def replace_bytes(path, data):
    temporary = path.with_name(path.name + '.partial')
    temporary.write_bytes(data)
    os.replace(temporary, path)


def run_round(folder, n, session, fingerprint, server_facts, lab, *, backend, clock=utc_now):
    """Run round n through `session` and write its answers and the ledger, holding the round lock throughout. `backend` reads the
    Missions backend that serves the requests (Refused when it is not the named one). Returns the answers record."""
    folder = Path(folder)
    with RoundLock(folder, n):
        return _run_round(folder, n, session, fingerprint, server_facts, lab, backend, clock)


def _run_round(folder, n, session, fingerprint, server_facts, lab, backend, clock):
    data, items = pending(folder, n)
    started = clock()
    serving_before = backend()
    before = fingerprint()
    answers = []
    for i, item in enumerate(items, 1):
        text, is_error = session.call(item['tool'], item['arguments'])
        answer = {'index': i}
        if 'id' in item:
            answer['id'] = item['id']
        answer.update({'tool': item['tool'], 'arguments': item['arguments'], 'isError': is_error, 'text': text})
        answers.append(answer)
    try:
        after = fingerprint()
    except Refused as error:
        after = {'error': str(error)}
    try:
        serving_after = backend()
    except Refused as error:
        serving_after = {'error': str(error)}
    record = {
        'round': n,
        'startedAt': started,
        'finishedAt': clock(),
        'relay': {'version': VERSION, 'sha256': lab['code'].get('study/blind/relay.py')},
        'lab': lab,
        'server': dict(server_facts, name='raw'),
        'requestFile': {'file': requests_name(n), 'sha256': sha256(data)},
        'fingerprint': {'before': before, 'after': after, 'same': before == after},
        'missionsBackend': {'before': serving_before, 'after': serving_after, 'same': serving_before == serving_after},
        'answers': answers,
    }
    out = json_bytes(record)
    with open(folder / answers_name(n), 'xb') as handle:  # exclusive: a round's answers are written once
        handle.write(out)
    ledger = read_ledger(folder)
    previous = ledger['rounds'][-1]['chain'] if ledger['rounds'] else None
    ledger['rounds'].append({'round': n, 'requests': {'file': requests_name(n), 'sha256': sha256(data)},
                             'answers': {'file': answers_name(n), 'sha256': sha256(out)},
                             'chain': chain(previous, sha256(data), sha256(out))})
    replace_bytes(folder / LEDGER, json_bytes(ledger))
    return record


# ------------------------------------------------------------------------------------------------------------------ the command

def main(argv=None, out=print):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run', help='run one round of the author\'s requests (needs the stack, the real Missions service and the go)')
    r.add_argument('--dir', required=True, help='the relay folder of the author\'s repository')
    r.add_argument('--round', type=int, required=True, help='the round to run: the next one')
    r.add_argument('--missions', choices=('simulated', 'real'), required=True,
                   help='the Missions backend the round must reach: checked on the Missions port, and its fingerprint is read')
    r.add_argument('--dry-run', action='store_true', help='check the request file and print the requests; run nothing')
    v = sub.add_parser('verify', help='check a relay folder against its ledger')
    v.add_argument('--dir', required=True)
    args = parser.parse_args(argv)
    try:
        folder = relay_folder(args.dir)
        if args.command == 'verify':
            problems = verify(folder)
            out(json.dumps({'rounds': len(read_ledger(folder)['rounds']), 'problems': problems}, indent=2))
            return 1 if problems else 0
        if args.dry_run:
            _, items = pending(folder, args.round)
            out('round %d: %d request(s); nothing was run' % (args.round, len(items)))
            for i, item in enumerate(items, 1):
                out('%3d  %s  %s' % (i, item['tool'], json.dumps(item['arguments'], ensure_ascii=False)))
            return 0
        lab = lab_state()
        server, facts = live_server()
        record = run_round(folder, args.round, ServerSession(server), lambda: live_fingerprint(args.missions), facts, lab,
                           backend=lambda: serving_backend(args.missions))
        out(json.dumps({'round': record['round'], 'answers': len(record['answers']),
                        'errors': sum(1 for a in record['answers'] if a['isError']),
                        'fingerprintSame': record['fingerprint']['same'],
                        'missionsBackendSame': record['missionsBackend']['same'], 'ledger': str(folder / LEDGER)}, indent=2))
        for key, what in (('fingerprint', 'the dataset fingerprint'), ('missionsBackend', 'the Missions backend')):
            if not record[key]['same']:
                print('relay.py: %s changed during the round; the answers are kept as the author will see them' % what, file=sys.stderr)
        return 0
    except Refused as error:
        print('relay.py: refused: %s' % error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
