"""The legacy-load reader of study 3: the requests that Missions, Personnel and Assets received per run and arm, descriptive only.

    python -B study/analysis3/legacy3.py --bundle <copy of the run folder> --sums <SHA256SUMS file> --bundle-checksum <sha256>
        --corpus-dir <the corpus the bundle ran> --legacy-dir <copy of the state folder's legacy-load folder> --out <new folder>
        [--run-id study-3] [--replicates 10000]

It fills the marked place of PLAN.md section 10 (Job study3_legacy_load, decisions L1 to L6 and D1 to D7). The copy of the bundle is verified
exactly as analyze3.py verifies it, and the same records count (data3.load: one record per planned run, its last attempt, the void-block
rule); the analysis itself runs without this reader. The output, legacy-load.json and legacy-load.md in --out (outside the repository, a
new folder), is descriptive and supports no confirmatory claim.

What counts as one request (L2, D5). Raw arms (alpha, beta), from each run's transcript: an http_request or soap_request that returned an
HTTP status, that timed out waiting for an answer, or whose error shows that a connection was made and the request sent (a reset, a remote
disconnect, a bad status line; counted, and reported apart). Not counted: an address the allow-list refused, a refused connection or a
name that did not resolve, and an error text the reader cannot classify (reported as unclassified). The system is the URL's port (8082
Personnel, 8083 Missions, 8084 Assets). GraphQL arms (gamma, delta, epsilon): every REQUEST line of the three adapters' request log, as
launch.py saved it (time, system, answer status; no URL and no body).

How a request is placed (L3, L5, D6). A run's window is its first transcript event to its finishedAt. A GraphQL run's requests are the
saved requests inside its window, in the session (one stack start) that covers it. A session's requests before its first window are its
initialization load, the others outside every window are unattributed, and every request within the session's clock-offset bound of a
window's start or end is counted as near a boundary. A block whose session is missing, was not saved whole, fails its file sums, has no
clock reading or an offset bound above 1 second at either end, holds a row or a document the reader cannot read, or (delta and epsilon) shows no completed Personnel snapshot read before its
first scored run (11 consecutive Personnel requests answered 200: one probe and 10 pages) is not countable, and its GraphQL runs are left
out of the per-question figures.

The figures (D4). For each system (and the three together) and arm, the mean requests per scored run of the core set, each arm the
equal-weight mean of its model x round cells, as section 4 weighs them; the ratios of federation (0.5 Apollo + 0.5 Cosmo) over GraphQL
Adapters and over Guided Direct Access, and of each arm over Direct Access. The cells are those of the planned runs, vendor errors
included, so a cell whose every run is missing empties its figure. 95 percent percentile intervals from section 4's resampling:
whole core tasks with replacement, stratified by direction, 10,000 replicates, seed 20261118. A replicate with an empty cell or a zero
denominator is unusable; with more than 1 percent unusable, or an empty cell or a zero denominator in the full sample, the figure is
reported as not estimable. Beside them: the block initialization load, a total that includes it, the unattributed requests, the requests
near a boundary and the blocks that are not countable.

Blindness. From a transcript the reader keeps only the first event's time, each tool event's tool name, the host and port of its URL and
its status or failure kind; it reads the status from the start of the result text and never keeps question, argument or answer text. With
the harness tools on, the agent read `result_id: <id>` and, for a long result, only its shape, so the reader takes the call's own text from
the run's results.jsonl by that id, reading the first 160 characters of it (the status or the failure reason) and keeping none. From
tasks.json it reads what data3.py reads. A task id is a cluster label and nothing else.
"""
import argparse
import json
import math
import re
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import data3  # noqa: E402
import stats3  # noqa: E402  (read-only: the replicate weights of section 4)

ARMS = ['alpha', 'beta', 'gamma', 'delta', 'epsilon']
RAW_ARMS = ('alpha', 'beta')
GRAPHQL_ARMS = ('gamma', 'delta', 'epsilon')
ROUTER_ARMS = ('delta', 'epsilon')
SYSTEMS = ('missions', 'personnel', 'assets')
ALL = 'all'
PORTS = {8082: 'personnel', 8083: 'missions', 8084: 'assets'}
RAW_TOOLS = ('http_request', 'soap_request')
FEDERATION = stats3.FEDERATION
RATIOS = (('federation/gamma', 'federation', 'gamma'), ('federation/beta', 'federation', 'beta'), ('beta/alpha', 'beta', 'alpha'),
          ('gamma/alpha', 'gamma', 'alpha'), ('delta/alpha', 'delta', 'alpha'), ('epsilon/alpha', 'epsilon', 'alpha'))
