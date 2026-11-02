"""Compare the two derivations of corpus 2's keys: keys-a.json (derive_a.py) and keys-b.json (derive_b.py, the blind second derivation).

Decisions K3 and K4 of the Job study2_corpus_keys_b. For each of the 90 tasks of the pool, the ambiguity set and the development set:

- B's answer, scored by scoring.py against keys-a.json, must be correct;
- A's answer must equal B's under the scorer's folding (case, space, hyphen and underscore; numbers by value; lists of strings as sets;
  other lists in any order), or be one of B's declared variants;
- the declared variants of the two are compared as sets: a variant of one side is matched when it fits a variant of the other side
  (B's by its answer, A's by its checks);
- for the ambiguity set, per interpretation: the same names, each of B's interpretation answers correct under A's rubric as that
  interpretation, A's answer equal to B's answer of the same interpretation, and B's example answer and variants among its
  interpretations.

Every difference was brought to the lead developer and decided, task by task; DECIDED names them, each bound to the exact differences
and to the hashes of its task and of both keys' entries, and the comparison passes only when the differences it finds are exactly the
decided ones on those same inputs. Neither derivation is changed here: a fix is its own Job.

    python -B study/corpus2/compare_keys.py

prints one line per difference (task id, kind, detail and decision), never a question, and exits 0 only when every difference found is
decided and every decided difference is found. Standard library only.
"""
import copy
import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scoring  # noqa: E402

# Phase B as the Job record holds it (K6): the private repository's commit, the hashes of the two files, the package they came from.
B_RECORD = {
    'commit': '26131e702556a9c2edf1524e8090d850b556ce91',
    'model': 'GPT-6 Astra High, as the Codex desktop app shows it',
    'date': '2026-10-31',
    'packageSha256': '2e25f8f03ce2d5876edd0e10e94d1de2b4ad1c86f5533358555a79553b1ab679',
    'labCommit': '6c18afa638ce583dcd79125177ba9a210f5a3686',
    'sha256': {
        'derive_b.py': '1e3e568e9e98590b68c7a76c2f7bc4f945dbc6d8550c9491b997756d3f3bd7c4',
        'keys-b.json': '5e05e494fd61b31f1776991c892189c6f8da4f7296ce9d51fb5c1b19391fdb72',
        'test_derive_b.py': '108ba52c6f677b7b08038998733cdcb19210d44b4d29bc4d2b78584dfc96c1a8',
    },
}

# The inputs B hashed that the lab does not hold: the package's own manifest and README, written by study/blind/blind.py for the package
# and covered by packageSha256. dev.json is rebuilt from the lab's file (b_dev_input), and every other input must hash as the lab's file,
# both read from Git at B_RECORD['labCommit'] (the files B received), not from the lab's current files: a later fix of the lab's questions
# (the Job study2_corpus_wording) does not change what B was given.
B_PACKAGE_ONLY_INPUTS = ('MANIFEST.json', 'README.md')
B_REWRITTEN_INPUT = 'study/corpus2/dev.json'

