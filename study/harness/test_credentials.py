"""Tests of the credential handling and the launcher with FAKE credentials and a FAKE store. No real key, no real call, and no write to the
real Credential Manager."""
import io
import os
import sys
import unittest
from unittest import mock

import credentials
import launcher
from credentials import CREDENTIALS, CredentialError, MemoryCredentialStore, NotInteractiveError

FAKE_ANTHROPIC = 'sk-ant-FAKEFAKEFAKEFAKEFAKEFAKE'
FAKE_OPENAI = 'sk-FAKEFAKEFAKEFAKEFAKEFAKEFAKE'
A, O = CREDENTIALS['anthropic']['target'], CREDENTIALS['openai']['target']


class Asker:
    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0)


class SanityTests(unittest.TestCase):
    def test_shape_only(self):
        self.assertIsNone(credentials.sanity_problem('anthropic', FAKE_ANTHROPIC))
        self.assertIsNone(credentials.sanity_problem('openai', FAKE_OPENAI))
        self.assertIn('start', credentials.sanity_problem('anthropic', FAKE_OPENAI))
        self.assertIn('whitespace', credentials.sanity_problem('openai', 'sk-has space in it xxxxxxxxxxxxxxx'))
        self.assertIn('short', credentials.sanity_problem('openai', 'sk-short'))

    def test_names_do_not_depend_on_the_repository(self):
        for info in CREDENTIALS.values():
            self.assertTrue(info['target'].startswith('agent-study/'))
            self.assertNotIn('graphql', info['target'].lower())
            self.assertNotIn('federation', info['target'].lower())


class PromptTests(unittest.TestCase):
    def test_prompt_asks_twice_hidden_and_stores(self):
        store, ask, said = MemoryCredentialStore(), Asker(FAKE_ANTHROPIC, FAKE_ANTHROPIC), []
        credentials.prompt_and_store(store, 'anthropic', True, ask=ask, out=said.append)
        self.assertEqual(store.read(A), FAKE_ANTHROPIC)
        self.assertEqual(len(ask.prompts), 2)
        self.assertNotIn(FAKE_ANTHROPIC, ' '.join(said))

    def test_mismatch_and_bad_shape_store_nothing(self):
        store = MemoryCredentialStore()
        with self.assertRaises(CredentialError):
            credentials.prompt_and_store(store, 'anthropic', True, ask=Asker(FAKE_ANTHROPIC, FAKE_ANTHROPIC + 'x'), out=print)
        with self.assertRaises(CredentialError):
            credentials.prompt_and_store(store, 'anthropic', True, ask=Asker('nonsense', 'nonsense'), out=print)
        self.assertEqual(store.values, {})

    def test_non_interactive_refuses_and_never_asks(self):
        store, ask = MemoryCredentialStore(), Asker()
        with self.assertRaisesRegex(NotInteractiveError, 'run the launcher yourself in a terminal'):
            credentials.prompt_and_store(store, 'openai', False, ask=ask, out=print)
        self.assertEqual(ask.prompts, [])

    def test_is_interactive_needs_both_ends_on_a_terminal(self):
        tty, pipe = mock.Mock(isatty=lambda: True), io.StringIO()
        self.assertTrue(credentials.is_interactive(tty, tty))
        self.assertFalse(credentials.is_interactive(tty, pipe))
        self.assertFalse(credentials.is_interactive(pipe, tty))


