"""Tests of the corpus check (the Job study2_runner_corpus_check): on every start and every resume, before any task is used, the runner checks
each corpus file its task set reads against the hash corpus-manifest.json lists for it, and refuses with STOP and exit 3, writing nothing, on
a file that differs or is not listed. No real model call, no stack, no key: fake stacks and fake vendor clients only."""
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import runner
from fakes import FakeDocker, FakeVendorClient, container, submit
from mcp_client import FakeToolSession
from runner import CorpusRefused, Study, check_corpus, corpus_files, sha256_lf
from study_common import Redactor, sha256_json

STUDY = Path(__file__).resolve().parent.parent
CORPUS1, CORPUS2 = STUDY / 'corpus', STUDY / 'corpus2'
MODELS = {'models': {'model-a': {'vendor': 'va', 'request': {}, 'max_output_tokens': 100}, 'model-b': {'vendor': 'vb', 'request': {}, 'max_output_tokens': 100}}}
PRICES = {'dated': '2026-10-20', 'models': {m: {'input': 2.0, 'cached_read': 0.2, 'cache_write': 2.5, 'output': 10.0} for m in ('model-a', 'model-b')}}
STUB_ID = 'sha256:' + 'a' * 64
PROVENANCE = {'compose_projects': ['lab'], 'backends': {'missions': {'mode': 'simulated', 'service': 'missions-stub', 'image_id': STUB_ID}}}
DRAWN = ('tasks.json', 'schemas.json', 'expected.json')
SUBSET = {'set': 'scored', 'tasks': ['A02', 'A03']}  # two scored tasks of corpus 2; a subset reads the files of its set


class FakeStack:
    def __init__(self, scenario):
        pass

    def start(self):
        pass

    def wait_ready(self, run_id, timeout):
        pass

    def stop_service(self, name):
        pass

    def start_service(self, name):
        pass

    def teardown(self):
        pass


def one_byte_changed(path):
    """Change one byte of a corpus file and keep it valid JSON: the first indenting space becomes a tab."""
    data = path.read_bytes()
    index = data.index(b'\n ') + 1
    path.write_bytes(data[:index] + b'\t' + data[index + 1:])


class CorpusCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'results'

    def copy(self, source):
        """A scratch copy of a committed corpus folder: the manifest, the scorer and the files a task set reads."""
        folder = Path(self.tmp.name) / ('copy-' + source.name)
        folder.mkdir()
        for name in ('corpus-manifest.json', 'scoring.py', 'dev.json') + DRAWN:
            shutil.copy(source / name, folder / name)
        return folder

    def config(self, task_set, **over):
        base = {'scenarios': {'alpha': {'mcp_url': 'x', 'stack': {}, 'warmup_calls': [{'tool': 'lookup', 'arguments': {}}], 'provenance': PROVENANCE}},
                'scenario_order': ['alpha'], 'models': ['model-a', 'model-b'], 'trials': 1, 'seed': 7, 'task_set': task_set,
                'warmup_passes': 1, 'budgets': {'va': {'tokens': 1_000_000}, 'vb': {'tokens': 1_000_000}},
                'limits': {'max_tool_calls': 5, 'retry_backoff_seconds': 0}}
        base.update(over)
        return base

    def study(self, corpus, task_set, run_id='r1', **over):
        def factory(model):
            return FakeVendorClient([lambda s, t, tools: submit({'value': 'blue'})] * 500, max_output_tokens=100, model=model)

        def session(scenario, key):
            return FakeToolSession([{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object'}}], {'lookup': lambda a: 'ok'})
        return Study(self.config(task_set, **over), MODELS, PRICES, run_id, root=self.root, corpus_dir=corpus, client_factory=factory,
                     session_factory=session, stack_factory=FakeStack, redactor=Redactor([]), sleep=lambda s: None,
                     docker=FakeDocker([container('lab', 'missions-stub', 'stub:1', STUB_ID)]))

    def main(self, corpus, task_set, run_id, resume=False):
        """runner.main on a config file naming the corpus, with the fake vendor client of --dry-run: (exit code, what it printed)."""
        path = Path(self.tmp.name) / ('config-%s.json' % run_id)
        config = self.config(task_set, models=['claude-sonnet-5-5', 'gpt-6.1-sol'], corpus_dir=str(corpus),
                             budgets={'anthropic': {'tokens': 1_000_000}, 'openai': {'tokens': 1_000_000}})
        path.write_text(json.dumps(config), encoding='utf-8')
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'LAB_RESULTS_DIR': str(self.root)}), redirect_stdout(out):
            code = runner.main(['--config', str(path), '--run-id', run_id, '--dry-run'] + (['--resume'] if resume else []))
        return code, out.getvalue()

    def written(self):
        """Every file under the results root with its bytes."""
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()} if self.root.exists() else {}

    # ------------------------------------------------------------------ which files a task set reads
    def test_each_task_set_reads_its_own_files(self):
        self.assertEqual(corpus_files('dev'), ('dev.json',))
        self.assertEqual(corpus_files('scored'), DRAWN)
        self.assertEqual(corpus_files({'set': 'dev', 'tasks': ['V05']}), ('dev.json',))
        self.assertEqual(corpus_files(SUBSET), DRAWN)
        self.assertEqual(corpus_files('development'), (), 'an unknown set reads nothing here; load_tasks refuses it')

    # ------------------------------------------------------------------ the committed corpora pass
    def test_the_committed_corpora_pass_on_a_start_and_a_resume(self):
        for number, (corpus, task_set) in enumerate(((CORPUS1, 'dev'), (CORPUS1, 'scored'), (CORPUS2, 'dev'), (CORPUS2, SUBSET))):
            with self.subTest(corpus=corpus.name, task_set=task_set):
                check_corpus(corpus, task_set)
                run_id = 'r%d' % number
                self.assertEqual(self.study(corpus, task_set, run_id).run(), 'complete')
                self.assertEqual(self.study(corpus, task_set, run_id).run(resume=True), 'complete')

    def test_both_manifests_hash_their_files_with_crlf_read_as_lf(self):
        for corpus in (CORPUS1, CORPUS2):
            listed = json.loads((corpus / 'corpus-manifest.json').read_text(encoding='utf-8'))['files']
            for name in ('dev.json',) + DRAWN:
                self.assertEqual(sha256_lf(corpus / name), listed[name], '%s/%s' % (corpus.name, name))

    # ------------------------------------------------------------------ the plan identity is unchanged
    def test_the_plan_hash_of_a_fixed_config_is_unchanged(self):
        # Computed on main at 1bd6bfa, before the check existed: the check adds nothing to the plan identity or corpusFreeze.
        for corpus, task_set, pinned in ((CORPUS1, 'dev', 'a53dcca476b7e00fd96129ac7c31786b74729ec28aefbb2e12e5a41ca0cfe028'),
                                         (CORPUS1, 'scored', 'd0c80de1641116edad82e83ed5adc7f1282cfb266c52df97b84b5501b5233e3f'),
                                         (CORPUS2, SUBSET, '0a4bf9ade786c76e021e8fe34f8628b8cd33ec8f37463af0de0f867db68f0ae1'),
                                         (CORPUS2, 'dev', '086031dc49d8ae51632812b3a43b4fcfd8ac51dd4ed9ce933d1c56fa670a0dd4')):
            with self.subTest(corpus=corpus.name, task_set=task_set):
                self.assertEqual(sha256_json(self.study(corpus, task_set).plan_identity()), pinned)

    # ------------------------------------------------------------------ one byte changed
    def test_one_byte_changed_in_a_file_the_set_reads_stops_a_start_with_nothing_written(self):
        cases = [(CORPUS2, SUBSET, name) for name in DRAWN] + [(CORPUS2, 'dev', 'dev.json'), (CORPUS1, 'scored', 'schemas.json'),
                                                               (CORPUS1, 'dev', 'dev.json')]
        for number, (source, task_set, name) in enumerate(cases):
            with self.subTest(corpus=source.name, file=name):
                corpus = self.copy(source)
                listed = json.loads((corpus / 'corpus-manifest.json').read_text(encoding='utf-8'))['files'][name]
                one_byte_changed(corpus / name)
                code, out = self.main(corpus, task_set, 'start%d' % number)
                self.assertEqual(code, 3)
                self.assertTrue(out.startswith('STOP: The corpus files the task set reads do not match corpus-manifest.json'), out)
                self.assertIn('- %s: the manifest lists %s, the file hashes to %s' % (name, listed, sha256_lf(corpus / name)), out)
                self.assertTrue(out.endswith('Study run start%d: corpus_refused\n' % number), out)
                self.assertEqual(out.count('\n- '), 1, 'only the changed file is named')
                self.assertEqual(self.written(), {}, 'nothing is written')
                shutil.rmtree(corpus)

    def test_one_byte_changed_stops_a_resume_with_nothing_written(self):
        corpus = self.copy(CORPUS2)
        self.assertEqual(self.study(corpus, SUBSET, 'run1').run(), 'complete')
        before = self.written()
        one_byte_changed(corpus / 'schemas.json')
        with self.assertRaises(CorpusRefused) as refused:
            self.study(corpus, SUBSET, 'run1').run(resume=True)
        self.assertEqual(len(refused.exception.problems), 1)
        self.assertTrue(refused.exception.problems[0].startswith('schemas.json: the manifest lists '))
        code, out = self.main(corpus, SUBSET, 'run1', resume=True)
        self.assertEqual(code, 3)
        self.assertIn('- schemas.json: the manifest lists ', out)
        self.assertTrue(out.endswith('Study run run1: corpus_refused\n'), out)
        self.assertEqual(self.written(), before, 'the run folder is unchanged: no resumes.jsonl, no record, no bundle')
        self.assertFalse((self.root / 'run1' / 'resumes.jsonl').exists())

    def test_every_changed_file_is_named(self):
        corpus = self.copy(CORPUS2)
        for name in DRAWN:
            one_byte_changed(corpus / name)
        with self.assertRaises(CorpusRefused) as refused:
            check_corpus(corpus, 'scored')
        self.assertEqual([p.split(':')[0] for p in refused.exception.problems], list(DRAWN))
        check_corpus(corpus, 'dev')  # the dev set reads none of them

    # ------------------------------------------------------------------ a file the manifest does not list, or that is missing
    def test_a_file_the_manifest_does_not_list_stops_the_run(self):
        corpus = self.copy(CORPUS2)
        path = corpus / 'corpus-manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        del manifest['files']['expected.json']
        path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        code, out = self.main(corpus, SUBSET, 'unlisted')
        self.assertEqual(code, 3)
        self.assertIn('- expected.json is not listed in the manifest\'s files (the file hashes to %s)' % sha256_lf(corpus / 'expected.json'), out)
        self.assertTrue(out.endswith('Study run unlisted: corpus_refused\n'), out)
        self.assertEqual(self.written(), {})

    def test_a_manifest_without_files_or_unreadable_and_a_missing_file_are_refused(self):
        corpus = self.copy(CORPUS1)
        (corpus / 'dev.json').unlink()
        with self.assertRaisesRegex(CorpusRefused, 'dev.json: the manifest lists [0-9a-f]{64}, the file hashes to nothing: it is missing'):
            check_corpus(corpus, 'dev')
        (corpus / 'corpus-manifest.json').write_text('{"freeze": "test"}\n', encoding='utf-8')
        with self.assertRaisesRegex(CorpusRefused, 'tasks.json is not listed in the manifest\'s files'):
            check_corpus(corpus, 'scored')
        (corpus / 'corpus-manifest.json').write_text('not json', encoding='utf-8')
        with self.assertRaisesRegex(CorpusRefused, 'corpus-manifest.json cannot be read'):
            check_corpus(corpus, 'scored')

    # ------------------------------------------------------------------ CRLF line endings
    def test_crlf_line_endings_whose_lf_bytes_match_pass(self):
        for source in (CORPUS1, CORPUS2):
            with self.subTest(corpus=source.name):
                corpus = self.copy(source)
                for name in ('dev.json',) + DRAWN:
                    path = corpus / name
                    path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
                check_corpus(corpus, 'dev')
                check_corpus(corpus, 'scored')
                self.assertEqual(self.study(corpus, 'dev', 'crlf-' + source.name).run(), 'complete')
                shutil.rmtree(corpus)

    def test_the_check_never_writes_or_repairs_a_corpus_file(self):
        corpus = self.copy(CORPUS2)
        one_byte_changed(corpus / 'tasks.json')
        before = {p.name: p.read_bytes() for p in corpus.iterdir()}
        with self.assertRaises(CorpusRefused):
            check_corpus(corpus, 'scored')
        self.assertEqual({p.name: p.read_bytes() for p in corpus.iterdir()}, before)


if __name__ == '__main__':
    unittest.main()