CLOCK_LIMIT_SECONDS = 1.0  # L5
SNAPSHOT_EXCHANGES = 11  # D6: one probe and 10 pages of personnel-v2-large-004 (1,000 people, 100 a page)
SEED = stats3.SEED
REPLICATES = stats3.REPLICATES
UNUSABLE_LIMIT = stats3.UNUSABLE_LIMIT
SCHEMA = 1  # the session folders' schema, as study/launch/launch.py writes it

STATUS = re.compile(r'^\s*\{"status": (\d{3})\b')
STORED_CHARS = 160  # of a stored result's text: enough for its status or failure reason, never kept and never its body
REASON = re.compile(r'The service did not answer: ([A-Za-z_][A-Za-z0-9_.]*)')
SANDBOX_REFUSALS = ('Address refused', 'The header ')
TIMEOUTS = {'TimeoutError', 'timeout', 'socket.timeout'}
NO_CONNECTION = {'ConnectionRefusedError', 'gaierror', 'socket.gaierror', 'herror'}
CONNECTED = {'ConnectionResetError', 'ConnectionAbortedError', 'BrokenPipeError', 'RemoteDisconnected', 'BadStatusLine', 'IncompleteRead',
             'LineTooLong', 'HTTPException'}
COUNTED_KINDS = ('status', 'timeout', 'connected')
RAW_KINDS = COUNTED_KINDS + ('refused', 'noConnection', 'unclassified')


class LegacyError(Exception):
    """An input the reader cannot read at all (a bad folder or argument); a block it cannot count is reported, not raised."""