# The differences the lead developer decided on 2026-10-31, one at a time (K4). Each decision is bound to what was decided: the exact
# differences found (kind and detail) and the SHA-256 of the task as its file holds it (question, schema and the rest) and of both keys'
# entries (canonical JSON). A changed question, schema or key, or another difference of the same kind, no longer matches the decision,
# and the comparison fails until the lead developer decides again.
DECIDED = {
    'C02': {
        'decision': 'both acceptable',
        'reading': "B's one variant (ANSWERED with no id) is already accepted by A's checks",
        'differences': [
            ['variants-differ', '1 of B only (1 of them correct under A), 0 of A only'],
        ],
        'sha256': {
            'task': '233b603ddee1803c591657b6614338904e92d4dd2bd10e9a3f43abe54f950771',
            'keyA': '769feb4be2a06e84df910dc0c4d710c0a712c787836f1b108d84a14d06b6196a',
            'keyB': 'b56c796ce40b2760a929b8e6a27c71b9a312525df172f3b3930597e3a06c0c33',
        },
    },
    'D04': {
        'decision': 'both acceptable',
        'reading': "B's partial subsets of the identifiers are already accepted by A's ids_within check",
        'differences': [
            ['variants-differ', '7 of B only (7 of them correct under A), 0 of A only'],
        ],
        'sha256': {
            'task': 'c5c83742ce130800e38d07862d9622fd9811e4dbb9b738303b0ac80c0fcbf0ec',
            'keyA': 'b83d7c3ea7dde87c547ef852f0bf39b194e24ac984823ddd08b78e6fab2a3691',
            'keyB': '4e3254eecb70b645714fb266fe53f5d3f0a5400bc095a164cf5752b3616f13aa',
        },
    },
    'D07': {
        'decision': 'both acceptable',
        'reading': ('null and an empty list for the names that cannot be established are equivalent; fields_null accepts '
                    'both'),
        'differences': [
            ['answer-differs', 'paths $.missions'],
        ],
        'sha256': {
            'task': 'ca35d8113dafac7fb689b9b3ab6d9c9642202df27179ea48284b7c65d01fc318',
            'keyA': '38350f6e9ef7b2a0965bc3dd6aab0aea3948e43e98fa73079895392898d60ec7',
            'keyB': '921cf9582b340dba66091b4b893f3c3edfbcdc75f0fd0f3839b89e55adfe3c36',
        },
    },
    'D09': {
        'decision': 'both acceptable',
        'reading': "B's partial subsets of the identifiers are already accepted by A's ids_within check",
        'differences': [
            ['variants-differ', '15 of B only (15 of them correct under A), 0 of A only'],
        ],
        'sha256': {
            'task': '50df2447965d1b84f57d51bb548735754964e119d54f1f000a4d4bcc601e68dd',
            'keyA': '806cc19d7cf5eb65cff44591cf59c365899656ff9b5f74fffd56a3b03b2dc5d0',
            'keyB': '9876b95c5d3e75abde594240f3ca3dfa78346866b51ea920e60cc1eb66dafa14',
        },
    },
    'F02': {
        'decision': 'both acceptable',
        'reading': ('the example answers show different accepted readings; the rubric scores either, and both readings '
                    'agree'),
        'differences': [
            ['example-reading-differs', 'A actual, B estimated'],
        ],
        'sha256': {
            'task': 'a50919906f7726a53ae2d37c727bb73d0a8311738ee206c9e9ac9033aac85133',
            'keyA': 'b0f21113e8861ef488b38776bcf35cd5285ccc79fc362fb83276879bf869aa09',
            'keyB': '96367692345b69d107c7011c12eebc4d3f43b9fa5b262d3fa087937142d4118e',
        },
    },
    'V04': {
        'decision': 'both acceptable',
        'reading': "B's partial subsets of the identifiers are already accepted by A's checks",
        'differences': [
            ['variants-differ', '3 of B only (3 of them correct under A), 0 of A only'],
        ],
        'sha256': {
            'task': 'f7a40e8e42da4e013df86cb42dccdc91cc2786d8c9d1ddb6151c63913a47b5d7',
            'keyA': '447d04dd432151c21c2b4cf5d357092462f70c1949a7a3dc4e7b757d3184c0eb',
            'keyB': 'cace6e4e051f91f7e5389a260545990be9d3e24daadeeab2fa1f64e4ea553b50',
        },
    },
    'V06': {
        'decision': 'question clarified',
        'reading': ('the wording of 2026-11-02 leaves out the types with no such missions, which is the answer of A and of the main answer '
                    "of B; B's variant that lists every type with a zero count is no longer a fair reading of the question; the "
                    'decision of 2026-10-31 (question unclear) was on the earlier wording, and both derivations stay unchanged'),
        'differences': [
            ['variants-differ', '1 of B only (0 of them correct under A), 0 of A only'],
            ['b-variant-not-correct-under-a', '1 of 1 variants of B'],
        ],
        'sha256': {
            'task': '626d70a7be32ccc8438c15a8928219bcdc65dfaf6c7219de255ddfa8ebdb97df',
            'keyA': '415d2395a41865b1f4dee4707954b89b2bc87d584fa0b0e468cbc5c13e67a952',
            'keyB': 'eb5b62d9654333d8f95c603778b2ff50ba911d97f8190a3951cc9e53fa632bec',
        },
    },
}


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def lf_sha256(path):
    """SHA-256 of a file with CRLF read as LF, so a checkout's line endings do not change it."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def lab_input(path, commit=None):
    """The bytes of a lab file at the commit the package was built from (B_RECORD['labCommit'] by default), read from Git."""
    commit = B_RECORD['labCommit'] if commit is None else commit
    return subprocess.run(['git', '-C', str(HERE), 'show', '%s:%s' % (commit, path)], check=True, capture_output=True).stdout


def input_problems(keys_b, read=lab_input):
    """The inputs B recorded (keys-b.json) that do not hash as the files B received: [path]. `read` gives the bytes of a lab path at the
    package's lab commit."""
    problems = []
    for path, digest in keys_b['inputs'].items():
        if path in B_PACKAGE_ONLY_INPUTS:
            continue
        data = read(path)
        if path == B_REWRITTEN_INPUT:
            data = b_dev_input(data)
        else:
            data = data.replace(b'\r\n', b'\n')
        if hashlib.sha256(data).hexdigest() != digest:
            problems.append(path)
    return problems