class LauncherTests(unittest.TestCase):
    def run_launcher(self, argv, store, interactive=False, ask=None):
        said, spawned = [], []
        code = launcher.main(argv, store=store, interactive=interactive, ask=ask or Asker(), out=said.append,
                             spawn=lambda cmd, env: spawned.append((cmd, env)) or 0)
        return code, said, spawned

    def full(self):
        return MemoryCredentialStore({A: FAKE_ANTHROPIC, O: FAKE_OPENAI})

    def test_check_reports_present_or_missing_never_a_value(self):
        code, said, _ = self.run_launcher(['--check'], MemoryCredentialStore({A: FAKE_ANTHROPIC}))
        text = '\n'.join(said)
        self.assertEqual(code, 1)
        self.assertIn('present', text)
        self.assertIn('missing', text)
        self.assertNotIn(FAKE_ANTHROPIC, text)

    def test_run_gives_the_keys_only_to_the_child(self):
        before = dict(os.environ)
        code, _, spawned = self.run_launcher(['run', '--', '--run-id', 'x', '--config', 'c.json'], self.full())
        self.assertEqual(code, 0)
        command, env = spawned[0]
        self.assertEqual(env['ANTHROPIC_API_KEY'], FAKE_ANTHROPIC)
        self.assertEqual(env['OPENAI_API_KEY'], FAKE_OPENAI)
        self.assertEqual(command[-4:], ['--run-id', 'x', '--config', 'c.json'])
        self.assertNotIn(FAKE_ANTHROPIC, ' '.join(command))  # never an argument
        self.assertEqual(dict(os.environ), before)  # the launcher's own environment is untouched

    def test_missing_and_not_interactive_stops_clearly_and_starts_nothing(self):
        code, said, spawned = self.run_launcher(['run', '--', '--run-id', 'x'], MemoryCredentialStore({A: FAKE_ANTHROPIC}), interactive=False)
        self.assertEqual(code, 2)
        self.assertEqual(spawned, [])
        self.assertIn('run the launcher yourself in a terminal', '\n'.join(said))

    def test_missing_and_interactive_prompts_stores_and_continues(self):
        store = MemoryCredentialStore({A: FAKE_ANTHROPIC})
        ask = Asker(FAKE_OPENAI, FAKE_OPENAI)
        code, said, spawned = self.run_launcher(['run', '--', '--run-id', 'x'], store, interactive=True, ask=ask)
        self.assertEqual(code, 0)
        self.assertEqual(store.read(O), FAKE_OPENAI)
        self.assertEqual(spawned[0][1]['OPENAI_API_KEY'], FAKE_OPENAI)
        self.assertNotIn(FAKE_OPENAI, '\n'.join(said))

    def test_set_credentials_replaces_a_key_in_a_terminal_only(self):
        store = self.full()
        code, _, _ = self.run_launcher(['--set-credentials', 'openai'], store, interactive=True, ask=Asker('sk-ROTATEDROTATEDROTATEDROTATED', 'sk-ROTATEDROTATEDROTATEDROTATED'))
        self.assertEqual((code, store.read(O)), (0, 'sk-ROTATEDROTATEDROTATEDROTATED'))
        code, said, _ = self.run_launcher(['--set-credentials', 'openai'], store, interactive=False)
        self.assertEqual(code, 2)
        self.assertEqual(store.read(O), 'sk-ROTATEDROTATEDROTATEDROTATED')

    def test_a_stored_value_of_the_wrong_shape_is_refused_without_echo(self):
        code, said, spawned = self.run_launcher(['run', '--', '--run-id', 'x'], MemoryCredentialStore({A: 'garbage', O: FAKE_OPENAI}))
        self.assertEqual((code, spawned), (2, []))
        self.assertNotIn('garbage', '\n'.join(said))

    def test_no_key_is_ever_a_command_line_option(self):
        parser_help = launcher.__doc__ + credentials.__doc__
        for flag in ('--api-key', '--key', '--token'):
            self.assertNotIn(flag, parser_help)


@unittest.skipUnless(sys.platform == 'win32', 'Windows Credential Manager only')
class WindowsStoreTests(unittest.TestCase):
    def test_reading_a_target_that_does_not_exist_is_none(self):
        self.assertIsNone(credentials.WindowsCredentialStore().read('agent-study/test-target-that-does-not-exist'))


if __name__ == '__main__':
    unittest.main()
