"""Support of the Assets service gate: a disposable PostgreSQL 17 container, the service as a local process and an HTTP client.

Everything is disposable and uniquely named per run. The container is the official image pinned by digest, bound to
loopback on an ephemeral port, small (a memory limit, a few megabytes of shared buffers, data in memory) and always
removed at the end. Credentials are random per run and travel only through the process environment. The reviewed Oracle
container of the Missions gates is never touched. Missing Docker, a missing image or a missing driver is a failure,
never a skip.
"""
from pathlib import Path
import atexit
import http.client
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time

COMPONENT = Path(__file__).resolve().parents[3]
SERVICE = COMPONENT / 'service'
# The official image, pinned by the digest of its OCI index. Resolved from the registry on 2026-10-15 (tag postgres:17-bookworm).
IMAGE = 'postgres:17-bookworm@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826'
IMAGE_RESOLVED_ON = '2026-10-15'
DATABASE = 'assets'
READER = 'assets_service'
TIMINGS = {}


def phase(name, started):
    TIMINGS[name] = round(time.monotonic() - started, 1)
    print(f'assets-service timing: {name} {TIMINGS[name]}s', flush=True)


def docker(argv, timeout=180, env=None, check=True):
    result = subprocess.run(['docker'] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)
    out = result.stdout.decode('utf-8', 'replace')
    if check and result.returncode:
        raise RuntimeError(f'docker {argv[0]} failed ({result.returncode}):\n' + result.stderr.decode('utf-8', 'replace')[-3000:] + out[-3000:])
    return out.strip()


def wait_ready(dsn_args, attempts=60, delay=1.0):
    """Connect to the freshly started server; the published port answers before the database does."""
    import psycopg
    last = None
    for _ in range(attempts):
        try:
            connection = psycopg.connect(connect_timeout=3, **dsn_args)
            connection.execute('SELECT 1')
            connection.rollback()
            return connection
        except psycopg.Error as error:
            last = error
            time.sleep(delay)
    raise RuntimeError('PostgreSQL did not become ready: ' + str(last))


class Postgres:
    """One disposable PostgreSQL 17 container."""

    def __init__(self):
        self.name = 'assets-service-gate-' + secrets.token_hex(6)
        self.admin_password = secrets.token_hex(16)
        self.reader_password = secrets.token_hex(16)
        self.port = None
        self.running = False

    def admin_args(self, database=DATABASE):
        return {'host': '127.0.0.1', 'port': self.port, 'user': 'postgres', 'password': self.admin_password, 'dbname': database}

    def start(self):
        started = time.monotonic()
        docker(['version', '--format', '{{.Server.Version}}'])
        present = subprocess.run(['docker', 'image', 'inspect', IMAGE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not present:
            docker(['pull', IMAGE], timeout=900)
        phase('image-present-or-pulled', started)
        started = time.monotonic()
        env = dict(os.environ, POSTGRES_PASSWORD=self.admin_password)
        atexit.register(self.stop)
        self.running = True
        docker(['run', '-d', '--name', self.name, '--label', 'starfleet.assets.gate=1', '--memory', '512m',
                '--tmpfs', '/var/lib/postgresql/data', '-p', '127.0.0.1::5432',
                '-e', 'POSTGRES_PASSWORD', '-e', 'POSTGRES_DB=' + DATABASE, IMAGE,
                '-c', 'shared_buffers=32MB', '-c', 'max_connections=40', '-c', 'fsync=off', '-c', 'synchronous_commit=off',
                '-c', 'full_page_writes=off', '-c', 'log_statement=all', '-c', 'log_line_prefix=%m [%p] %u@%d '], env=env)
        mapping = docker(['port', self.name, '5432/tcp'])
        self.port = int(mapping.splitlines()[0].rsplit(':', 1)[1])
        connection = wait_ready(self.admin_args())
        connection.close()
        phase('container-start-to-ready', started)

    def stop(self):
        if self.running:
            self.running = False
            try:
                docker(['rm', '-f', '-v', self.name], timeout=60)
            except Exception as error:
                print(f'assets-service: container {self.name} was not removed: {error}', file=sys.stderr, flush=True)

    def admin(self, database=DATABASE, autocommit=True):
        import psycopg
        connection = psycopg.connect(connect_timeout=5, **self.admin_args(database))
        connection.autocommit = autocommit
        return connection

    def dump(self, database, *options):
        """pg_dump output from inside the container, for the byte comparison of two databases."""
        return docker(['exec', '-e', 'PGPASSWORD=' + self.admin_password, self.name, 'pg_dump', '-U', 'postgres', '--no-owner',
                       '--no-privileges', *options, database])

    def service_env(self, database=DATABASE, user=READER, password=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('PG', 'ASSETS_'))}
        env.update(PGHOST='127.0.0.1', PGPORT=str(self.port), PGDATABASE=database, PGUSER=user,
                   PGPASSWORD=password if password is not None else self.reader_password, PYTHONUNBUFFERED='1')
        return env


class ServiceProcess:
    """The service as a local Python process, on an ephemeral loopback port."""

    def __init__(self, env):
        self.env = env
        self.process = None
        self.port = None
        self.log = tempfile.NamedTemporaryFile(prefix='assets-service-', suffix='.log', delete=False)

    def start(self, timeout=30):
        self.process = subprocess.Popen([sys.executable, '-B', str(SERVICE / 'assets_service.py'), '--host', '127.0.0.1', '--port', '0'],
                                        stdout=subprocess.PIPE, stderr=self.log, env=self.env, cwd=str(SERVICE))
        line = []
        reader = threading.Thread(target=lambda: line.append(self.process.stdout.readline().decode('utf-8', 'replace').strip()), daemon=True)
        reader.start()
        reader.join(timeout)
        if not line or not line[0].startswith('LISTENING '):
            self.stop()
            raise RuntimeError('The service did not start: ' + (line[0] if line else 'no output') + '\n' + self.log_text())
        self.port = int(line[0].rsplit(':', 1)[1])
        atexit.register(self.stop)

    def log_text(self):
        self.log.flush()
        return Path(self.log.name).read_text(encoding='utf-8', errors='replace')[-3000:]

    def stop(self):
        process, self.process = self.process, None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(10)
        if process and process.stdout:
            process.stdout.close()
        try:
            self.log.close()
            os.unlink(self.log.name)
        except OSError:
            pass


class Reply:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body

    def header(self, name):
        return [v for k, v in self.headers if k.lower() == name.lower()]

    def json(self):
        return json.loads(self.body.decode('utf-8'))


def request(port, method, target, headers=None, body=None):
    """One request on a fresh connection; http.client sends the target exactly as given."""
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=20)
    try:
        connection.request(method, target, body=body, headers=headers or {})
        response = connection.getresponse()
        return Reply(response.status, response.getheaders(), response.read())
    finally:
        connection.close()


def raw_exchange(port, data, timeout=10):
    """Send raw bytes and read the whole reply: for requests that http.client would not send."""
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as connection:
        connection.sendall(data)
        chunks = []
        while True:
            try:
                chunk = connection.recv(65536)
            except (socket.timeout, ConnectionResetError):
                break
            if not chunk:
                break
            chunks.append(chunk)
    return b''.join(chunks)