# The question changes the Job study2_corpus_wording made since B's inputs, and only those: the SHA-256 of each question as reviewed
# (E01, E03, E06 and E07 by the author and the checker, V06 by the lead developer). The current corpus may differ from what B received
# in exactly these five questions.
REVIEWED_QUESTIONS = {
    'study/corpus2/pool.json': {
        'E01': '276e6bff20e415b16a7f861ded031d223dafb707b76f75ddeb920610b65d0dd7',
        'E03': '0ed78ff6f457dd6c83728a645e7dbafa4ca10761ff33dccf91d4029699e0c43b',
        'E06': '840b1b54c953136fbfb3ca31ceda215342b7b69ba53030ea4a776fcf95d39745',
        'E07': '6e264c897c9a727dcaaed113be8885f9a39cafd75c15fed2604414ec30785f48',
    },
    'study/corpus2/dev.json': {
        'V06': 'e45b4188b0e1d5b25f9a92395044b6b318fe9e8e6688fe92e1b7cb392e8df494',
    },
}


def current_input(path):
    """The bytes of a lab input as the working tree holds it."""
    return (HERE.parents[1] / path).read_bytes()


# The draw (Job study2_preflight_final, decision Q10): B received schemas.json empty, before the draw. The current file may differ from
# it only by being exactly the drawn schemas.json, the one draw.py writes from the committed step 7 reports and the seed tasks.json records.
DRAWN_SCHEMAS = 'study/corpus2/schemas.json'
STEP7_REPORTS = ('study/evidence/study-2-preflight', '07-answerability-*.json')


def drawn_files(folder=HERE, reports=None):
    """The bytes of tasks.json, schemas.json and expected.json that draw.py writes from the committed step 7 reports (STEP7_REPORTS) and
    the seed that tasks.json records, computed in memory with draw.py's own functions: {name: bytes}. None when tasks.json records no
    draw. Nothing is written. A report, pool, ambiguity set or key that draw.py would refuse raises its ValueError."""
    import draw
    record = json.loads((folder / 'tasks.json').read_text(encoding='utf-8')).get('draw')
    if not record:
        return None
    if reports is None:
        reports = sorted((folder.parents[1] / STEP7_REPORTS[0]).glob(STEP7_REPORTS[1]))
    texts = {name: (folder / name).read_text(encoding='utf-8') for name in ('pool.json', 'ambiguity.json', 'keys-a.json')}
    pool = json.loads(texts['pool.json'])['tasks']
    ambiguity = json.loads(texts['ambiguity.json'])['tasks']
    keys = json.loads(texts['keys-a.json'])['keys']
    report_texts = [Path(p).read_text(encoding='utf-8') for p in reports]
    parsed = [json.loads(t) for t in report_texts]
    draw.check_pool(pool, keys)
    current = draw.input_hashes(folder)
    eligible, fingerprint = draw.eligible_ids(pool, parsed, keys, current)
    draw.check_ambiguity(ambiguity, parsed, keys, current)
    chosen = draw.draw(pool, eligible, record['seed'])
    # the draw record exactly as draw.main writes it
    again = {'seed': record['seed'], 'poolSha256': draw.sha256_text(texts['pool.json']),
             'ambiguitySha256': draw.sha256_text(texts['ambiguity.json']), 'keysSha256': draw.sha256_text(texts['keys-a.json']),
             'eligible': len(eligible), 'poolTasks': len(pool), 'missionsDatasetFingerprint': fingerprint,
             'answerabilityReports': sorted(draw.sha256_text(t) for t in report_texts)}
    return {name: text.encode('utf-8') for name, text in draw.outputs(pool, ambiguity, keys, chosen, again).items()}


