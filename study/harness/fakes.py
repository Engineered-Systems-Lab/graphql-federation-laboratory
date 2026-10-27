"""Fakes for the harness tests: a scripted vendor client, a scripted stack, a scripted Docker. No SDK, no key, no network, no real API call,
no container."""
import json

from budget import Usage
from vendors import Turn, VendorFatalError, VendorTransientError


class FakeVendorClient:
    """Returns the scripted steps in order. A step is a Turn, an exception instance to raise, or a function (system, transcript, tools) -> step."""

    vendor = 'fake'

    def __init__(self, steps, max_output_tokens=1000, model='fake-model'):
        self.steps, self.max_output_tokens, self.model, self.calls = list(steps), max_output_tokens, model, []

    def create(self, system, transcript, tools):
        self.calls.append((system, [dict(item) for item in transcript], [t['name'] for t in tools]))
        step = self.steps.pop(0)
        if callable(step):
            step = step(system, transcript, tools)
        if isinstance(step, Exception):
            raise step
        return step


def turn(text='', calls=(), usage=(10, 0, 0, 5), stop='end_turn'):
    """A neutral Turn. `calls` are (id, name, arguments). `usage` is (input, cached_read, cache_write, output)."""
    tool_calls = [{'id': i, 'name': n, 'arguments': a} for i, n, a in calls]
    return Turn(text, tool_calls, Usage(*usage), stop, [{'raw': True, 'calls': len(tool_calls)}], 'req-1')


def submit(answer, usage=(10, 0, 0, 5), call_id='c-submit'):
    return turn('', [(call_id, 'submit_answer', answer)], usage)


def container(project, service, image_ref, image_id, env=None, ports=None, mounts=(), state='running', number=1):
    """One scripted container as `docker inspect` describes it. `ports` maps '4000/tcp' to [(host ip, host port)]; `mounts` are
    (source, destination, read_only) bind mounts."""
    name = '%s-%s-%d' % (project, service, number)
    return {'Id': 'id-' + name, 'Name': '/' + name, 'Image': image_id, 'State': {'Status': state},
            'Config': {'Image': image_ref, 'Env': ['%s=%s' % item for item in (env or {}).items()],
                       'Labels': {'com.docker.compose.project': project, 'com.docker.compose.service': service,
                                  'com.docker.compose.container-number': str(number)}},
            'NetworkSettings': {'Ports': {port: [{'HostIp': ip, 'HostPort': hp} for ip, hp in binds] for port, binds in (ports or {}).items()}},
            'Mounts': [{'Type': 'bind', 'Source': str(source), 'Destination': dest, 'RW': not ro} for source, dest, ro in mounts]}


class FakeDocker:
    """Answers the two read-only commands of provenance.py from scripted containers, and refuses everything else. `lines=True` prints the
    newer one-object-per-line output of `docker compose ps`, otherwise the older JSON array."""

    def __init__(self, containers, lines=True, fail=None):
        self.containers, self.lines, self.fail, self.calls = list(containers), lines, fail, []

    def __call__(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        if self.fail:
            raise self.fail
        if argv[:2] == ['compose', '-p'] and argv[3:] == ['ps', '--all', '--format', 'json']:
            rows = [{'ID': c['Id'], 'Name': c['Name'].lstrip('/'), 'Service': c['Config']['Labels']['com.docker.compose.service'],
                     'State': c['State']['Status']} for c in self.containers if c['Config']['Labels']['com.docker.compose.project'] == argv[2]]
            return ''.join(json.dumps(r) + '\n' for r in rows) if self.lines else json.dumps(rows)
        if argv[:1] == ['inspect'] and len(argv) > 1:
            by_id = {c['Id']: c for c in self.containers}
            return json.dumps([by_id[i] for i in argv[1:]])
        raise AssertionError('FakeDocker: not a read-only provenance command: %r' % argv)


__all__ = ['FakeVendorClient', 'turn', 'submit', 'container', 'FakeDocker', 'VendorFatalError', 'VendorTransientError']
