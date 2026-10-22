"""Verify built JAR resources, real selected-version smoke, and fail-closed startup.

Run after Maven clean verify, using JDK 17 on PATH and the pinned Python environment.
All services are temporary child processes bound to free loopback ports.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from xml_validation import COMPONENT, require, cli


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(0.1)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def environment(version, profile, port):
    env = os.environ.copy()
    env.pop('CREW_DATASET_VERSION', None)
    if version is not None:
        env['CREW_DATASET_VERSION'] = version
    env.update(CREW_FAILURE_PROFILE=profile, CREW_BIND_HOST='127.0.0.1', CREW_PORT=str(port))
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java', default='java')
    args = parser.parse_args()
    version = subprocess.run([args.java, '-version'], capture_output=True, text=True, check=True)
    require('version "17.' in version.stderr, 'JDK 17 required')
    jar = COMPONENT / 'target/crew-personnel-1.0.0.jar'
    release = COMPONENT / 'datasets/released/crew-v1-large-003'
    approved = {f'datasets/crew-v1-small-{i:03}.xml': COMPONENT / f'fixtures/canonical/crew-v1-small-{i:03}.xml' for i in (1, 2)}
    approved.update({f'datasets/released/crew-v1-large-003/{name}': release / name
                     for name in ['manifest.json'] + [f'page-{i:03}.xml' for i in range(8)]})
    with zipfile.ZipFile(jar) as archive:
        actual = [n for n in archive.namelist() if n.startswith('datasets/') and not n.endswith('/')]
        require(len(actual) == len(set(actual)) and set(actual) == set(approved), 'Unapproved/duplicate JAR dataset resources')
        for name, path in approved.items():
            require(archive.read(name) == path.read_bytes(), f'Packaged bytes differ: {name}')
    print('PASS: built JAR contains exactly 11 approved dataset resources with source-identical bytes.', flush=True)
    with tempfile.TemporaryDirectory(prefix='crew-runtime-') as tmp:
        for selected, profile in [(None, 'normal'), ('crew-v1-small-001', 'normal'),
                                  ('crew-v1-small-002', 'normal'), ('crew-v1-large-003', 'normal'),
                                  ('crew-v1-large-003', 'unavailable')]:
            port = free_port()
            with open(Path(tmp) / 'service.log', 'w+b') as log:
                process = subprocess.Popen([args.java, '-jar', str(jar)], env=environment(selected, profile, port), stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 30
                    while not listening(port) and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.05)
                    require(process.poll() is None and listening(port), 'Service did not publish')
                    subprocess.run([sys.executable, '-B', str(COMPONENT / 'validation/smoke.py'),
                                    '--endpoint', f'http://127.0.0.1:{port}/soap/crew-personnel',
                                    '--dataset-version', selected or 'crew-v1-small-002', '--profile', profile], check=True)
                finally:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=15)
        prefix = 'datasets/released/crew-v1-large-003/'
        for mode, resource in [('missing-manifest', 'manifest.json'), ('tampered-manifest', 'manifest.json'),
                               ('missing-page', 'page-004.xml'), ('tampered-page', 'page-004.xml')]:
            bad_jar = Path(tmp) / (mode + '.jar')
            with zipfile.ZipFile(jar) as source, zipfile.ZipFile(bad_jar, 'w') as target:
                for item in source.infolist():
                    data = source.read(item)
                    if item.filename == prefix + resource:
                        if mode.startswith('missing'):
                            continue
                        data = data.replace(b'800', b'801', 1) if resource == 'manifest.json' else data.replace(b'ACTIVE', b'ACTIVX', 1)
                    target.writestr(item, data)
            port = free_port()
            with open(Path(tmp) / 'failure.log', 'w+b') as log:
                process = subprocess.Popen([args.java, '-cp', str(bad_jar) + os.pathsep + str(jar.parent / 'lib/*'),
                                            'lab.enterprise.crew.Main'], env=environment('crew-v1-large-003', 'normal', port), stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 20
                    opened = False
                    while process.poll() is None and time.monotonic() < deadline:
                        opened |= listening(port)
                        time.sleep(0.02)
                    require(process.poll() is not None and process.returncode != 0 and not opened and not listening(port),
                            f'Invalid selected package published or did not fail: {mode}')
                    log.seek(0)
                    output = log.read().decode('utf-8', errors='replace')
                    require('Crew & Personnel:' not in output and
                            ('Missing registered resource' in output or 'hash mismatch' in output), 'Unexpected startup failure')
                finally:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=15)
            print(f'PASS: {mode} exits before publication; no fallback.', flush=True)


if __name__ == '__main__':
    sys.exit(cli(main))