def current_problems(keys_b, read_current=current_input, read_lab=lab_input, drawn=None):
    """How the current lab inputs differ from the ones B received, beyond the reviewed question changes and the draw: [description]. A
    file B hashed must be the same as at the package's lab commit, except that pool.json and dev.json may differ in the `question` of the
    tasks of REVIEWED_QUESTIONS, which must be exactly the reviewed one (every other field of every task, and the set of tasks, must be
    equal), and that schemas.json, empty when B received it, may be exactly the drawn schemas.json (drawn_files; `drawn` gives its bytes
    instead)."""
    problems = []
    for path in keys_b['inputs']:
        if path in B_PACKAGE_ONLY_INPUTS:
            continue
        then, now = read_lab(path).replace(b'\r\n', b'\n'), read_current(path).replace(b'\r\n', b'\n')
        reviewed = REVIEWED_QUESTIONS.get(path)
        if reviewed is None:
            if then != now and not (path == DRAWN_SCHEMAS and _is_the_drawn_schemas(then, now, drawn)):
                problems.append('%s differs from the file B received' % path)
            continue
        old, new = json.loads(then.decode('utf-8')), json.loads(now.decode('utf-8'))
        if {k: v for k, v in old.items() if k != 'tasks'} != {k: v for k, v in new.items() if k != 'tasks'}:
            problems.append('%s differs outside its tasks' % path)
        old_tasks, new_tasks = {t['id']: t for t in old['tasks']}, {t['id']: t for t in new['tasks']}
        if [t['id'] for t in old['tasks']] != [t['id'] for t in new['tasks']]:
            problems.append('%s holds other tasks than the file B received' % path)
            continue
        for task_id, task in old_tasks.items():
            current = new_tasks[task_id]
            if task_id in reviewed:
                if hashlib.sha256(current['question'].encode('utf-8')).hexdigest() != reviewed[task_id]:
                    problems.append('%s %s: the question is not the reviewed one' % (path, task_id))
                task, current = dict(task, question=None), dict(current, question=None)
            if task != current:
                problems.append('%s %s differs from the file B received' % (path, task_id))
    return problems


def _is_the_drawn_schemas(then, now, drawn=None):
    """True when B's schemas.json held no schema and the current one is byte for byte the drawn schemas.json."""
    if json.loads(then.decode('utf-8')).get('schemas') != {}:
        return False
    if drawn is None:
        files = drawn_files()
        if files is None:
            return False
        drawn = files['schemas.json']
    return now == drawn.replace(b'\r\n', b'\n')


