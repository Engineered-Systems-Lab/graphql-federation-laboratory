"""Test of the harness's MCP client against the real local raw server of study/mcp (a loopback process, no stack, no key, no model).

It needs the pinned `mcp` package; without it the test is skipped and says so (the study gate reports that count).
"""
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

try:  # a real import: a folder called mcp on the path (study/mcp) is not the package
    from mcp import Client  # noqa: F401
    HAVE_MCP = True
except ImportError:
    HAVE_MCP = False
SERVER = Path(__file__).resolve().parent.parent / 'mcp' / 'raw_server.py'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@unittest.skipUnless(HAVE_MCP, 'the pinned mcp package is not installed in this interpreter')
class McpSessionTests(unittest.TestCase):
    def test_lists_tools_calls_one_and_sends_the_run_id(self):
        from mcp_client import McpSession
        with tempfile.TemporaryDirectory() as tmp:
            release = Path(tmp) / 'mapping' / '1.3'
            release.mkdir(parents=True)
            (release / 'a.json').write_text('{}', encoding='utf-8')
            log, port = Path(tmp) / 'calls.jsonl', free_port()
            server = subprocess.Popen([sys.executable, '-B', str(SERVER), '--mapping-dir', str(Path(tmp) / 'mapping'), '--port', str(port),
                                       '--log', str(log)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.addCleanup(lambda: (server.terminate(), server.wait(timeout=15)))
            session = None
            for _ in range(40):
                try:
                    session = McpSession('http://127.0.0.1:%d/mcp' % port, 'run-key-1')
                    break
                except Exception:
                    time.sleep(0.5)
            self.assertIsNotNone(session, 'the server did not start')
            with session:
                names = [t['name'] for t in session.tools()]
                self.assertEqual(names, ['http_request', 'soap_request', 'read_mapping_release'])
                self.assertTrue(all(t['input_schema'] for t in session.tools()))
                text, is_error = session.call('read_mapping_release', {'release': '1.3'})
                self.assertFalse(is_error)
                self.assertIn('a.json', text)
                text, is_error = session.call('read_mapping_release', {'release': '2.0'})
                self.assertTrue(is_error)
            entries = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
            self.assertEqual({e['run_id'] for e in entries}, {'run-key-1'})


if __name__ == '__main__':
    unittest.main()
