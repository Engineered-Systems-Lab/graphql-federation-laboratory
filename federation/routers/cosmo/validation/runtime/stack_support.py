"""Helpers of the Cosmo router gates: Docker calls, free ports and the stack project (the GraphQL client is the shared suite's, re-exported here).

Everything a gate creates is disposable and uniquely named; a gate removes only what it created (its own compose project and its own
image tags). The wgc image is a build tool shared by every run and is not removed. Missing Docker is a failure.
"""
from pathlib import Path
import os
import secrets
import socket
import subprocess
import sys

ROUTER_DIR = Path(__file__).resolve().parents[2]
FEDERATION = ROUTER_DIR.parents[1]
ROOT = FEDERATION.parent
STACK_DIR = FEDERATION / 'stack'
COMPOSE_FILE = STACK_DIR / 'compose.yaml'
START = STACK_DIR / 'start.sh'
COMPOSE_SCRIPT = ROUTER_DIR / 'compose_execution_config.py'
COMMITTED_EXECUTION_CONFIG = ROUTER_DIR / 'execution-config.json'
ROUTER_CONFIG = ROUTER_DIR / 'config.yaml'
APOLLO_DIR = FEDERATION / 'routers/apollo'
APOLLO_SUPERGRAPH = APOLLO_DIR / 'supergraph.graphql'
ACCEPTANCE = FEDERATION / 'acceptance'
EXPECTED = ACCEPTANCE / 'expected-outcomes.json'
SERVICES = ('assets-db', 'assets-bootstrap', 'assets-service', 'personnel-service', 'missions-stub', 'missions-adapter', 'personnel-adapter',
            'assets-adapter', 'mapping-adapter')
ADAPTERS = ('missions', 'mapping', 'assets', 'personnel')
ROUTER_SERVICE = 'cosmo-router'
PROFILE = ['--profile', 'cosmo']

# The router-neutral client of the shared acceptance suite: one POST that keeps the HTTP status, a wait for an endpoint, the codes of an errors list.
sys.path.insert(0, str(ACCEPTANCE))
from graphql_client import codes, post, wait_for_graphql  # noqa: E402,F401


def bash():
    """The bash of Git for Windows when there is one (the WSL launcher on the PATH fails on every call)."""
    for candidate in ('bash', r'C:\Program Files\Git\bin\bash.exe'):
        try:
            if subprocess.run([candidate, '-c', 'echo ok'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30).stdout.strip() == b'ok':
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError('No working bash was found; the gate runs from Git Bash')


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def run(argv, env=None, timeout=300, cwd=None):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env, cwd=cwd)
    result.stdout, result.stderr = result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace')
    return result


