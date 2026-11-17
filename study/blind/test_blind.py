"""The tests of the blind workers' packages: the leak checks of decision I5 and the builder. Offline: no stack, no API key.

- (a) The guide package holds no file under the excluded paths and no lab file under study/.
- (b) No corpus 2 or study 1 question text is anywhere in the guide package, exact, whitespace-normalized or as a 10-word fragment.
- (c) No corpus 2 task id is in the guide package.
- (d) The keys B package holds no expected entry and nothing of keys-a.json, derive_a.py, expected.json or reference/, and a rebuild from
  the same source gives the same manifest hash and the same bytes.
- Each check catches a planted leak; the manifest check catches a changed, added or missing file and a .git entry; the builder refuses
  an output inside a Git work tree, a folder that is not empty and a commit whose blind.py is not this one.
- Study 3's keys B package (keys-b3, the Job study3_blind_inputs): (a) nothing of either derivation A of corpus 2 or 3 (derive_a.py,
  derive_a3.py, keys-a.json, expected.json, reference/), by path or by bytes; (b) exactly the 31 ids of newTaskIds in the tasks and the
  schemas, each record (without its designNote) and schema the lab's own JSON value, and no carried, ambiguity or development question
  (exact, whitespace-normalized or a 10-word fragment starting at any word) in any file or the manifest, outside the new questions
  themselves, whose shared wording is pinned; (c) no expected, directions or designNote entry; (d) a rebuild gives the same package hash
  (with the other packages).
- The rewrites: select keeps exactly the named entries of a list or a map, in the file's order, and refuses a missing or doubled id and a
  file that does not round-trip; drop still writes what it wrote for study 2's package; study 2's two definitions are unchanged.

The packages are built from the working tree (the files Git tracks or would track), so the checks judge the definitions and the lab files
as they stand. The build from a commit is checked against HEAD.
"""
import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import blind

ROOT = blind.ROOT


def build(name, folder):
    return blind.write_package(name, blind.WorkingSource(), folder)