def b_dev_input(lab_bytes):
    """The dev.json B received, rebuilt from the lab's file as study/blind/blind.py rewrote it for the package: the `expected` entry of
    every task dropped and nothing else, written back with indent 2 and a final newline."""
    value = json.loads(lab_bytes.replace(b'\r\n', b'\n').decode('utf-8'))
    for task in value['tasks']:
        task.pop('expected', None)
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def fold(value):
    """The scorer's folding of a whole answer: strings by scoring.norm, numbers by value, lists of strings as sets (duplicates kept
    apart), other lists in any order, objects by their fields. null and an empty list stay different."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return ('number', str(Decimal(repr(value) if isinstance(value, float) else str(value)).normalize()))
    if isinstance(value, str):
        return scoring.norm(value)
    if isinstance(value, dict):
        return ('object', tuple(sorted((name, fold(item)) for name, item in value.items())))
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return ('set', tuple(sorted({scoring.norm(item) for item in value})), len(value))
        return ('list', tuple(sorted((fold(item) for item in value), key=repr)))
    raise TypeError('cannot fold %r' % (value,))


def differing_paths(a, b, path='$'):
    """The paths of the fields where two answers differ after folding."""
    if fold(a) == fold(b):
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        paths = []
        for name in sorted(set(a) | set(b)):
            paths += differing_paths(a.get(name, '<absent>'), b.get(name, '<absent>'), path + '.' + name)
        return paths
    return [path]


def submitted(answer):
    """A key's answer as a submission: answerStatus ANSWERED where the key leaves it out, as test_corpus2.py reads a key."""
    answer = copy.deepcopy(answer)
    answer.setdefault('answerStatus', 'ANSWERED')
    return answer


def context(task, task_set):
    return {'taskId': task['id'], 'set': task_set, 'category': task['category'], 'askRequester': []}


def compare_core(task, key_a, key_b):
    """The differences of one task of the pool or the development set."""
    found = []
    schema, ctx = task['schema'], context(task, 'core')
    answer_a, answer_b = submitted(key_a['answer']), submitted(key_b['answer'])
    result = scoring.score(answer_b, schema, key_a, ctx)
    if result['outcome'] != 'correct':
        found.append(('b-not-correct-under-a', '%s, failed %s' % (result['outcome'], ','.join(result['failedChecks']))))
    variants_b = [submitted(variant['answer']) for variant in key_b['variants']]
    if fold(answer_a) != fold(answer_b) and all(fold(answer_a) != fold(variant) for variant in variants_b):
        found.append(('answer-differs', 'paths %s' % ','.join(differing_paths(answer_a, answer_b))))
    variants_a = key_a.get('variants', [])
    b_unmatched = [v for v in variants_b if not any(not scoring.run_checks(v, va['checks'])[0] for va in variants_a)]
    a_unmatched = [va for va in variants_a if not any(not scoring.run_checks(v, va['checks'])[0] for v in variants_b)]
    if b_unmatched or a_unmatched:
        accepted = sum(1 for v in b_unmatched if scoring.score(v, schema, key_a, ctx)['outcome'] == 'correct')
        found.append(('variants-differ', '%d of B only (%d of them correct under A), %d of A only'
                      % (len(b_unmatched), accepted, len(a_unmatched))))
    rejected = [v for v in variants_b if scoring.score(v, schema, key_a, ctx)['outcome'] != 'correct']
    if rejected:
        found.append(('b-variant-not-correct-under-a', '%d of %d variants of B' % (len(rejected), len(variants_b))))
    return found


def compare_ambiguity(task, key_a, key_b):
    """The differences of one task of the ambiguity set, per interpretation."""
    found = []
    schema, ctx, rubric = task['schema'], context(task, 'ambiguity'), key_a['rubric']
    names_a = {item['name'] for item in rubric['interpretations']}
    names_b = set(key_b['interpretations'])
    if names_a != names_b:
        found.append(('interpretation-names-differ', 'A only %s, B only %s' % (sorted(names_a - names_b), sorted(names_b - names_a))))
    for name in sorted(names_a & names_b):
        result = scoring.score(submitted(key_b['interpretations'][name]['answer']), schema, key_a, ctx)
        if result['outcome'] != 'correct' or result['tags'] != ['interpretation:' + name]:
            found.append(('b-interpretation-not-correct-under-a', '%s: %s %s' % (name, result['outcome'], result['tags'])))
    answer_a = submitted(key_a['answer'])
    reading_a = scoring.evaluate_interpretations(answer_a, rubric)[0]
    if reading_a in key_b['interpretations']:
        answer_b = submitted(key_b['interpretations'][reading_a]['answer'])
        if fold(answer_a) != fold(answer_b):
            found.append(('a-answer-differs', '%s: paths %s' % (reading_a, ','.join(differing_paths(answer_a, answer_b)))))
    else:
        found.append(('a-reading-missing-in-b', str(reading_a)))
    readings_b = [fold(submitted(item['answer'])) for item in key_b['interpretations'].values()]
    outside = [v for v in [key_b['answer']] + [v['answer'] for v in key_b['variants']] if fold(submitted(v)) not in readings_b]
    if outside:
        found.append(('b-answer-outside-interpretations', '%d answers' % len(outside)))
    reading_b = scoring.evaluate_interpretations(submitted(key_b['answer']), rubric)[0]
    if reading_b != reading_a:
        found.append(('example-reading-differs', 'A %s, B %s' % (reading_a, reading_b)))
    return found