def r6(value):
    if isinstance(value, float):
        return round(value, 6) if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: r6(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [r6(v) for v in value]
    return value


def seconds(text):
    """Seconds since the epoch of an ISO 8601 time with a zone (the harness's and launch.py's), or None."""
    try:
        moment = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment.timestamp() if moment.tzinfo else None


# ------------------------------------------------------------------------------------------------------------------ the raw arms
def unwrapped(text):
    """The scenario tool's own text from what the agent read, when the harness tools wrapped it: the `result_id: <id>` line and any
    `warning: ` lines above it removed. A result the harness stored and showed only as its shape has no status here; the full text is
    read from results.jsonl instead (see `read_transcript`)."""
    lines = text.split('\n')
    while lines and (lines[0].startswith('result_id: ') or lines[0].startswith('warning: ')):
        lines.pop(0)
    return '\n'.join(lines)


def raw_request(event, stored=None):
    """(system or None, kind) of one transcript event, or None for an event that is no raw request. Reads only the tool name, the URL's
    host and port, the error flag and the start of the result text. With the harness tools on, `stored` is the run's results.jsonl by
    result id, as (error flag, text): the full text of the call the event names (its `harness.resultId`) replaces what the agent read."""
    if event.get('kind') != 'tool' or event.get('name') not in RAW_TOOLS:
        return None
    url = (event.get('arguments') or {}).get('url')
    try:
        port = urllib.parse.urlsplit(str(url)).port
    except ValueError:
        port = None
    system = PORTS.get(port)
    text, is_error = str(event.get('text') or ''), bool(event.get('isError'))
    result_id = (event.get('harness') or {}).get('resultId') if isinstance(event.get('harness'), dict) else None
    if stored and result_id in stored:
        is_error, text = stored[result_id]
    text = unwrapped(text)
    if not is_error:
        kind = 'status' if STATUS.match(text) else 'unclassified'
    elif any(refusal in text for refusal in SANDBOX_REFUSALS):
        kind = 'refused'
    else:
        reason = REASON.search(text)
        name = reason.group(1) if reason else None
        kind = ('timeout' if name in TIMEOUTS else 'noConnection' if name in NO_CONNECTION else 'connected' if name in CONNECTED
                else 'unclassified')
    if kind in COUNTED_KINDS and system is None:
        kind = 'unclassified'  # the allow-list reaches only the three ports, so a request elsewhere cannot be placed
    return system, kind


def read_stored(path):
    """{result id: (error flag, the start of the text)} of a run's results.jsonl (the harness tools' store), or {} when there is none.
    Only the first STORED_CHARS characters of a text are kept: enough for the status at its start, never the body."""
    out = {}
    if not Path(path).is_file():
        return out
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            if line.strip():
                entry = json.loads(line)
                out[entry.get('resultId')] = (bool(entry.get('isError')), str(entry.get('text') or '')[:STORED_CHARS])
    return out


def read_transcript(path):
    """(first event's time in seconds or None, [(system, kind)] of its raw requests) of one run's transcript, read with the run's
    results.jsonl beside it when the harness tools were on."""
    first, requests = None, []
    if not Path(path).is_file():
        return None, []
    stored = read_stored(Path(path).parent / 'results.jsonl')
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if first is None:
                first = seconds(event.get('ts'))
            found = raw_request(event, stored)
            if found is not None:
                requests.append(found)
    return first, requests


def run_window(bundle, key):
    """(start, end) of a run in seconds: its first transcript event and its finishedAt; a part that cannot be read is None."""
    run_dir = Path(bundle) / 'runs' / key
    start, requests = read_transcript(run_dir / 'transcript.jsonl')
    result = json.loads((run_dir / 'result.json').read_text(encoding='utf-8'))
    return start, seconds(result.get('finishedAt')), requests


# ------------------------------------------------------------------------------------------------------------------ the sessions
def sha256_file(path):
    return data3.sha256_file(path)


def read_session(folder):
    """One session folder as launch.py wrote it: its scenario, start and end times, clock bounds, request rows and its problems (each a
    reason the session cannot be counted)."""
    folder = Path(folder)
    problems = []

    def load(name):
        path = folder / name
        if not path.is_file():
            return None
        try:
            document = json.loads(path.read_text(encoding='utf-8', errors='replace'))
        except ValueError:
            problems.append('%s cannot be read' % name)
            return None
        if not isinstance(document, dict):
            problems.append('%s cannot be read' % name)
            return None
        return document
    start, end, sums = load('start.json'), load('end.json'), load('sha256.json')
    failed = set()
    if sums is None:
        problems.append('no sha256.json')
    else:
        for name in ('start.json', 'requests.jsonl', 'end.json'):
            if (folder / name).is_file() and sums.get(name) != sha256_file(folder / name):
                problems.append('%s does not match its SHA-256 in sha256.json' % name)
                failed.add(name)
    # A document that fails its sum is not read further; every value read from the others is checked before it is used, so a malformed
    # value is a problem of its session and never stops the reader.
    start = None if 'start.json' in failed else start
    end = None if 'end.json' in failed else end
    if start is None and 'start.json' not in failed:
        problems.append('no start.json: the session was not opened at the start')
    if end is None and 'end.json' not in failed:
        problems.append('no end.json: the log was not saved at the teardown')
    times, bounds = {}, {}
    for point, name, document in (('start', 'start.json', start), ('end', 'end.json', end)):
        if document is None:
            times[point] = bounds[point] = None
            continue
        if document.get('schema') != SCHEMA:
            problems.append('%s has the schema %r, not %d' % (name, document.get('schema'), SCHEMA))
        at = document.get('at')
        times[point] = seconds(at) if isinstance(at, str) else None
        if times[point] is None:
            problems.append('%s holds no readable time' % name)
        clock = document.get('clock')
        bound = clock.get('offsetBound') if isinstance(clock, dict) else None
        if bound is None:
            problems.append('no clock reading at the %s' % point)
        elif isinstance(bound, bool) or not isinstance(bound, (int, float)) or not math.isfinite(bound) or bound < 0:
            problems.append('the clock reading at the %s is not a number of seconds (%r)' % (point, bound))
            bound = None
        elif bound > CLOCK_LIMIT_SECONDS:
            problems.append('clock offset bound %.3f s at the %s, above %.1f s' % (bound, point, CLOCK_LIMIT_SECONDS))
        bounds[point] = bound
    if end is not None:
        adapters = end.get('adapters')
        adapters = adapters if isinstance(adapters, dict) else {}
        for system in SYSTEMS:
            adapter = adapters.get(system)
            adapter = adapter if isinstance(adapter, dict) else {}
            if adapter.get('saved') is not True:
                problems.append('the %s adapter log was not saved (%s)' % (system, str(adapter.get('error') or 'absent')[:120]))
    rows = []
    requests_file = folder / 'requests.jsonl'
    if not requests_file.is_file():
        if end is not None:
            problems.append('no requests.jsonl')
    elif 'requests.jsonl' in failed:
        pass  # reported above; a file that fails its sum is not read
    else:
        for number, line in enumerate(requests_file.read_text(encoding='utf-8', errors='replace').splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                t = seconds(row['t'])
                if t is None or row['system'] not in SYSTEMS or row['kind'] not in ('request', 'response'):
                    raise ValueError(line[:80])
                rows.append((t, row['system'], row['kind'], row.get('status')))
            except (ValueError, KeyError, TypeError):
                problems.append('requests.jsonl line %d cannot be read' % number)
                break
    named = [d.get('scenario') for d in (start, end) if d is not None and isinstance(d.get('scenario'), str)]
    scenario = named[0] if named else folder.name.rsplit('-', 1)[-1]
    if len(set(named)) > 1:
        problems.append('start.json and end.json name different scenarios')
    return {'name': folder.name, 'scenario': scenario, 'start': times['start'], 'end': times['end'],
            'offset': max((b for b in bounds.values() if b is not None), default=None), 'rows': sorted(rows, key=lambda r: r[0]),
            'problems': problems}


def read_sessions(folder):
    folder = Path(folder)
    if not folder.is_dir():
        raise LegacyError('the legacy-load folder %s does not exist' % folder)
    return [read_session(path) for path in sorted(folder.iterdir()) if path.is_dir()]


def session_of(sessions, scenario, start, end):
    """The session of a scenario that covers a run window: opened before it began and, when saved, saved after it finished; the latest
    such session, as a later start of the same scenario begins a new one."""
    covering = [s for s in sessions if s['scenario'] == scenario and s['start'] is not None and s['start'] <= start
                and (s['end'] is None or end <= s['end'])]
    return max(covering, key=lambda s: s['start']) if covering else None


def snapshot_read_completed(rows, before):
    """D6: before `before`, SNAPSHOT_EXCHANGES consecutive Personnel requests each answered 200 before the next Personnel request. A
    request with no answer (a timeout) or an answer other than 200 starts the count again."""
    streak, pending = 0, False
    for t, system, kind, status in rows:
        if t >= before:
            break
        if system != 'personnel':
            continue
        if kind == 'request':
            if pending:
                streak = 0
            pending = True
            continue
        streak = streak + 1 if pending and status == 200 else 0
        pending = False
        if streak >= SNAPSHOT_EXCHANGES:
            return True
    return False


def empty_counts():
    return {system: 0 for system in SYSTEMS}


def session_load(session, windows, router):
    """The requests of one session, placed: per window (by run key), initialization, unattributed and near a boundary."""
    requests = [(t, system) for t, system, kind, _ in session['rows'] if kind == 'request']
    first = min(start for start, _ in windows.values())
    per_run = {key: empty_counts() for key in windows}
    init, unattributed = empty_counts(), empty_counts()
    bound = session['offset'] or 0.0
    edges = [edge for window in windows.values() for edge in window]
    near = 0
    for t, system in requests:
        if any(abs(t - edge) <= bound for edge in edges):
            near += 1
        home = next((key for key, (start, end) in windows.items() if start <= t <= end), None)
        if home is not None:
            per_run[home][system] += 1
        elif t < first:
            init[system] += 1
        else:
            unattributed[system] += 1
    return {'perRun': per_run, 'initialization': init, 'unattributed': unattributed, 'nearBoundary': near, 'offset': session['offset'],
            'snapshotRead': snapshot_read_completed(session['rows'], first) if router else None}


# ------------------------------------------------------------------------------------------------------------------ placing every run
def place(records, bundle, sessions):
    """Each record's requests per system (None when its block is not countable), and the facts per block and session."""
    windows, raw = {}, {}
    for record in records:
        start, end, requests = run_window(bundle, record['runKey'])
        windows[record['runKey']] = (start, end)
        raw[record['runKey']] = requests
    counts, blocks = {}, {}
    by_block = {}
    for record in records:
        by_block.setdefault(record['block'], []).append(record)
    for block, own in sorted(by_block.items()):
        arm = own[0]['arm']
        facts = {'arm': arm, 'runs': len(own), 'problems': [], 'sessions': []}
        blocks[block] = facts
        if arm in RAW_ARMS:
            for record in own:
                tally = {kind: empty_counts() for kind in RAW_KINDS}
                tally['unplaced'] = 0
                for system, kind in raw[record['runKey']]:
                    if system is None:
                        tally['unplaced'] += 1
                    else:
                        tally[kind][system] += 1
                record_counts = {system: sum(tally[kind][system] for kind in COUNTED_KINDS) for system in SYSTEMS}
                counts[record['runKey']] = {'requests': record_counts, 'raw': tally}
            facts['initialization'] = empty_counts()
            facts['unattributed'] = empty_counts()
            continue
        groups = {}
        for record in own:
            start, end = windows[record['runKey']]
            if start is None or end is None:
                facts['problems'].append('run %s has no readable window' % record['runKey'])
                continue
            session = session_of(sessions, arm, start, end)
            if session is None:
                facts['problems'].append('no saved session covers run %s' % record['runKey'])
                continue
            groups.setdefault(session['name'], (session, {}))[1][record['runKey']] = (start, end)
        init, unattributed = empty_counts(), empty_counts()
        placed = {}
        for name, (session, own_windows) in sorted(groups.items()):
            facts['problems'] += ['session %s: %s' % (name, problem) for problem in session['problems']]
            load = session_load(session, own_windows, arm in ROUTER_ARMS)
            if load['snapshotRead'] is False:
                facts['problems'].append('session %s: no completed Personnel snapshot read before the first scored run' % name)
            facts['sessions'].append({'name': name, 'offset': load['offset'], 'nearBoundary': load['nearBoundary'],
                                      'initialization': load['initialization'], 'unattributed': load['unattributed'],
                                      'snapshotRead': load['snapshotRead']})
            for system in SYSTEMS:
                init[system] += load['initialization'][system]
                unattributed[system] += load['unattributed'][system]
            placed.update(load['perRun'])
        facts['initialization'], facts['unattributed'] = init, unattributed
        facts['countable'] = not facts['problems']
        for record in own:
            counts[record['runKey']] = {'requests': placed.get(record['runKey']) if facts['countable'] else None}
    for facts in blocks.values():
        facts.setdefault('countable', not facts['problems'])
    return counts, blocks


# ------------------------------------------------------------------------------------------------------------------ the figures
def system_value(requests, system):
    return float(sum(requests.values()) if system == ALL else requests[system])


def interval(estimate, draws, replicates):
    """A figure with its 95 percent percentile interval, or not estimable: a non-finite estimate (an empty cell or a zero denominator in the
    full sample), or more than 1 percent of the replicates unusable, counted in whole replicates so that exactly 1 percent passes."""
    estimate = float(estimate)
    if not math.isfinite(estimate):
        return {'estimable': False, 'reason': 'a cell of the full sample is empty or a denominator is zero'}
    valid = draws[np.isfinite(draws)]
    if replicates - valid.size > round(UNUSABLE_LIMIT * replicates, 9):
        return {'estimable': False, 'estimate': estimate, 'usable': int(valid.size),
                'reason': 'more than 1 percent of the replicates are unusable'}
    low, high = np.percentile(valid, [2.5, 97.5])
    return {'estimable': True, 'estimate': estimate, 'low': float(low), 'high': float(high), 'usable': int(valid.size)}


def estimates(rows, counts, tasks, stratum_of, system, replicates, seed=SEED, planned=None):
    """D4: each arm's mean requests per run with its interval, and the ratios, on the same replicates. The cells are those of the planned
    runs (`planned`, vendor errors included), so a cell whose every run is missing stays a required cell and empties the figure."""
    index = {task: i for i, task in enumerate(tasks)}
    cells = {arm: sorted({(r['model'], r['row']) for r in (planned or rows) if r['arm'] == arm}, key=repr) for arm in ARMS}
    sums, totals, used = {}, {}, {}
    for arm in ARMS:
        position = {cell: j for j, cell in enumerate(cells[arm])}
        sums[arm], totals[arm] = np.zeros((len(tasks), len(position))), np.zeros((len(tasks), len(position)))
        used[arm] = 0
        for r in rows:
            requests = counts[r['runKey']]['requests']
            if r['arm'] != arm or requests is None:
                continue
            i, j = index[r['task']], position[(r['model'], r['row'])]
            sums[arm][i, j] += system_value(requests, system)
            totals[arm][i, j] += 1.0
            used[arm] += 1

    def arm_means(weights):
        out = {}
        for arm in ARMS:
            if not cells[arm]:
                out[arm] = np.full(weights.shape[0], np.nan)
                continue
            with np.errstate(invalid='ignore', divide='ignore'):
                means = (weights @ sums[arm]) / (weights @ totals[arm])
            out[arm] = means.mean(axis=1)
        out['federation'] = sum(w * out[a] for a, w in FEDERATION.items())
        return out
    full = arm_means(np.ones((1, len(tasks))))
    rng = np.random.default_rng([seed, 61, (SYSTEMS + (ALL,)).index(system)])
    stars = arm_means(stats3.stratified_weights(rng, stats3.strata_indices(tasks, stratum_of), replicates))

    arms = {}
    for arm in ARMS:
        arms[arm] = dict(interval(full[arm][0], stars[arm], replicates), runs=used[arm],
                         runsLeftOut=sum(1 for r in rows if r['arm'] == arm and counts[r['runKey']]['requests'] is None))
    ratios = {}
    for name, top, bottom in RATIOS:
        with np.errstate(invalid='ignore', divide='ignore'):
            whole = full[top][0] / full[bottom][0] if full[bottom][0] != 0 else math.nan
            draws = np.where(stars[bottom] != 0, stars[top] / np.where(stars[bottom] != 0, stars[bottom], 1.0), np.nan)
        ratios[name] = interval(whole, draws, replicates)
    return {'arms': arms, 'ratios': ratios, 'attempted': replicates}


def compute(records, strata, bundle, legacy_dir, replicates=REPLICATES, seed=SEED):
    """Every output of the reader, from the analysis's records, its strata, the bundle copy and the legacy-load folder."""
    sessions = read_sessions(legacy_dir)
    counts, blocks = place(records, bundle, sessions)
    planned = [r for r in records if r.get('set', 'core') == 'core']
    rows = [r for r in planned if r['outcome'] != 'vendor_error']
    tasks = sorted({r['task'] for r in rows})
    stratum_of = {task: strata[task]['direction'] for task in tasks}
    per_question = {system: estimates(rows, counts, tasks, stratum_of, system, replicates, seed, planned) for system in SYSTEMS + (ALL,)}
    initialization, total, unattributed, raw = {}, {}, {}, {}
    for arm in ARMS:
        own = [b for b in blocks.values() if b['arm'] == arm and b['countable']]
        runs = [r for r in records if r['arm'] == arm and counts[r['runKey']]['requests'] is not None]
        init = {s: sum(b['initialization'][s] for b in own) for s in SYSTEMS}
        loose = {s: sum(b['unattributed'][s] for b in own) for s in SYSTEMS}
        placed = {s: sum(counts[r['runKey']]['requests'][s] for r in runs) for s in SYSTEMS}
        sessions_counted = sum(len(b['sessions']) for b in own) if arm in GRAPHQL_ARMS else 0
        initialization[arm] = {'blocks': len(own), 'sessions': sessions_counted, 'requests': init,
                               'perSession': {s: init[s] / sessions_counted for s in SYSTEMS} if sessions_counted else None}
        unattributed[arm] = loose
        whole = {s: placed[s] + init[s] + loose[s] for s in SYSTEMS}
        total[arm] = {'runs': len(runs), 'requests': whole, 'perRun': {s: whole[s] / len(runs) for s in SYSTEMS} if runs else None,
                      'note': 'every request of the countable blocks: the runs, the block initialization and the unattributed ones'}
        if arm in RAW_ARMS:
            raw[arm] = {kind: {s: sum(counts[r['runKey']]['raw'][kind][s] for r in records if r['arm'] == arm) for s in SYSTEMS}
                        for kind in RAW_KINDS}
            raw[arm]['unplaced'] = sum(counts[r['runKey']]['raw']['unplaced'] for r in records if r['arm'] == arm)
    return r6({
        'schema': 1, 'tier': 'descriptive',
        'about': 'The legacy-load reader of study 3 (PLAN.md section 10): requests to Missions, Personnel and Assets per run and arm. '
                 'Descriptive only; it supports no confirmatory claim.',
        'perQuestion': per_question,
        'blockInitialization': initialization,
        'totalWithInitialization': total,
        'unattributed': unattributed,
        'nearBoundary': {block: sum(s['nearBoundary'] for s in facts['sessions']) for block, facts in sorted(blocks.items())
                         if facts['arm'] in GRAPHQL_ARMS},
        'notCountable': {block: facts['problems'] for block, facts in sorted(blocks.items()) if not facts['countable']},
        'rawArms': raw,
        'blocks': {block: {'arm': facts['arm'], 'countable': facts['countable'], 'sessions': facts['sessions']}
                   for block, facts in sorted(blocks.items())},
        'sessionsRead': len(sessions),
    })


# ------------------------------------------------------------------------------------------------------------------ the output
def tables(result):
    lines = ['# Legacy load (descriptive)', '', result['about'], '', '## Mean requests per scored run (95 percent interval)', '',
             '| System | ' + ' | '.join(data3.ARM_NAMES[a] for a in ARMS) + ' |', '| --- |' + ' --- |' * len(ARMS)]

    def cell(entry):
        if not entry.get('estimable'):
            return 'not estimable'
        return '%.2f (%.2f to %.2f)' % (entry['estimate'], entry['low'], entry['high'])
    for system in SYSTEMS + (ALL,):
        lines.append('| %s | %s |' % (system, ' | '.join(cell(result['perQuestion'][system]['arms'][a]) for a in ARMS)))
    lines += ['', '## Ratios of the means (95 percent interval)', '', '| System | ' + ' | '.join(name for name, _, _ in RATIOS) + ' |',
              '| --- |' + ' --- |' * len(RATIOS)]
    for system in SYSTEMS + (ALL,):
        lines.append('| %s | %s |' % (system, ' | '.join(cell(result['perQuestion'][system]['ratios'][name]) for name, _, _ in RATIOS)))
    lines += ['', '## Blocks that are not countable', '']
    lines += ['- %s: %s' % (block, '; '.join(problems)) for block, problems in result['notCountable'].items()] or ['- none']
    return '\n'.join(lines) + '\n'


def outside_repository(path):
    path = Path(path).resolve()
    if path == REPO or REPO in path.parents:
        raise LegacyError('the output folder must be outside the repository, not %s' % path)
    if path.exists():
        raise LegacyError('the output folder %s exists already' % path)
    return path


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--sums', required=True)
    parser.add_argument('--bundle-checksum', required=True)
    parser.add_argument('--corpus-dir', required=True)
    parser.add_argument('--legacy-dir', required=True, help="a copy of the state folder's legacy-load folder")
    parser.add_argument('--out', required=True, help='a new folder outside the repository')
    parser.add_argument('--run-id', default='study-3')
    parser.add_argument('--replicates', type=int, default=REPLICATES)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        out = outside_repository(args.out)
        _, _, _, strata, records, _, _ = data3.load(args.bundle, args.sums, args.run_id, args.bundle_checksum, args.corpus_dir)
        result = compute(records, strata, args.bundle, args.legacy_dir, args.replicates)
    except (data3.VerificationError, LegacyError) as error:
        print('STOP: %s' % error, file=sys.stderr)
        return 2
    out.mkdir(parents=True)
    with open(out / 'legacy-load.json', 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write('\n')
    with open(out / 'legacy-load.md', 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(tables(result))
    print('wrote %s and %s' % (out / 'legacy-load.json', out / 'legacy-load.md'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