class Packages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name)
        if blind.inside_git_work_tree(cls.base):
            raise unittest.SkipTest('the temporary folder %s is inside a Git work tree' % cls.base)
        cls.manifests = {name: build(name, cls.base / name) for name in blind.PACKAGES}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copy(self, name):
        target = Path(tempfile.mkdtemp(dir=self.base))
        shutil.copytree(self.base / name, target / name)
        return target / name

    def files(self, name):
        return [p for p in blind.package_files(self.base / name) if p != blind.MANIFEST]

    # ------------------------------------------------------------------------------------------- the leak checks on the packages

    def test_no_package_leaks(self):
        for name in blind.PACKAGES:
            with self.subTest(package=name):
                self.assertEqual(blind.check_manifest(self.base / name), [])
                self.assertEqual(blind.leaks(name, self.base / name), [])

    def test_a_the_guide_holds_nothing_under_the_excluded_paths_nor_under_study(self):
        definition = blind.load_definitions(blind.WorkingSource())['packages']['guide']
        for path in self.files('guide'):
            self.assertFalse(path.startswith('study/'), path)
            for prefix in definition['excluded']:
                self.assertFalse(blind.under(path, prefix), path)
        for prefix in ('study/corpus/', 'study/corpus2/', 'study/evidence/', 'study/guide/', 'docs/agent-study/', 'docs/AGENT-STUDY-REPORT.md'):
            self.assertIn(prefix, definition['excluded'])

    def test_b_no_question_text_is_in_the_guide_exact_or_whitespace_normalized(self):
        text = {p: blind.normalized((self.base / 'guide' / p).read_bytes().decode('utf-8', 'replace')) for p in self.files('guide')}
        questions = blind.questions()
        self.assertGreater(len(questions), 100)
        for question in questions:
            for path, body in text.items():
                self.assertNotIn(blind.normalized(question), body, path)

    def test_c_no_corpus2_task_id_is_in_the_guide(self):
        ids = blind.task_ids()
        self.assertGreater(len(ids), 80)
        for path in self.files('guide'):
            body = (self.base / 'guide' / path).read_bytes().decode('utf-8', 'replace')
            for task_id in ids:
                self.assertIsNone(re.search(r'(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])' % re.escape(task_id), body), (path, task_id))

    def test_d_keys_b_holds_no_expected_entry_and_nothing_of_the_first_derivation(self):
        files = self.files('keys-b')
        for path in files:
            self.assertFalse(path.startswith('study/corpus2/reference/'), path)
            self.assertNotIn(path, ('study/corpus2/keys-a.json', 'study/corpus2/derive_a.py', 'study/corpus2/expected.json'))
        forbidden = {blind.sha256((ROOT / p).read_bytes()) for p in ('study/corpus2/keys-a.json', 'study/corpus2/derive_a.py',
                                                                      'study/corpus2/expected.json')}
        forbidden |= {blind.sha256((ROOT / p).read_bytes()) for p in blind.WorkingSource().files_under('study/corpus2/reference/')}
        for path in files:
            self.assertNotIn(blind.sha256((self.base / 'keys-b' / path).read_bytes()), forbidden, path)
        dev = json.loads((self.base / 'keys-b' / 'study/corpus2/dev.json').read_text(encoding='utf-8'))
        self.assertEqual(sum('expected' in task for task in dev['tasks']), 0)

    def test_d_the_rewrite_of_dev_json_drops_the_expected_entries_and_nothing_else(self):
        original = json.loads((ROOT / 'study/corpus2/dev.json').read_text(encoding='utf-8'))
        rewritten = json.loads((self.base / 'keys-b' / 'study/corpus2/dev.json').read_text(encoding='utf-8'))
        for task in original['tasks']:
            self.assertIn('expected', task)
            del task['expected']
        self.assertEqual(rewritten, original)
        entry = next(e for e in self.manifests['keys-b']['files'] if e['path'] == 'study/corpus2/dev.json')
        self.assertEqual(entry['source'], 'rewritten')
        self.assertEqual(entry['rewrite']['removed'], len(original['tasks']))
        self.assertEqual(entry['labSha256'], blind.sha256((ROOT / 'study/corpus2/dev.json').read_bytes()))

    def test_d_a_rebuild_gives_the_same_manifest_hash_and_the_same_bytes(self):
        for name in blind.PACKAGES:
            with self.subTest(package=name):
                again = Path(tempfile.mkdtemp(dir=self.base)) / name
                manifest = build(name, again)
                self.assertEqual(manifest['packageSha256'], self.manifests[name]['packageSha256'])
                self.assertEqual(blind.package_files(again), blind.package_files(self.base / name))
                for path in blind.package_files(again):
                    self.assertEqual((again / path).read_bytes(), (self.base / name / path).read_bytes(), path)

    # ------------------------------------------------------------------------------------------- the checks catch planted leaks

    def test_the_checks_catch_planted_question_text_and_task_ids(self):
        question = json.loads((ROOT / 'study/corpus2/pool.json').read_text(encoding='utf-8'))['tasks'][0]
        study1 = json.loads((ROOT / 'study/corpus/tasks.json').read_text(encoding='utf-8'))['tasks'][0]['question']
        for planted, mark in ((question['question'], '(b)'), ('  \n'.join(question['question'].split(' ')), '(b)'),
                              (study1, '(b)'), ('see %s.' % question['id'], '(c)')):
            with self.subTest(planted=planted[:40]):
                folder = self.copy('guide')
                with open(folder / 'docs/PERSONNEL-V2.md', 'a', encoding='utf-8', newline='\n') as handle:
                    handle.write('\n' + planted + '\n')
                self.assertTrue(any(f.startswith(mark) for f in blind.leaks('guide', folder)), planted)

    def test_the_checks_catch_planted_files(self):
        folder = self.copy('guide')
        (folder / 'study/corpus2').mkdir(parents=True)
        (folder / 'study/corpus2/notes.txt').write_text('x', encoding='utf-8')
        found = blind.leaks('guide', folder)
        self.assertTrue(any('excluded path study/corpus2/' in f for f in found), found)
        self.assertTrue(any('lab file under study/' in f for f in found), found)
        keys = self.copy('keys-b')
        shutil.copy(ROOT / 'study/corpus2/keys-a.json', keys / 'study/corpus2/renamed.json')
        shutil.copy(ROOT / 'study/corpus2/dev.json', keys / 'study/corpus2/dev.json')
        found = blind.leaks('keys-b', keys)
        self.assertTrue(any('has the bytes of study/corpus2/keys-a.json' in f for f in found), found)
        self.assertTrue(any('dev.json holds an expected entry' in f for f in found), found)

    def test_the_manifest_check_catches_a_changed_an_added_and_a_missing_file_and_a_git_entry(self):
        folder = self.copy('guide')
        (folder / 'docs/PERSONNEL-V2.md').write_bytes(b'changed\n')
        (folder / 'extra.md').write_bytes(b'extra\n')
        (folder / 'TOOLS.md').unlink()
        (folder / '.git').mkdir()
        (folder / '.git' / 'HEAD').write_bytes(b'ref: refs/heads/main\n')
        problems = blind.check_manifest(folder)
        for expected in ('changed: docs/PERSONNEL-V2.md', 'not in the manifest: extra.md', 'missing: TOOLS.md', 'the package holds a .git entry'):
            self.assertIn(expected, problems)
        manifest = json.loads((folder / blind.MANIFEST).read_text(encoding='utf-8'))
        manifest['labCommit'] = '0' * 40
        (folder / blind.MANIFEST).write_text(json.dumps(manifest), encoding='utf-8')
        self.assertIn('packageSha256 does not match the manifest', blind.check_manifest(folder))

    # ------------------------------------------------------------------------------------------------------- what the packages hold

    def test_the_packages_hold_their_definitions_and_the_manifest_says_how_each_file_was_made(self):
        definitions = blind.load_definitions(blind.WorkingSource())
        for name in blind.PACKAGES:
            files = self.files(name)
            for item in definitions['packages'][name]['include']:
                if 'path' in item:
                    self.assertIn(item['path'], files)
                else:
                    self.assertTrue(any(p.startswith(item['dir']) for p in files), item['dir'])
            manifest = self.manifests[name]
            self.assertEqual(sorted(e['path'] for e in manifest['files']), files)
            self.assertEqual(manifest['builder']['version'], blind.VERSION)
            for entry in manifest['files']:
                if entry['source'] == 'lab':
                    self.assertEqual(entry['sha256'], blind.sha256((ROOT / entry['path']).read_bytes()), entry['path'])
                    self.assertEqual(entry['sha256'], entry['labSha256'])
        self.assertEqual({e['path']: e['source'] for e in self.manifests['guide']['files'] if e['source'] != 'lab'},
                         {'README.md': 'readme', 'TOOLS.md': 'derived'})

    def test_nothing_considered_and_left_out_is_in_the_guide(self):
        definitions = blind.load_definitions(blind.WorkingSource())
        files = self.files('guide')
        for item in definitions['considered']:
            if item['package'] != 'guide':
                continue
            pattern = re.escape(item['path']).replace(r'\*', '[^/]+')
            self.assertFalse([p for p in files if re.match(pattern, p)], item['path'])

    def test_the_guide_readme_says_nothing_of_the_arms_or_the_hypotheses(self):
        text = (self.base / 'guide' / blind.README).read_text(encoding='utf-8')
        for word in ('Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'arm', 'arms', 'hypothesis', 'hypotheses', 'Guided Direct Access',
                     'GraphQL', 'router', 'adapter', 'study 1', 'corpus', 'answer key', 'compared'):
            self.assertIsNone(re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(word), text, re.IGNORECASE), word)
        self.assertIsNone(re.search(r'federation(?!/mapping-releases)', text, re.IGNORECASE))
        self.assertIn('No task-specific hints.', text)
        self.assertIn('relay/round-001.requests.json', text)

    def test_the_tool_texts_are_the_sources_own(self):
        tools = (self.base / 'guide' / 'TOOLS.md').read_text(encoding='utf-8')
        raw = blind.raw_server_tools((ROOT / 'study/mcp/raw_server.py').read_text(encoding='utf-8'))
        self.assertEqual([t['name'] for t in raw], ['http_request', 'soap_request', 'read_mapping_release'])
        for tool in raw:
            self.assertIn(tool['description'], tools)
            for p in tool['parameters']:
                self.assertIn(p['description'], tools)
        import sys
        sys.path.insert(0, str(ROOT / 'study' / 'harness'))
        import harness_tools
        self.assertEqual(blind.harness_tools((ROOT / 'study/harness/harness_tools.py').read_text(encoding='utf-8')),
                         [harness_tools.TOOLS[n] for n in harness_tools.NAMES])
        readme = (ROOT / 'study/mcp/README.md').read_text(encoding='utf-8')
        for heading in ('What each tool does', 'The sandbox'):
            body = blind.markdown_section(readme, heading).split('\n', 1)[1]
            self.assertIn(body.strip(), tools)

    # ------------------------------------------------------------------------------------------- study 3's keys B package (keys-b3)

    FIRST_DERIVATIONS = ('study/corpus2/derive_a.py', 'study/corpus2/keys-a.json', 'study/corpus2/expected.json',
                         'study/corpus3/derive_a3.py', 'study/corpus3/keys-a.json', 'study/corpus3/expected.json')
    REFERENCES = ('study/corpus2/reference/', 'study/corpus3/reference/')

    def b3(self, path):
        return json.loads((self.base / 'keys-b3' / path).read_text(encoding='utf-8'))

    def test_b3_a_holds_nothing_of_either_first_derivation_by_path_or_by_bytes(self):
        excluded = blind.load_definitions(blind.WorkingSource())['packages']['keys-b3']['excluded']
        for path in self.FIRST_DERIVATIONS + self.REFERENCES + ('study/corpus2/dev.json', 'study/corpus3/dev.json'):
            self.assertIn(path, excluded)
        forbidden = {blind.sha256((ROOT / p).read_bytes()): p for p in self.FIRST_DERIVATIONS}
        for folder in self.REFERENCES:
            files = blind.WorkingSource().files_under(folder)
            self.assertTrue(files, folder)
            forbidden.update({blind.sha256((ROOT / p).read_bytes()): p for p in files})
        for path in self.files('keys-b3'):
            self.assertNotIn(path, self.FIRST_DERIVATIONS, path)
            self.assertFalse(any(path.startswith(folder) for folder in self.REFERENCES), path)
            self.assertNotIn(blind.sha256((self.base / 'keys-b3' / path).read_bytes()), forbidden, path)

    def test_b3_b_holds_exactly_the_new_tasks_as_the_lab_holds_them(self):
        new = json.loads((ROOT / 'study/corpus3/corpus-manifest.json').read_text(encoding='utf-8'))['newTaskIds']
        self.assertEqual(len(new), 31)
        self.assertEqual(blind.new_task_ids(), new)
        lab_tasks = json.loads((ROOT / 'study/corpus3/tasks.json').read_text(encoding='utf-8'))
        lab_schemas = json.loads((ROOT / 'study/corpus3/schemas.json').read_text(encoding='utf-8'))
        tasks, schemas = self.b3('study/corpus3/tasks.json'), self.b3('study/corpus3/schemas.json')
        self.assertEqual(sorted(t['id'] for t in tasks['tasks']), sorted(new))
        self.assertEqual(sorted(schemas['schemas']), sorted(new))
        lab_new = [t for t in lab_tasks['tasks'] if t['id'] in new]
        self.assertTrue(any('designNote' in t for t in lab_new))
        self.assertEqual(tasks['tasks'], [{k: v for k, v in t.items() if k != 'designNote'} for t in lab_new])
        self.assertEqual(schemas['schemas'], {k: v for k, v in lab_schemas['schemas'].items() if k in new})
        self.assertEqual(list(tasks), [k for k in lab_tasks if k != 'directions'])
        self.assertEqual({k: v for k, v in tasks.items() if k != 'tasks'}, {k: v for k, v in lab_tasks.items() if k not in ('tasks', 'directions')})
        self.assertEqual({k: v for k, v in schemas.items() if k != 'schemas'}, {k: v for k, v in lab_schemas.items() if k != 'schemas'})
        for path in ('study/corpus3/tasks.json', 'study/corpus3/schemas.json'):
            self.assertEqual((self.base / 'keys-b3' / path).read_bytes(), blind.json_bytes(self.b3(path)), path)

    def test_b3_b_no_question_of_a_task_that_is_not_new_is_in_it(self):
        others = blind.other_questions()
        self.assertGreater(len(others), 150)
        new = set(blind.new_task_ids())
        for name in ('study/corpus3/tasks.json', 'study/corpus3/dev.json', 'study/corpus2/pool.json', 'study/corpus2/ambiguity.json'):
            for task in json.loads((ROOT / name).read_text(encoding='utf-8'))['tasks']:
                if task['id'] not in new:
                    self.assertIn(task['question'], others, (name, task['id']))
        texts = {p: blind.normalized((self.base / 'keys-b3' / p).read_bytes().decode('utf-8', 'replace')) for p in self.files('keys-b3')}
        for question in others:
            for path, body in texts.items():
                self.assertNotIn(blind.normalized(question), body, path)

    def test_b3_c_holds_no_expected_no_directions_and_no_design_note_entry(self):
        for path in self.files('keys-b3'):
            if path.startswith('study/') and path.endswith('.json'):
                keys = set(blind.walk_keys(self.b3(path)))
                for key in ('expected', 'directions', 'designNote'):
                    self.assertNotIn(key, keys, path)

    def test_b3_b_the_wording_new_questions_share_with_other_questions_is_pinned(self):
        # a 10-word fragment of these other tasks' questions lies inside these new questions; the scan cuts the new questions out
        self.assertEqual(blind.shared_fragments(), [('B26', 'V06'), ('E23', 'E13'), ('E25', 'E13')])

    def test_the_scan_text_unwraps_escaped_line_breaks_and_decodes_json_strings(self):
        question = 'one two three four five six seven eight nine ten eleven twelve'
        wrapped = question.replace('five ', 'five\n')
        for path, data in (('m.json', blind.json_bytes({'why': wrapped})), ('m.json', blind.json_bytes({'lines': wrapped.split('\n')})),
                           ('x.py', ('text = %r\n' % wrapped).encode('utf-8'))):
            with self.subTest(path=path, data=data[:30]):
                self.assertIn(question, blind.scan_text(path, data))

    def test_fragments_start_at_every_word(self):
        words = ['word%02d' % i for i in range(14)]
        found = blind.fragments(' '.join(words))
        for start in range(5):
            self.assertIn(' '.join(words[start:start + 10]), found)
        self.assertEqual(len(found), 6)

    def test_b3_holds_study_2s_keys_b_files_byte_for_byte_and_nothing_else_of_corpus_2(self):
        files = self.files('keys-b3')
        for path in ('study/corpus2/derive_b.py', 'study/corpus2/test_derive_b.py'):
            self.assertEqual((self.base / 'keys-b3' / path).read_bytes(), (ROOT / path).read_bytes(), path)
        self.assertEqual([p for p in files if p.startswith('study/')],
                         ['study/corpus2/derive_b.py', 'study/corpus2/test_derive_b.py', 'study/corpus3/schemas.json', 'study/corpus3/tasks.json'])

    def test_b3_the_manifest_records_each_rewrite_with_the_hashes_of_its_sources(self):
        entries = {e['path']: e for e in self.manifests['keys-b3']['files']}
        listed = blind.sha256((ROOT / 'study/corpus3/corpus-manifest.json').read_bytes())
        new = blind.new_task_ids()
        tasks, schemas = entries['study/corpus3/tasks.json'], entries['study/corpus3/schemas.json']
        self.assertEqual(tasks['labSha256'], blind.sha256((ROOT / 'study/corpus3/tasks.json').read_bytes()))
        self.assertEqual(schemas['labSha256'], blind.sha256((ROOT / 'study/corpus3/schemas.json').read_bytes()))
        select, drop, note = tasks['rewrite']
        self.assertEqual(select['select'], {'path': 'study/corpus3/corpus-manifest.json', 'list': 'newTaskIds', 'labSha256': listed})
        self.assertEqual((select['from'], sorted(select['kept']), select['removed']), ('tasks', sorted(new), 113 - 31))
        self.assertEqual((drop['drop'], drop['removed']), ('directions', 1))
        self.assertNotIn('from', drop)
        self.assertEqual((note['drop'], note['from']), ('designNote', 'tasks'))
        self.assertEqual(note['removed'], sum('designNote' in t for t in json.loads(
            (ROOT / 'study/corpus3/tasks.json').read_text(encoding='utf-8'))['tasks'] if t['id'] in new))
        self.assertEqual(schemas['rewrite']['select']['labSha256'], listed)
        self.assertEqual((schemas['rewrite']['from'], sorted(schemas['rewrite']['kept']), schemas['rewrite']['removed']),
                         ('schemas', sorted(new), 113 - 31))
        self.assertEqual({p: e['source'] for p, e in entries.items() if e['source'] != 'lab'},
                         {'README.md': 'readme', 'study/corpus3/tasks.json': 'rewritten', 'study/corpus3/schemas.json': 'rewritten'})

    def test_b3_the_readme_names_what_is_here_and_what_was_left_out(self):
        text = (self.base / 'keys-b3' / blind.README).read_text(encoding='utf-8')
        for word in ('study/corpus3/tasks.json', 'study/corpus3/schemas.json', 'study/corpus2/derive_b.py', 'study/corpus2/test_derive_b.py',
                     'federation/mapping-releases/', 'personnel-v2-large-004', 'directions', 'keys-a.json', 'expected.json', 'derive_a3.py',
                     'reference/', 'designNote', 'The new tasks are all you get.'):
            self.assertIn(word, text)
        self.assertNotIn('{commit}', text)

    def test_b3_the_checks_catch_planted_leaks(self):
        lab_tasks = json.loads((ROOT / 'study/corpus3/tasks.json').read_text(encoding='utf-8'))
        new = set(blind.new_task_ids())
        carried = next(t for t in lab_tasks['tasks'] if t['id'] not in new)
        folder = self.copy('keys-b3')
        tasks = json.loads((folder / 'study/corpus3/tasks.json').read_text(encoding='utf-8'))
        tasks['tasks'].append(carried)
        tasks['directions'] = {}
        tasks['tasks'][0]['expected'] = 1
        tasks['tasks'][1]['designNote'] = 'x'
        (folder / 'study/corpus3/tasks.json').write_bytes(blind.json_bytes(tasks))
        with open(folder / blind.README, 'a', encoding='utf-8', newline='\n') as handle:
            handle.write('\n' + '  \n'.join(carried['question'].split(' ')) + '\n')
        shutil.copy(ROOT / 'study/corpus3/keys-a.json', folder / 'study/corpus3/renamed.json')
        (folder / 'study/corpus3/reference').mkdir()
        (folder / 'study/corpus3/reference/x.py').write_text('x', encoding='utf-8')
        found = blind.leaks('keys-b3', folder)
        for mark in ('(a) study/corpus3/renamed.json has the bytes of study/corpus3/keys-a.json',
                     '(a) study/corpus3/reference/x.py is under the excluded path study/corpus3/reference/',
                     '(b) study/corpus3/tasks.json holds the ids', '(b) README.md holds question text',
                     '(b) study/corpus3/tasks.json holds question text', '(c) study/corpus3/tasks.json holds an expected entry',
                     '(c) study/corpus3/tasks.json holds a directions entry', '(c) study/corpus3/tasks.json holds a designNote entry'):
            self.assertTrue(any(f.startswith(mark) for f in found), (mark, found))
        # a question planted in the manifest's copied texts, and a 10-word window that starts off the five-word grid
        dev = json.loads((ROOT / 'study/corpus3/dev.json').read_text(encoding='utf-8'))['tasks'][0]['question']
        words = next(t['question'] for t in lab_tasks['tasks'] if t['id'] not in new and len(t['question'].split()) > 14).split()
        window = next(' '.join(words[i:i + 10]) for i in range(1, len(words) - 9) if i % 5 and len(' '.join(words[i:i + 10])) >= 50)
        wrapped = ' '.join(words[:5]) + '\n' + ' '.join(words[5:])
        for planted, where in ((dev, blind.MANIFEST), (wrapped, blind.MANIFEST), (window, blind.README)):
            with self.subTest(where=where, wrapped='\n' in planted):
                folder = self.copy('keys-b3')
                if where == blind.MANIFEST:
                    manifest = json.loads((folder / blind.MANIFEST).read_text(encoding='utf-8'))
                    manifest['files'][0]['note'] = planted
                    (folder / blind.MANIFEST).write_bytes(blind.json_bytes(manifest))
                else:
                    with open(folder / where, 'a', encoding='utf-8', newline='\n') as handle:
                        handle.write('\n' + planted + '\n')
                found = blind.leaks('keys-b3', folder)
                self.assertTrue(any(f.startswith('(b) %s holds question text' % where) for f in found), found)
        guide = self.copy('guide')
        manifest = json.loads((guide / blind.MANIFEST).read_text(encoding='utf-8'))
        manifest['files'][0]['note'] = dev
        (guide / blind.MANIFEST).write_bytes(blind.json_bytes(manifest))
        self.assertTrue(any(f.startswith('(b) MANIFEST.json holds question text') for f in blind.leaks('guide', guide)))
        schemas_gone = self.copy('keys-b3')
        (schemas_gone / 'study/corpus3/schemas.json').unlink()
        self.assertIn('(b) study/corpus3/schemas.json is missing', blind.leaks('keys-b3', schemas_gone))


