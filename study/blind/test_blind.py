"""The tests of the blind workers' packages: the leak checks of decision I5 and the builder. Offline: no stack, no API key.

- (a) The guide package holds no file under the excluded paths and no lab file under study/.
- (b) No corpus 2 or study 1 question text is anywhere in the guide package, exact, whitespace-normalized or as a 10-word fragment.
- (c) No corpus 2 task id is in the guide package.
- (d) The keys B package holds no expected entry and nothing of keys-a.json, derive_a.py, expected.json or reference/, and a rebuild from
  the same source gives the same manifest hash and the same bytes.
- Each check catches a planted leak; the manifest check catches a changed, added or missing file and a .git entry; the builder refuses
  an output inside a Git work tree, a folder that is not empty and a commit whose blind.py is not this one.

The packages are built from the working tree (the files Git tracks or would track), so the checks judge the definitions and the lab files
as they stand. The build from a commit is checked against HEAD.
"""
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

    def test_neither_package_leaks(self):
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