def docker(args, timeout=300, check=True):
    result = run(['docker'] + args, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('docker ' + ' '.join(args[:3]) + ' failed: ' + (result.stderr or result.stdout)[-2000:])
    return result.stdout


class Stack:
    """One uniquely named compose project of federation/stack/compose.yaml with the Cosmo profile, on ephemeral loopback ports."""

    def __init__(self, scratch):
        self.token = secrets.token_hex(6)
        self.project = 'fed-cosmo-' + self.token
        self.scratch = Path(scratch)
        self.ports = {name: free_port() for name in ('router',) + ADAPTERS}
        self.execution_config = self.scratch / 'execution-config.json'
        self.images = {key: f'fed-cosmo-gate-{key}:{self.token}' for key in
                       ('assets-service', 'personnel-service', 'missions-adapter', 'personnel-adapter', 'assets-adapter', 'mapping-adapter')}
        self.admin_password, self.service_password = secrets.token_hex(16), secrets.token_hex(16)

    def env(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('STACK_', 'COMPOSE_', 'PG', 'ASSETS_', 'MISSIONS_', 'PERSONNEL_', 'MAPPING_', 'ROUTER_',
                                                                      'COSMO_', 'EXECUTION_', 'FEDERATION_', 'SUPERGRAPH_'))}
        env.update(
            COMPOSE_PROJECT_NAME=self.project,
            # The file asks for SUPERGRAPH_FILE whenever it is read, because the Apollo router is part of it; this run never starts that router.
            SUPERGRAPH_FILE=str(APOLLO_SUPERGRAPH),
            EXECUTION_CONFIG_FILE=str(self.execution_config),
            COSMO_ROUTER_HOST_PORT=str(self.ports['router']),
            MISSIONS_ADAPTER_HOST_PORT=str(self.ports['missions']),
            MAPPING_ADAPTER_HOST_PORT=str(self.ports['mapping']),
            ASSETS_ADAPTER_HOST_PORT=str(self.ports['assets']),
            PERSONNEL_ADAPTER_HOST_PORT=str(self.ports['personnel']),
            STACK_ASSETS_DB_ADMIN_PASSWORD=self.admin_password,
            STACK_ASSETS_DB_SERVICE_PASSWORD=self.service_password,
            STACK_ASSETS_SERVICE_IMAGE=self.images['assets-service'],
            STACK_PERSONNEL_SERVICE_IMAGE=self.images['personnel-service'],
            STACK_MISSIONS_ADAPTER_IMAGE=self.images['missions-adapter'],
            STACK_PERSONNEL_ADAPTER_IMAGE=self.images['personnel-adapter'],
            STACK_ASSETS_ADAPTER_IMAGE=self.images['assets-adapter'],
            STACK_MAPPING_ADAPTER_IMAGE=self.images['mapping-adapter'],
        )
        return env

    def compose(self, args, timeout=900):
        return run(['docker', 'compose', '-f', str(COMPOSE_FILE)] + PROFILE + args, self.env(), timeout)

    def compose_ok(self, args, timeout=900):
        result = self.compose(args, timeout)
        if result.returncode:
            raise RuntimeError('docker compose ' + ' '.join(args[:3]) + ' failed: ' + (result.stderr or result.stdout)[-2500:])
        return result.stdout

    def adapter_url(self, name):
        return f'http://127.0.0.1:{self.ports[name]}/graphql'

    @property
    def router_url(self):
        return f'http://127.0.0.1:{self.ports["router"]}/graphql'

    def compose_execution_config(self, out, extra=(), timeout=900):
        """Run the committed composition script exactly as a person would, against this project's adapters."""
        argv = [sys.executable, '-B', str(COMPOSE_SCRIPT), '--out', str(out)] + list(extra)
        result = run(argv, self.env(), timeout)
        if result.returncode:
            raise RuntimeError('compose_execution_config.py failed: ' + (result.stderr or result.stdout)[-2500:])
        return result.stdout

    def start_backends(self):
        self.compose_ok(['up', '-d', '--build', '--wait', '--wait-timeout', '600'] + list(SERVICES), timeout=2400)
        for name in ADAPTERS:
            wait_for_graphql(self.adapter_url(name))

    def start_router(self):
        self.compose_ok(['up', '-d', '--wait', '--wait-timeout', '120', ROUTER_SERVICE], timeout=300)
        wait_for_graphql(self.router_url)

    def restart(self, service):
        self.compose_ok(['restart', '--timeout', '30', service])
        if service.endswith('-adapter'):
            wait_for_graphql(self.adapter_url(service[:-len('-adapter')]))

    def teardown(self):
        """Remove only what this run created: its compose project (containers, network, volumes) and its image tags."""
        problems = []
        result = self.compose(['down', '--volumes', '--remove-orphans', '--timeout', '30'], timeout=300)
        if result.returncode:
            problems.append('compose down: ' + result.stderr[-1500:])
        for image in self.images.values():
            result = run(['docker', 'rmi', '--force', image])
            if result.returncode and 'No such image' not in result.stderr:
                problems.append('image ' + image + ': ' + result.stderr[-300:])
        return problems
