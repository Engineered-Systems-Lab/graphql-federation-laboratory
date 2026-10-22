"""The Missions adapter start script's port rule, with no Docker: a taken port is refused with one line and a free one is accepted
(--dry-run). The real start, on a free port, and the refusal while the adapter itself holds the port are in test_packaging.
"""
from pathlib import Path
import os
import socket
import subprocess
import unittest

START = Path(__file__).resolve().parents[3] / 'start.sh'
ROOT = Path(__file__).resolve().parents[6]


def find_bash():
    """A bash that works: the one on the PATH if it runs a command (the WSL launcher does not), else Git for Windows'."""
    for candidate in ('bash', r'C:\Program Files\Git\bin\bash.exe'):
        try:
            if subprocess.run([candidate, '-c', 'echo ok'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30).stdout.strip() == b'ok':
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError('No working bash was found; the gate runs from Git Bash')


BASH = find_bash()


class StartScriptTest(unittest.TestCase):
    def run_script(self, port, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('MISSIONS_', 'COMPOSE_'))}
        env['MISSIONS_ADAPTER_HOST_PORT'] = str(port)
        result = subprocess.run([BASH, str(START)] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=60)
        return result.returncode, result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace')

    def test_a_taken_port_is_refused_with_one_line(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(64)
            code, out, err = self.run_script(listener.getsockname()[1], '--dry-run', 'start')
        self.assertEqual(code, 1)
        self.assertEqual(out, '')
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn('already in use', err)

    def test_a_free_port_starts_the_stack(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        code, out, err = self.run_script(port, '--dry-run', 'start')
        self.assertEqual(code, 0, err)
        self.assertIn('would run: docker compose', out)
        self.assertIn('up -d', out)

    def test_the_default_port_is_8183(self):
        self.assertIn('PORT="${MISSIONS_ADAPTER_HOST_PORT:-8183}"', START.read_text(encoding='utf-8'))

    def test_it_never_removes_anything(self):
        commands = [line.strip() for line in START.read_text(encoding='utf-8').splitlines() if line.strip().startswith('run docker')]
        self.assertEqual(sorted(c.split()[5] for c in commands), ['ps', 'stop', 'up'])
        self.assertNotRegex(' '.join(commands), r'(down|rm|rmi|prune|--volumes)')

    def test_bad_usage_exits_2(self):
        self.assertEqual(self.run_script(8183, 'frobnicate')[0], 2)
        self.assertEqual(self.run_script(8183)[0], 2)
        self.assertEqual(self.run_script('abc', 'start')[0], 2)

    def test_the_attributes_keep_the_script_lf(self):
        attributes = (ROOT / '.gitattributes').read_text(encoding='utf-8')
        self.assertIn('federation/adapters/missions/start.sh text eol=lf', attributes.splitlines())


if __name__ == '__main__':
    unittest.main()