class Rewrites(unittest.TestCase):
    STUDY2_COMMIT = '6c18afa638ce583dcd79125177ba9a210f5a3686'
    STUDY2_DEV_SHA256 = 'd1a7879367f697a064551db01524185dd2c0bf535371fc2dd0010274fd5bbb7e'

    def test_drop_still_writes_what_it_wrote_for_study_2s_package(self):
        # study 2's keys-b package, built from STUDY2_COMMIT, holds study/corpus2/dev.json with this SHA-256 and 15400 bytes
        original = blind.GitSource(self.STUDY2_COMMIT).read('study/corpus2/dev.json')
        data, removed = blind.drop_key(original, 'expected', 'tasks', 'study/corpus2/dev.json')
        self.assertEqual((hashlib.sha256(data).hexdigest(), len(data), removed), (self.STUDY2_DEV_SHA256, 15400, 8))
        manifest = blind.manifest_of('keys-b', blind.WorkingSource(), blind.plan(blind.WorkingSource(), 'keys-b'))
        entry = next(e for e in manifest['files'] if e['path'] == 'study/corpus2/dev.json')
        self.assertEqual(sorted(entry['rewrite']), ['drop', 'from', 'removed', 'why'])

    def test_study_2s_two_definitions_are_unchanged(self):
        before = json.loads(blind.GitSource(self.STUDY2_COMMIT).read(blind.DEFINITIONS).decode('utf-8'))
        now = blind.load_definitions(blind.WorkingSource())
        for name in ('guide', 'keys-b'):
            self.assertEqual(now['packages'][name], before['packages'][name], name)
        self.assertEqual([c for c in now['considered'] if c['package'] != 'keys-b3'], before['considered'])

    def test_drop_without_from_removes_one_top_level_key(self):
        data = blind.json_bytes({'about': 'a', 'directions': {'x': 1}, 'tasks': []})
        self.assertEqual(blind.drop_key(data, 'directions', None, 'f.json'), (blind.json_bytes({'about': 'a', 'tasks': []}), 1))
        with self.assertRaises(blind.Refused):
            blind.drop_key(data, 'missing', None, 'f.json')

    def test_select_keeps_exactly_the_named_entries_of_a_list_or_a_map_in_the_files_order(self):
        listed = blind.json_bytes({'tasks': [{'id': 'A', 'q': 1}, {'id': 'B', 'q': [2]}, {'id': 'C', 'q': {'r': 3}}], 'x': 'y'})
        data, kept, removed = blind.select_ids(listed, ['C', 'A'], 'tasks', 'f.json')
        self.assertEqual(json.loads(data), {'tasks': [{'id': 'A', 'q': 1}, {'id': 'C', 'q': {'r': 3}}], 'x': 'y'})
        self.assertEqual((kept, removed), (['A', 'C'], 1))
        mapped = blind.json_bytes({'schemas': {'A': {'t': 1}, 'B': {}, 'C': []}})
        data, kept, removed = blind.select_ids(mapped, ['B', 'C'], 'schemas', 'f.json')
        self.assertEqual(json.loads(data), {'schemas': {'B': {}, 'C': []}})
        self.assertEqual((kept, removed), (['B', 'C'], 1))

    def test_select_refuses_a_missing_or_doubled_id_and_a_file_that_does_not_round_trip(self):
        listed = blind.json_bytes({'tasks': [{'id': 'A'}, {'id': 'B'}]})
        for args in ((listed, ['A', 'Z'], 'tasks'), (blind.json_bytes({'tasks': [{'id': 'A'}, {'id': 'A'}]}), ['A'], 'tasks'),
                     (json.dumps({'tasks': [{'id': 'A'}]}).encode('utf-8'), ['A'], 'tasks'), (listed, ['A'], 'other'),
                     (blind.json_bytes({'tasks': [{'name': 'A'}]}), ['A'], 'tasks')):
            with self.assertRaises(blind.Refused):
                blind.select_ids(args[0], args[1], args[2], 'f.json')
        for bad in ({'ids': []}, {'ids': ['A', 'A']}, {'ids': 'A'}, {'other': ['A']}, {'ids': ['A', '']}):
            with self.assertRaises(blind.Refused):
                blind.id_list(json.dumps(bad).encode('utf-8'), 'ids', 'm.json')
        self.assertEqual(blind.id_list(json.dumps({'ids': ['B', 'A']}).encode('utf-8'), 'ids', 'm.json'), ['B', 'A'])