def compare(keys_a=None, keys_b=None, tasks=None):
    """{task id: {'differences': [[kind, detail], ...], 'sha256': {'task', 'keyA', 'keyB'}}} for every task with a difference. The keys
    default to the two key files and `tasks`, a (pool, ambiguity, dev) triple of task lists, to the three task files."""
    keys_a = load('keys-a.json')['keys'] if keys_a is None else keys_a
    keys_b = load('keys-b.json')['keys'] if keys_b is None else keys_b
    if tasks is None:
        tasks = load('pool.json')['tasks'], load('ambiguity.json')['tasks'], load('dev.json')['tasks']
    pool, ambiguity, dev = tasks
    ids = [task['id'] for task in pool + ambiguity + dev]
    if set(keys_a) != set(ids) or set(keys_b) != set(ids):
        raise ValueError('the keys do not cover exactly the %d tasks: A %d, B %d' % (len(ids), len(keys_a), len(keys_b)))
    differences = {}
    for task in pool + dev + ambiguity:
        key_a, key_b = keys_a[task['id']], keys_b[task['id']]
        found = (compare_ambiguity if task in ambiguity else compare_core)(task, key_a, key_b)
        if found:
            differences[task['id']] = {
                'differences': [[kind, detail] for kind, detail in found],
                'sha256': {'task': canonical_sha256(task), 'keyA': canonical_sha256(key_a), 'keyB': canonical_sha256(key_b)},
            }
    return differences


def undecided(differences, decided=None):
    """The mismatches between the differences found and the decided ones: [(task id, why)]. A task matches only when the exact
    differences and the hashes of its task and both keys equal those that were decided."""
    decided = DECIDED if decided is None else decided
    out = []
    for task_id in sorted(set(differences) | set(decided)):
        found, want = differences.get(task_id), decided.get(task_id)
        if want is None:
            out.append((task_id, 'not decided: %s' % found['differences']))
        elif found is None:
            out.append((task_id, 'decided, but no difference is found any more'))
        elif found['differences'] != want['differences']:
            out.append((task_id, 'the differences changed: found %s, decided %s' % (found['differences'], want['differences'])))
        elif found['sha256'] != want['sha256']:
            changed = sorted(name for name in want['sha256'] if found['sha256'].get(name) != want['sha256'][name])
            out.append((task_id, 'decided on other inputs: %s changed since the decision' % ', '.join(changed)))
    return out


def main(argv=None):
    differences = compare()
    for task_id, found in sorted(differences.items()):
        decision = DECIDED.get(task_id, {}).get('decision', 'NOT DECIDED')
        for kind, detail in found['differences']:
            print('%s  %s  %s  [%s]' % (task_id, kind, detail, decision))
    mismatches = undecided(differences)
    for task_id, why in mismatches:
        print('MISMATCH %s: %s' % (task_id, why), file=sys.stderr)
    tasks = len(load('keys-a.json')['keys'])
    print('%d tasks compared, %d with a difference, %d mismatched with the decided cases' % (tasks, len(differences), len(mismatches)))
    return 1 if mismatches else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
