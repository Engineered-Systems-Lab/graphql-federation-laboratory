"""Build and check the input packages of study 2's blind workers: the guide author's and the keys B worker's.

    python -B study/blind/blind.py build guide|keys-b --commit <full lab commit> --output <new folder outside any Git work tree>
    python -B study/blind/blind.py verify <package folder>
    python -B study/blind/blind.py list guide|keys-b [--commit <full lab commit>]

`build` reads everything from the named commit, never from the working tree: the package definitions (packages.json), the README
templates and every file of the allow-list. It refuses unless this script's own bytes are the commit's study/blind/blind.py, so the output
is a function of the commit alone, and the same commit always gives the same bytes. The output is a plain folder: no `.git`, no remote,
no history. It holds the allowed files, each at its lab path, the package README at its root, any derived file the definition names and
`MANIFEST.json` with the commit, every file's SHA-256 and size, how each file was made, the builder's version and hash, and the package's
own hash (`packageSha256`, the SHA-256 of the manifest's canonical JSON without that field).

`verify` checks a built package against its manifest (every file, nothing more, no `.git`) and runs the leak checks of decision I5 against
the lab checkout this script belongs to. `list` prints the files a package would hold, from the commit or, without --commit, from the
working tree. This script never creates a repository, a remote or a push: the lead developer makes the private repository from the folder.

Standard library only; Git is called read-only.
"""
import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

VERSION = 1
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SELF = 'study/blind/blind.py'
DEFINITIONS = 'study/blind/packages.json'
MANIFEST = 'MANIFEST.json'
README = 'README.md'
PACKAGES = ('guide', 'keys-b')
CORPUS2 = 'study/corpus2/'
FULL_SHA = re.compile(r'[0-9a-f]{40}')
TOOL_ARGS_SKIPPED = ('ctx',)


