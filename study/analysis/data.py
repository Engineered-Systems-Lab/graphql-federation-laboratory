"""Reading a study run for the analysis: verify a copy of the run folder, then load one record per agent run.

The raw run folders stay outside the repository and are read-only; the analysis reads COPIES. Before anything is read, a copy is checked
three ways: every file against the per-file sums of the archive (SHA256SUMS-*.txt, lines `<sha256> *<run>/<path>`), no file missing or
extra, and the bundle checksum recomputed from the bundle's file list the way the runner writes it (study/harness/runner.py,
write_bundle). A copy that fails any check stops the analysis.
"""
import csv
import hashlib
import json
from pathlib import Path

# The scenario of a run as the analysis names it. gamma-prime-1 ran the Gamma scenario again after the mapping lookups landed; its runs
# are kept apart from study-1's Gamma (the as-built case) under their own name.
SCENARIO_OF_RUN = {'study-1': {}, 'gamma-prime-1': {'gamma': 'gamma_prime'}}
VENDOR_FILES = ('budget-anthropic.jsonl', 'budget-openai.jsonl')
USAGE_KINDS = ('input', 'cached_read', 'cache_write', 'output')


class VerificationError(Exception):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def read_sums(sums_file, run_id):
    """The {relative path: sha256} of one run in an archive sums file."""
    sums = {}
    prefix = run_id + '/'
    for line in Path(sums_file).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        digest, name = line.split(' ', 1)
        name = name.lstrip('*')
        if name.startswith(prefix):
            sums[name[len(prefix):]] = digest
    if not sums:
        raise VerificationError('the sums file lists no file of %s' % run_id)
    return sums


def verify_copy(folder, sums_file, run_id, expected_checksum=None):
    """Check a copy of a run folder; returns the verified facts or raises VerificationError."""
    folder = Path(folder)
    sums = read_sums(sums_file, run_id)
    have = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    missing, extra = sorted(set(sums) - have), sorted(have - set(sums))
    if missing or extra:
        raise VerificationError('%s: missing %s, extra %s' % (run_id, missing[:5], extra[:5]))
    bad = [name for name in sorted(sums) if sha256_file(folder / name) != sums[name]]
    if bad:
        raise VerificationError('%s: %d files differ from the sums, first %s' % (run_id, len(bad), bad[0]))
    bundle = json.loads((folder / 'bundle.json').read_text(encoding='utf-8'))
    listed = bundle['files']
    if set(listed) != have - {'bundle.json'}:
        raise VerificationError('%s: the bundle file list does not match the folder' % run_id)
    if any(sums[name] != digest for name, digest in listed.items()):
        raise VerificationError('%s: the bundle file list disagrees with the sums' % run_id)
    checksum = hashlib.sha256(json.dumps(listed, sort_keys=True).encode('utf-8')).hexdigest()
    if checksum != bundle['checksum']:
        raise VerificationError('%s: the bundle checksum does not recompute' % run_id)
    if expected_checksum and checksum != expected_checksum:
        raise VerificationError('%s: bundle checksum %s, expected %s' % (run_id, checksum, expected_checksum))
    if bundle.get('studyRunId') != run_id or bundle.get('status') != 'complete':
        raise VerificationError('%s: the bundle is not a complete bundle of this run' % run_id)
    return {'run': run_id, 'files': len(sums), 'bundleChecksum': checksum, 'writtenAt': bundle['writtenAt'],
            'sumsFile': Path(sums_file).name, 'sumsFileSha256': sha256_file(sums_file)}


def dollars(usage, price):
    """The harness's own formula (study/harness/budget.py, dollars): USD per million tokens of each kind."""
    return sum(usage[kind] * price[kind] for kind in USAGE_KINDS) / 1_000_000


def request_log(folder):
    """One row per settled vendor request: run key, seconds and usage. Reserve and settle events pair by their sequence number."""
    rows = []
    for name in VENDOR_FILES:
        path = Path(folder) / name
        runs, seen = {}, set()
        for line in path.read_text(encoding='utf-8').splitlines():
            event = json.loads(line)
            if event['event'] == 'reserve':
                if event['seq'] in runs:
                    raise VerificationError('%s: sequence %s reserved twice' % (name, event['seq']))
                runs[event['seq']] = event['run']
            elif event['event'] == 'settle':
                if event['seq'] in seen or event['seq'] not in runs:
                    raise VerificationError('%s: sequence %s settled twice or never reserved' % (name, event['seq']))
                seen.add(event['seq'])
                rows.append({'run': runs[event['seq']], 'vendorFile': name, 'seconds': event['requestSeconds'],
                             'retry': bool(event.get('retry')), **{kind: event['usage'][kind] for kind in USAGE_KINDS}})
    return rows


def load_run(folder, run_id):
    """One record per agent run of a verified copy, in run-key order."""
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    prices = {model: entry['priceEntry'] for model, entry in manifest['models'].items()}
    with open(folder / 'scores.csv', encoding='utf-8', newline='') as handle:
        scores = {row['runKey']: row for row in csv.DictReader(handle)}
    rename = SCENARIO_OF_RUN[run_id]
    records = []
    for key in sorted(scores):
        row = scores[key]
        result = json.loads((folder / 'runs' / key / 'result.json').read_text(encoding='utf-8'))
        if result['outcome'] != row['outcome'] or result['runKey'] != key:
            raise VerificationError('%s: scores.csv and result.json disagree on %s' % (run_id, key))
        usage = {kind: int(result['usage'][kind]) for kind in USAGE_KINDS}
        score = result.get('score') or {}  # a run that did not finish or failed at the vendor has no score block
        outcome = row['outcome']
        records.append({
            'run': run_id, 'runKey': key, 'scenario': rename.get(row['scenario'], row['scenario']), 'task': row['taskId'],
            'category': row['category'], 'model': row['model'], 'trial': int(row['trial']), 'outcome': outcome,
            # The plan's outcome rules: a vendor error is missing (None) in the main analysis; everything else is right or wrong.
            'correct': None if outcome == 'error' else int(outcome == 'correct'),
            'seconds': float(result['elapsedSeconds']), 'toolCalls': int(result['toolCalls']), 'turns': int(result['turns']),
            'tokens': sum(usage.values()), 'usage': usage, 'cost': dollars(usage, prices[row['model']]),
            'submission': result.get('submission'), 'tags': row['tags'],
            'failedChecks': list(score.get('failedChecks') or []), 'honestyFailures': list(score.get('honestyFailures') or []),
        })
    return records, manifest


def load_corpus(corpus_dir):
    """{task id: (category, tags)} of the frozen corpus."""
    tasks = json.loads((Path(corpus_dir) / 'tasks.json').read_text(encoding='utf-8'))['tasks']
    return {t['id']: {'category': t['category'], 'difficulty': t.get('difficulty'), 'tags': t['tags']} for t in tasks}