class Builder(unittest.TestCase):
    def test_an_output_inside_a_git_work_tree_or_not_empty_is_refused(self):
        inside = ROOT / 'study' / 'blind' / 'never-made'
        with self.assertRaises(blind.Refused):
            blind.write_package('guide', blind.WorkingSource(), inside)
        self.assertFalse(inside.exists())
        with tempfile.TemporaryDirectory() as tmp:
            if blind.inside_git_work_tree(tmp):
                self.skipTest('the temporary folder is inside a Git work tree')
            (Path(tmp) / 'x').write_text('x', encoding='utf-8')
            with self.assertRaises(blind.Refused):
                blind.write_package('guide', blind.WorkingSource(), tmp)

    def test_a_commit_is_given_in_full(self):
        for bad in ('abc123', 'HEAD', 'main', ''):
            with self.assertRaises(blind.Refused):
                blind.GitSource(bad)

    def test_the_git_source_reads_the_commit(self):
        head = blind.git(['rev-parse', 'HEAD']).stdout.decode().strip()
        source = blind.GitSource(head)
        self.assertEqual(source.files_under('federation/mapping-releases/'),
                         blind.git(['ls-tree', '-r', '--name-only', head, '--', 'federation/mapping-releases/']).stdout.decode().split())
        for path in ('docs/PERSONNEL-V2.md', 'study/corpus2/dev.json'):
            if blind.git(['diff', '--quiet', 'HEAD', '--', path], check=False).returncode == 0:
                self.assertEqual(blind.lf(source.read(path)), blind.lf((ROOT / path).read_bytes()))

    def test_a_build_from_head_uses_the_builder_of_head_only(self):
        head = blind.git(['rev-parse', 'HEAD']).stdout.decode().strip()
        source = blind.GitSource(head)
        try:
            same = blind.lf(source.read(blind.SELF)) == blind.lf(Path(blind.__file__).read_bytes())
        except blind.Refused:
            same = False
        with tempfile.TemporaryDirectory() as tmp:
            if blind.inside_git_work_tree(tmp):
                self.skipTest('the temporary folder is inside a Git work tree')
            out = Path(tmp) / 'guide'
            if not same:
                with self.assertRaises(blind.Refused):
                    blind.build('guide', head, out)
                self.assertFalse(out.exists())
                return
            manifest = blind.build('guide', head, out)
            self.assertEqual(manifest['labCommit'], head)
            self.assertEqual(blind.check_manifest(out), [])
            again = blind.build('guide', head, Path(tmp) / 'again')
            self.assertEqual(again['packageSha256'], manifest['packageSha256'])


if __name__ == '__main__':
    unittest.main()