class Refused(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def lf(data):
    return data.replace(b'\r\n', b'\n')


def git(args, cwd=ROOT, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_') or k == 'GIT_PAGER'}
    done = subprocess.run(['git', *args], cwd=str(cwd), capture_output=True, env=env)
    if check and done.returncode != 0:
        raise Refused('git %s failed: %s' % (' '.join(args), done.stderr.decode('utf-8', 'replace').strip()))
    return done


# ------------------------------------------------------------------------------------------------------------------ the sources

class GitSource:
    """The files of one commit, read with git show and git ls-tree."""

    def __init__(self, commit, root=ROOT):
        if not FULL_SHA.fullmatch(commit or ''):
            raise Refused('give the full 40-character commit id, not %r' % commit)
        if git(['cat-file', '-t', commit], cwd=root, check=False).stdout.decode().strip() != 'commit':
            raise Refused('%s is not a commit of %s' % (commit, root))
        self.root, self.commit, self.label = Path(root), commit, commit

    def read(self, path):
        done = git(['cat-file', 'blob', '%s:%s' % (self.commit, path)], cwd=self.root, check=False)
        if done.returncode != 0:
            raise Refused('%s does not hold %s' % (self.commit, path))
        return done.stdout

    def files_under(self, folder):
        out = git(['ls-tree', '-r', '-z', '--name-only', self.commit, '--', folder], cwd=self.root).stdout.decode('utf-8')
        return sorted(name for name in out.split('\0') if name)


class WorkingSource:
    """The working tree's files that Git tracks or would track (the tests' and `list`'s source); never used by `build`."""

    def __init__(self, root=ROOT):
        self.root, self.commit, self.label = Path(root), None, 'working-tree'

    def read(self, path):
        target = self.root / path
        if not target.is_file():
            raise Refused('the working tree does not hold %s' % path)
        return target.read_bytes()

    def files_under(self, folder):
        out = git(['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', folder], cwd=self.root).stdout.decode('utf-8')
        return sorted(name for name in set(out.split('\0')) if name and (self.root / name).is_file())


# ----------------------------------------------------------------------------------------------------------- the derived files

def markdown_section(text, heading):
    """The `## heading` section of a Markdown text, its heading line included, up to the next `## ` heading. Refuses when absent."""
    lines = text.split('\n')
    start = next((i for i, line in enumerate(lines) if line.strip() == '## ' + heading), None)
    if start is None:
        raise Refused('the section %r is missing' % heading)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
    return '\n'.join(lines[start:end]).rstrip('\n') + '\n'


def _field_description(node):
    for keyword in getattr(node, 'keywords', []):
        if keyword.arg == 'description' and isinstance(keyword.value, ast.Constant):
            return keyword.value.value
    return None


def raw_server_tools(source_text):
    """The tools the raw MCP server's build() declares: name, description and parameters, read from the source (nothing is imported)."""
    tree = ast.parse(source_text)
    build = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build'), None)
    if build is None:
        raise Refused('raw_server.py has no build()')
    tools = []
    for node in ast.walk(build):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        description = None
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and ast.unparse(decorator.func) == 'server.tool':
                description = _field_description(decorator)
        if description is None:
            continue
        args = node.args.args
        defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)
        params = []
        for arg, default in zip(args, defaults):
            if arg.arg in TOOL_ARGS_SKIPPED:
                continue
            annotation, text = arg.annotation, None
            if isinstance(annotation, ast.Subscript) and ast.unparse(annotation.value) == 'Annotated':
                parts = annotation.slice.elts
                kind, text = ast.unparse(parts[0]), next((_field_description(p) for p in parts[1:] if _field_description(p)), None)
            else:
                kind = ast.unparse(annotation) if annotation is not None else None
            params.append({'name': arg.arg, 'type': kind, 'description': text, 'required': default is None,
                           'default': None if default is None else ast.unparse(default)})
        tools.append({'name': node.name, 'description': description, 'parameters': params})
    if not tools:
        raise Refused('raw_server.py declares no tool')
    return tools


class _Values:
    """Module-level constants of a source file, evaluated from its syntax tree: literals, names, list(), nothing else."""

    def __init__(self, source_text):
        self.nodes = {}
        for node in ast.parse(source_text).body:
            if isinstance(node, ast.Assign):
                targets = node.targets[0].elts if isinstance(node.targets[0], ast.Tuple) else node.targets
                values = node.value.elts if isinstance(node.targets[0], ast.Tuple) else [node.value]
                for target, value in zip(targets, values):
                    if isinstance(target, ast.Name):
                        self.nodes[target.id] = value

    def get(self, name):
        if name not in self.nodes:
            raise Refused('harness_tools.py has no constant %s' % name)
        return self.value(self.nodes[name])

    def value(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self.get(node.id)
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self.value(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            return {self.value(k): self.value(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'list' and len(node.args) == 1:
            return list(self.value(node.args[0]))
        raise Refused('harness_tools.py: cannot read %s' % ast.unparse(node))


def harness_tools(source_text):
    """The harness tools in the order the harness offers them (NAMES), each with name, description and input schema."""
    values = _Values(source_text)
    table = values.get('TOOLS')
    return [table[name] for name in values.get('NAMES')]


def render_tools(source, sources, commit_label):
    raw = raw_server_tools(source.read(sources['raw_server']).decode('utf-8'))
    harness = harness_tools(source.read(sources['harness_tools']).decode('utf-8'))
    readme = source.read(sources['mcp_readme']).decode('utf-8').replace('\r\n', '\n')
    out = ['# Tools', '',
           'The tools an agent is given, as the agent reads them. Generated from the laboratory\'s commit %s; `MANIFEST.json` names '
           'each source file with its SHA-256. Every text below is copied without change.' % commit_label, '',
           '## The MCP server\'s tools', '',
           'From `%s`: each tool\'s description and its parameters (name, type, description, and the default of an optional one).'
           % sources['raw_server'], '']
    for tool in raw:
        out += ['### %s' % tool['name'], '', tool['description'], '']
        for p in tool['parameters']:
            state = 'required' if p['required'] else 'optional, default %s' % p['default']
            out.append('- `%s` (`%s`, %s): %s' % (p['name'], p['type'], state, p['description'] or ''))
        out.append('')
    out += ['## The harness tools', '',
            'From `%s`: the two tools the harness offers beside the MCP server\'s, with their input schemas, as JSON.'
            % sources['harness_tools'], '', '```json', json.dumps(harness, indent=2, ensure_ascii=False), '```', '',
            '## From the MCP servers\' README', '',
            'The sections %s of `%s`, verbatim, one heading level down.' % (
                ' and '.join('"%s"' % s for s in sources['mcp_readme_sections']), sources['mcp_readme']), '']
    for heading in sources['mcp_readme_sections']:
        section = markdown_section(readme, heading)
        out.append(re.sub(r'^(#+) ', lambda m: '#' + m.group(1) + ' ', section, flags=re.MULTILINE).rstrip('\n'))
        out.append('')
    return ('\n'.join(out).rstrip('\n') + '\n').encode('utf-8')


def drop_key(data, key, where, path):
    """JSON `data` with `key` removed from every object of the list `where`. Refuses when the file does not round-trip unchanged, so the
    rewrite changes that key and nothing else."""
    value = json.loads(data.decode('utf-8'))
    if (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8') != data:
        raise Refused('%s does not round-trip through JSON with indent 2; the rewrite would change more than %r' % (path, key))
    items = value.get(where)
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise Refused('%s has no list of objects %r' % (path, where))
    removed = sum(1 for item in items if key in item)
    for item in items:
        item.pop(key, None)
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'), removed


# ------------------------------------------------------------------------------------------------------------------ the package

def load_definitions(source):
    data = json.loads(source.read(DEFINITIONS).decode('utf-8'))
    if data.get('version') != 1 or set(data.get('packages', {})) != set(PACKAGES):
        raise Refused('%s is not a version 1 definition of the packages %s' % (DEFINITIONS, ', '.join(PACKAGES)))
    return data


def under(path, prefix):
    return path == prefix or (prefix.endswith('/') and path.startswith(prefix))


def plan(source, name):
    """{package path: {"bytes", "source", ...}} for one package, from one source. Refuses an empty folder, a duplicate path, a missing
    file and any path under the package's excluded list."""
    if name not in PACKAGES:
        raise Refused('unknown package %r; the packages are %s' % (name, ', '.join(PACKAGES)))
    definition = load_definitions(source)['packages'][name]
    files = {}

    def put(path, entry):
        if path in files or path in (MANIFEST,):
            raise Refused('%s would hold %s twice' % (name, path))
        bad = [prefix for prefix in definition['excluded'] if under(path, prefix)]
        if bad:
            raise Refused('%s: %s is under the excluded path %s' % (name, path, bad[0]))
        files[path] = entry

    for item in definition['include']:
        paths = source.files_under(item['dir']) if 'dir' in item else [item['path']]
        if not paths:
            raise Refused('%s: the folder %s holds no file at %s' % (name, item['dir'], source.label))
        for path in paths:
            data = source.read(path)
            put(path, {'bytes': data, 'source': 'lab', 'labSha256': sha256(data)})
    for rewrite in definition.get('rewrite', []):
        path = rewrite['path']
        if path not in files:
            raise Refused('%s: the rewrite of %s names a file the package does not include' % (name, path))
        original = files[path]['bytes']
        data, removed = drop_key(original, rewrite['drop'], rewrite['from'], path)
        files[path] = {'bytes': data, 'source': 'rewritten', 'labSha256': sha256(original),
                       'rewrite': {'drop': rewrite['drop'], 'from': rewrite['from'], 'removed': removed, 'why': rewrite['why']}}
    for derived in definition.get('derived', []):
        if derived['kind'] != 'tool-texts':
            raise Refused('%s: unknown derived kind %r' % (name, derived['kind']))
        sources = derived['sources']
        names = [sources['raw_server'], sources['harness_tools'], sources['mcp_readme']]
        put(derived['path'], {'bytes': render_tools(source, sources, source.label), 'source': 'derived', 'kind': derived['kind'],
                              'from': [{'path': p, 'labSha256': sha256(source.read(p))} for p in names]})
    template = definition['readme']
    text = lf(source.read(template)).decode('utf-8').replace('{commit}', source.label)
    put(README, {'bytes': text.encode('utf-8'), 'source': 'readme', 'from': [{'path': template, 'labSha256': sha256(source.read(template))}]})
    return files


def manifest_of(name, source, files):
    entries = []
    for path in sorted(files):
        entry = {k: v for k, v in files[path].items() if k != 'bytes'}
        entry.update({'path': path, 'sha256': sha256(files[path]['bytes']), 'size': len(files[path]['bytes'])})
        entries.append(entry)
    manifest = {
        'package': name,
        'labCommit': source.commit,
        'source': source.label,
        'builder': {'version': VERSION, 'path': SELF, 'sha256': sha256(lf(source.read(SELF)))},
        'definitions': {'path': DEFINITIONS, 'sha256': sha256(source.read(DEFINITIONS))},
        'files': entries,
    }
    manifest['packageSha256'] = sha256(canonical(manifest))
    return manifest


def inside_git_work_tree(folder):
    """True when `folder` (which may not exist yet) is inside a Git work tree: a `.git` in it or above it, or Git says so."""
    folder = Path(folder).resolve()
    probe = folder
    while not probe.exists():
        probe = probe.parent
    for place in [folder, *folder.parents]:
        if (place / '.git').exists():
            return True
    done = git(['rev-parse', '--is-inside-work-tree'], cwd=probe, check=False)
    return done.returncode == 0 and done.stdout.decode().strip() == 'true'


def write_package(name, source, output):
    output = Path(output).resolve()
    if inside_git_work_tree(output):
        raise Refused('the output folder %s is inside a Git work tree; give a folder outside every repository' % output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise Refused('the output folder %s exists and is not empty' % output)
    files = plan(source, name)
    manifest = manifest_of(name, source, files)
    for path in sorted(files):
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(files[path]['bytes'])
    (output / MANIFEST).write_bytes(json.dumps(manifest, indent=2, ensure_ascii=False).encode('utf-8') + b'\n')
    return manifest


def build(name, commit, output, root=ROOT):
    source = GitSource(commit, root)
    running = lf(Path(__file__).read_bytes())
    if running != lf(source.read(SELF)):
        raise Refused('this blind.py is not the one of %s; run the builder of that commit (check it out, or use its worktree)' % commit)
    return write_package(name, source, output)


# ---------------------------------------------------------------------------------------------------------------- the checks

def package_files(folder):
    folder = Path(folder)
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file())


def check_manifest(folder):
    """The problems of a built package against its own manifest (an empty list when it is whole)."""
    folder = Path(folder)
    problems = []
    if any(p.name == '.git' for p in folder.rglob('*')):
        problems.append('the package holds a .git entry')
    try:
        manifest = json.loads((folder / MANIFEST).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        return problems + ['no readable %s: %s' % (MANIFEST, error)]
    claimed = dict(manifest)
    stated = claimed.pop('packageSha256', None)
    if stated != sha256(canonical(claimed)):
        problems.append('packageSha256 does not match the manifest')
    listed = {entry['path']: entry for entry in manifest.get('files', [])}
    present = set(package_files(folder)) - {MANIFEST}
    for path in sorted(present - set(listed)):
        problems.append('not in the manifest: %s' % path)
    for path in sorted(set(listed) - present):
        problems.append('missing: %s' % path)
    for path in sorted(present & set(listed)):
        data = (folder / path).read_bytes()
        if sha256(data) != listed[path]['sha256'] or len(data) != listed[path]['size']:
            problems.append('changed: %s' % path)
    return problems


def questions(root=ROOT):
    """The question texts of corpus 2 (pool, ambiguity, development set and any drawn task) and of study 1 (tasks and development set)."""
    out = []
    for name in ('study/corpus2/pool.json', 'study/corpus2/ambiguity.json', 'study/corpus2/dev.json', 'study/corpus2/tasks.json',
                 'study/corpus/tasks.json', 'study/corpus/dev.json'):
        data = json.loads((Path(root) / name).read_text(encoding='utf-8'))
        out += [task['question'] for task in data.get('tasks', []) if task.get('question')]
    return out


def task_ids(root=ROOT):
    """The task ids of corpus 2."""
    ids = set()
    for name in ('study/corpus2/pool.json', 'study/corpus2/ambiguity.json', 'study/corpus2/dev.json', 'study/corpus2/tasks.json'):
        data = json.loads((Path(root) / name).read_text(encoding='utf-8'))
        ids |= {task['id'] for task in data.get('tasks', []) if task.get('id')}
    return sorted(ids)


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip()


def fragments(question):
    """The question, and its 10-word windows of at least 50 characters taken every 5 words (as test_corpus2.py does)."""
    out = {normalized(question)}
    words = question.split()
    for start in range(0, max(1, len(words) - 9), 5):
        fragment = ' '.join(words[start:start + 10])
        if len(fragment) >= 50:
            out.add(fragment)
    return out


def walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


def leaks(name, folder, root=ROOT):
    """The leak findings of decision I5 for one built package (an empty list when there is none).

    guide:  (a) no file under an excluded path, nor any lab file under study/; (b) no corpus 2 or study 1 question, exact or
            whitespace-normalized, nor a 10-word fragment of one; (c) no corpus 2 task id as a word.
    keys-b: (d) no `expected` key in a corpus 2 JSON file (the released data's own curation files may hold that word); no file under an
            excluded path; no file whose bytes are those of an excluded file.
    """
    folder, root = Path(folder), Path(root)
    definition = load_definitions(WorkingSource(root))['packages'][name]
    paths = [p for p in package_files(folder) if p != MANIFEST]
    found = []
    for path in paths:
        for prefix in definition['excluded']:
            if under(path, prefix):
                found.append('(a) %s is under the excluded path %s' % (path, prefix))
    if name == 'guide':
        found += ['(a) %s is a lab file under study/' % p for p in paths if p.startswith('study/')]
        texts = {p: normalized((folder / p).read_bytes().decode('utf-8', 'replace')) for p in paths}
        for question in questions(root):
            for fragment in fragments(question):
                for path, text in texts.items():
                    if fragment in text:
                        found.append('(b) %s holds question text: %r' % (path, fragment[:80]))
        for task_id in task_ids(root):
            word = re.compile(r'(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])' % re.escape(task_id))
            for path, text in texts.items():
                if word.search(text):
                    found.append('(c) %s names the corpus 2 task id %s' % (path, task_id))
    else:
        forbidden = {}
        for prefix in definition['excluded']:
            for path in (WorkingSource(root).files_under(prefix) if prefix.endswith('/') else [prefix]):
                forbidden[sha256((root / path).read_bytes())] = path
        for path in paths:
            data = (folder / path).read_bytes()
            if sha256(data) in forbidden:
                found.append('(d) %s has the bytes of %s' % (path, forbidden[sha256(data)]))
            if path.startswith(CORPUS2) and path.endswith('.json') and 'expected' in set(walk_keys(json.loads(data.decode('utf-8')))):
                found.append('(d) %s holds an expected entry' % path)
    return sorted(set(found))


def verify(folder, root=ROOT):
    folder = Path(folder)
    problems = check_manifest(folder)
    if problems:
        return None, problems
    manifest = json.loads((folder / MANIFEST).read_text(encoding='utf-8'))
    return manifest, leaks(manifest['package'], folder, root)


# ------------------------------------------------------------------------------------------------------------------ the command

def main(argv=None, out=print):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build', help='build one package from a lab commit into a new folder outside any Git work tree')
    b.add_argument('package', choices=PACKAGES)
    b.add_argument('--commit', required=True, help='the full id of the lab commit to build from')
    b.add_argument('--output', required=True, help='a new or empty folder outside every Git work tree')
    v = sub.add_parser('verify', help='check a built package against its manifest and run the leak checks')
    v.add_argument('folder')
    li = sub.add_parser('list', help='print the files a package would hold')
    li.add_argument('package', choices=PACKAGES)
    li.add_argument('--commit', help='the full id of a lab commit (default: the working tree)')
    args = parser.parse_args(argv)
    try:
        if args.command == 'build':
            manifest = build(args.package, args.commit, args.output)
            _, found = verify(args.output)
            out(json.dumps({'package': manifest['package'], 'labCommit': manifest['labCommit'], 'files': len(manifest['files']),
                            'packageSha256': manifest['packageSha256'],
                            'manifestFileSha256': sha256((Path(args.output) / MANIFEST).read_bytes()), 'leaks': found}, indent=2))
            return 1 if found else 0
        if args.command == 'verify':
            manifest, found = verify(args.folder)
            out(json.dumps({'package': manifest and manifest['package'], 'labCommit': manifest and manifest['labCommit'],
                            'packageSha256': manifest and manifest['packageSha256'], 'problems': found}, indent=2))
            return 1 if found else 0
        source = GitSource(args.commit) if args.commit else WorkingSource()
        for path, entry in sorted(plan(source, args.package).items()):
            out('%s  %s' % (entry['source'], path))
        return 0
    except Refused as error:
        print('blind.py: refused: %s' % error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
