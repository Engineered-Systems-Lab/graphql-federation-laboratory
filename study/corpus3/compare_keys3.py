"""Compare the two derivations of the keys of corpus 3's 31 new tasks: keys-a.json (derive_a3.py) and keys-b3.json (derive_b3.py, the
blind second derivation).

Entries 5 and 6 of the Job study3_corpus_keys_b, decisions J4 and J7. The comparison is corpus 2's (study/corpus2/compare_keys.py,
unchanged and imported here), run on the new tasks with this folder's scorer. For each of the 31 new tasks:

- B's answer, scored by this folder's scoring.py against keys-a.json, must be correct;
- A's answer must equal B's under the scorer's folding (case, space, hyphen and underscore; numbers by value; lists of strings as sets;
  other lists in any order), or be one of B's declared variants;
- the declared variants of the two are compared as sets: a variant of one side is matched when it fits a variant of the other side
  (B's by its answer, A's by its checks).

The new tasks are all core tasks, so corpus 2's comparison of the ambiguity set does not apply.

Every difference was brought to the lead developer and decided, task by task; DECIDED names them, each bound to the exact differences
and to the hashes of its task and of both keys' entries, and the comparison passes only when the differences it finds are exactly the
decided ones on those same inputs. Neither derivation is changed here: a fix is its own Job.

B's inputs are checked without the package: the keys-b3 package is rebuilt in memory from Git at the package's lab commit, by the
`plan` and `manifest_of` of study/blind/blind.py as that commit holds it (never the working tree's builder, so a later change of the
builder or of its package definitions cannot change the reconstruction), and every input B hashed must hash as the rebuilt file,
MANIFEST.json included.
derive_b3.py and test_derive_b3.py check their inputs against the package's MANIFEST.json, so they run only in a copy of the package and
not in the study gate.

    python -B study/corpus3/compare_keys3.py

prints one line per difference (task id, kind, detail and decision), never a question, and exits 0 only when every difference found is
decided and every decided difference is found. Standard library only.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# This folder's scorer, under a name of its own, and corpus 2's comparison, also under a name of its own so that it never shadows a
# corpus 2 module. Corpus 2's functions read their scorer from their module's `scoring`, which is set to this folder's.
scoring3 = sys.modules.get('compare_keys3_scoring') or _load('compare_keys3_scoring', HERE / 'scoring.py')
compare2 = sys.modules.get('compare_keys3_corpus2') or _load('compare_keys3_corpus2', REPO / 'study' / 'corpus2' / 'compare_keys.py')
compare2.scoring = scoring3

canonical_sha256 = compare2.canonical_sha256
compare_core = compare2.compare_core
fold = compare2.fold
lf_sha256 = compare2.lf_sha256
undecided_against = compare2.undecided

# Phase B as the Job record holds it (J5): the private repository's final commit, the model, the date, the package and the hashes of
# B's three files.
B_RECORD = {
    'commit': 'b7dde8e0f475a88378adcb2bf316173ece13c39c',
    'model': 'GPT-6 Astra High (gpt-6-astra), in a Codex cloud task with network access None, as the lead developer reports',
    'date': '2026-11-17',
    'package': 'keys-b3',
    'packageSha256': '2feff55de79844aa67df69cb9685d6d70cdedc11737376b4fc530aa1a17a577a',
    'manifestSha256': '2dd51cba338f512e3510a7110d3adf7bdc5b63d01181348af0c5fddc29c5823d',
    'labCommit': '4e90e5c90cc2c5ee6a221e14358261204b049011',
    'sha256': {
        'derive_b3.py': 'c6a3ef83ade6791b74a3486ef50c8fea21017f83dfe6437afa3e97f231e97c65',
        'keys-b3.json': '581da9c2e8c4f7bef4f29944ad30e02106115710e14e05a1c401272266185a4b',
        'test_derive_b3.py': '0d3b2c1cf0f2506ee306cc93cca1c1bc5deb5ed6972800f28f2bfbc0791fa8c2',
    },
}

BUILDER = 'study/blind/blind.py'
# What the builder of the lab commit reads besides the packaged files: itself, its package definitions and its README templates. A
# rebuild of the current files reads these from Git at the lab commit too, so only the packaged files come from the working tree.
BUILDER_FOLDER = 'study/blind/'


def git_blob(commit, path):
    """The bytes of a lab path at a commit, read from Git, with the inherited GIT_* variables left out."""
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_') or k == 'GIT_PAGER'}
    return subprocess.run(['git', '-C', str(REPO), 'cat-file', 'blob', '%s:%s' % (commit, path)], check=True, capture_output=True,
                          env=env).stdout


def builder_at(commit):
    """study/blind/blind.py as `commit` holds it, loaded from Git as a module of its own (its root is this checkout's root)."""
    name = 'compare_keys3_blind_%s' % commit
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__file__ = str(REPO / BUILDER)
        sys.modules[name] = module
        exec(compile(git_blob(commit, BUILDER), '%s:%s' % (commit, BUILDER), 'exec'), module.__dict__)
    return sys.modules[name]


# The builder that made the package B received.
blind = builder_at(B_RECORD['labCommit'])

# The package files that are not lab files: the manifest and the README, written by blind.py for the package.
PACKAGE_ONLY_INPUTS = (blind.MANIFEST, blind.README)


class CurrentSource:
    """The lab's current files as the builder of the lab commit would package them: the builder's own folder (its definitions and README
    templates) read from Git at the lab commit, every other file from the working tree. `working` gives another working-tree source."""

    def __init__(self, working=None):
        self.git = blind.GitSource(B_RECORD['labCommit'], REPO)
        self.working = blind.WorkingSource(REPO) if working is None else working
        self.commit, self.label = None, 'working-tree'

    def read(self, path):
        return (self.git if path.startswith(BUILDER_FOLDER) else self.working).read(path)

    def files_under(self, folder):
        return (self.git if folder.startswith(BUILDER_FOLDER) else self.working).files_under(folder)

# The differences the lead developer decided, one at a time (J7). Each decision is bound to what was decided: the exact differences
# found (kind and detail) and the SHA-256 of the task (its record with its schema) and of both keys' entries (canonical JSON). A changed
# question, schema or key, or another difference of the same kind, no longer matches the decision, and the comparison fails until the
# lead developer decides again.
DECIDED = {}


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def package_files(source=None):
    """The keys-b3 package as the builder of the lab commit builds it from `source` (by default Git at B_RECORD['labCommit']), in
    memory: {path: bytes}, MANIFEST.json included, written as blind.write_package writes it. Nothing is written."""
    source = blind.GitSource(B_RECORD['labCommit'], REPO) if source is None else source
    files = blind.plan(source, B_RECORD['package'])
    manifest = blind.manifest_of(B_RECORD['package'], source, files)
    out = {path: entry['bytes'] for path, entry in files.items()}
    out[blind.MANIFEST] = json.dumps(manifest, indent=2, ensure_ascii=False).encode('utf-8') + b'\n'
    return out


def package_problems(files=None):
    """How the rebuilt package differs from the one B received, as the Job record holds it: [description]."""
    files = package_files() if files is None else files
    problems = []
    manifest = json.loads(files[blind.MANIFEST].decode('utf-8'))
    unsigned = {name: value for name, value in manifest.items() if name != 'packageSha256'}
    if {manifest.get('packageSha256'), blind.sha256(blind.canonical(unsigned))} != {B_RECORD['packageSha256']}:
        problems.append('the rebuilt package is not packageSha256 %s' % B_RECORD['packageSha256'])
    if hashlib.sha256(files[blind.MANIFEST]).hexdigest() != B_RECORD['manifestSha256']:
        problems.append('the rebuilt MANIFEST.json is not %s' % B_RECORD['manifestSha256'])
    return problems


def input_problems(keys_b, files=None):
    """The inputs B recorded (keys-b3.json) that do not hash as the files of the package rebuilt from Git at the package's lab commit,
    and the package files B did not record: [path]. `files` gives the package's bytes instead (package_files)."""
    files = package_files() if files is None else files
    problems = []
    for path, digest in keys_b['inputs'].items():
        if path not in files or hashlib.sha256(files[path]).hexdigest() != digest:
            problems.append(path)
    problems += sorted(path for path in files if path not in keys_b['inputs'])
    return problems


def current_problems(keys_b, current=None, then=None):
    """The lab files B hashed whose current bytes, as the builder of the lab commit would package them from the working tree
    (CurrentSource), differ from the ones B received: [path]. The manifest and the README are the package's own and are left out.
    `current` and `then` give the two packages instead."""
    current = package_files(CurrentSource()) if current is None else current
    then = package_files() if then is None else then
    return [path for path in keys_b['inputs'] if path not in PACKAGE_ONLY_INPUTS and current.get(path) != then.get(path)]


def new_tasks(tasks=None, schemas=None, manifest=None):
    """The new tasks, each its record in tasks.json with its schema from schemas.json, in the manifest's order of newTaskIds."""
    tasks = load('tasks.json')['tasks'] if tasks is None else tasks
    schemas = load('schemas.json')['schemas'] if schemas is None else schemas
    manifest = load('corpus-manifest.json') if manifest is None else manifest
    by_id = {task['id']: task for task in tasks}
    return [dict(by_id[task_id], schema=schemas[task_id]) for task_id in manifest['newTaskIds']]


def compare(keys_a=None, keys_b=None, tasks=None):
    """{task id: {'differences': [[kind, detail], ...], 'sha256': {'task', 'keyA', 'keyB'}}} for every new task with a difference. The
    keys default to the two key files and `tasks` to the new tasks (new_tasks)."""
    keys_a = load('keys-a.json')['keys'] if keys_a is None else keys_a
    keys_b = load('keys-b3.json')['keys'] if keys_b is None else keys_b
    tasks = new_tasks() if tasks is None else tasks
    ids = [task['id'] for task in tasks]
    if set(keys_b) != set(ids) or not set(ids) <= set(keys_a):
        raise ValueError('the keys do not cover exactly the %d new tasks: B %d, A lacks %s'
                         % (len(ids), len(keys_b), sorted(set(ids) - set(keys_a))))
    differences = {}
    for task in tasks:
        key_a, key_b = keys_a[task['id']], keys_b[task['id']]
        if task.get('set', 'core') != 'core' or key_b.get('set', 'core') != 'core':
            raise ValueError('%s is not a core task' % task['id'])
        found = compare_core(task, key_a, key_b)
        if found:
            differences[task['id']] = {
                'differences': [[kind, detail] for kind, detail in found],
                'sha256': {'task': canonical_sha256(task), 'keyA': canonical_sha256(key_a), 'keyB': canonical_sha256(key_b)},
            }
    return differences


def undecided(differences, decided=None):
    """The mismatches between the differences found and the decided ones: [(task id, why)], as corpus 2's undecided."""
    return undecided_against(differences, DECIDED if decided is None else decided)


def main(argv=None):
    differences = compare()
    for task_id, found in sorted(differences.items()):
        decision = DECIDED.get(task_id, {}).get('decision', 'NOT DECIDED')
        for kind, detail in found['differences']:
            print('%s  %s  %s  [%s]' % (task_id, kind, detail, decision))
    mismatches = undecided(differences)
    for task_id, why in mismatches:
        print('MISMATCH %s: %s' % (task_id, why), file=sys.stderr)
    print('%d tasks compared, %d with a difference, %d mismatched with the decided cases'
          % (len(load('keys-b3.json')['keys']), len(differences), len(mismatches)))
    return 1 if mismatches else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
