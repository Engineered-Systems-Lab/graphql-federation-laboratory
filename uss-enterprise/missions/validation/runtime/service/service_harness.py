"""Shared harness of the Missions service acceptance gates: the real Jersey/Tomcat service over plain JDBC against Oracle 18c.

Everything is disposable and uniquely named per run. One image tag per process (built once, shared by the read and write
gates, removed at exit), ephemeral loopback ports, and per test class a MS_TEST_ schema loaded with release 1.0 plus a
MS_SVC_ login holding only the grants that class declares. The reviewed Oracle container must already be provisioned and
running; it is reused and never removed, recreated or changed beyond those disposable schemas and logins. Missing Docker,
Oracle or Maven (inside the image build) is a failure, never a skip. No Dockerfile is committed: the build context is a
temporary directory.
"""
from decimal import Decimal
from pathlib import Path
import atexit
import http.client
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from lxml import etree

COMPONENT = Path(__file__).resolve().parents[3]
DATASETS = COMPONENT / 'datasets'
sys.path.insert(0, str(DATASETS))
spec = importlib.util.spec_from_file_location('missions_operator', DATASETS / 'missions_operator.py')
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)
import validate_release as validation

NS = 'urn:starfleet:missions:v1'
SCHEMA = etree.XMLSchema(etree.parse(str(COMPONENT / 'contracts/missions-v1.1.xsd')))
TIMINGS = {}
IMAGE = {'tag': None}


def q(name):
    return '{' + NS + '}' + name


def docker(argv, timeout=120, env=None, check=True):
    result = subprocess.run(['docker'] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)
    out = result.stdout.decode('utf-8', 'replace')
    if check and result.returncode:
        raise RuntimeError('docker ' + argv[0] + ' failed (' + str(result.returncode) + '):\n' + result.stderr.decode('utf-8', 'replace')[-3000:] + out[-3000:])
    return out.strip()


def phase(name, started):
    TIMINGS[name] = round(time.monotonic() - started, 1)
    print('missions-service timing: ' + name + ' ' + str(TIMINGS[name]) + 's', flush=True)


def ensure_image():
    """Builds the service image once per process; its Maven verify runs the Java unit tests on JDK 17."""
    if IMAGE['tag']:
        return IMAGE['tag']
    started = time.monotonic()
    tag = 'missions-service-validation:' + secrets.token_hex(6)
    build = subprocess.run(['docker', 'build', '--progress=plain', '-t', tag, str(COMPONENT)], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=1800)
    log = build.stdout.decode('utf-8', 'replace')
    if build.returncode:
        raise RuntimeError('Image build (Maven verify on JDK 17) failed:\n' + log[-6000:])
    IMAGE['tag'] = tag
    atexit.register(remove_image)
    tests = re.findall(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)\n?', log)
    print('missions-service: image ' + tag + ' built; Maven test summaries: ' + str(tests[-1:] or 'not echoed'), flush=True)
    phase('image-build-with-maven-verify', started)
    return tag


def remove_image():
    tag, IMAGE['tag'] = IMAGE['tag'], None
    if tag:
        try:
            docker(['rmi', tag])
        except Exception as error:
            print('missions-service: image ' + tag + ' was not removed: ' + str(error), file=sys.stderr, flush=True)


class Response:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body

    def header(self, name):
        return [v for k, v in self.headers if k.lower() == name.lower()]

    def xml(self):
        return etree.fromstring(self.body)


class ServiceCase(unittest.TestCase):
    """A service gate class: its own schema, login and containers around the shared image."""
    KIND = 'service'

    @classmethod
    def grants(cls):
        """SQL statements, one per entry, granting the login what this class's operations need."""
        raise NotImplementedError

    @classmethod
    def setUpClass(cls):
        cls.run_id = secrets.token_hex(6)
        cls.schema = 'MS_TEST_' + cls.run_id.upper()
        cls.login = 'MS_SVC_' + cls.run_id.upper()
        cls.password = 'P' + secrets.token_hex(12)
        cls.containers = []
        cls.owned = []
        cls.started = time.monotonic()
        try:
            cls.prepare()
        except BaseException:
            cls.cleanup()
            raise

    @classmethod
    def prepare(cls):
        started = time.monotonic()
        operator.db_guard()
        env = operator.ENV
        cls.network = env['network']
        cls.database_host = env['container']
        cls.pdb = env['pdb']
        phase(cls.KIND + ' guard', started)
        started = time.monotonic()
        operator.create_schema(cls.schema)
        cls.owned.append('schema')
        operator.reset('1.0', cls.schema, check_service=False)
        cls.path, cls.manifest, cls.data = validation.validate_release('1.0')
        # The password travels on SQL stdin, never argv or output.
        operator.sql('CREATE USER ' + cls.login + ' IDENTIFIED BY "' + cls.password + '" DEFAULT TABLESPACE USERS;\n'
                     'GRANT CREATE SESSION TO ' + cls.login + ';')
        cls.owned.append('login')
        for statement in cls.grants():
            operator.sql(statement)
        phase(cls.KIND + ' oracle-schema-load-and-login', started)
        ensure_image()
        started = time.monotonic()
        cls.base, cls.bad_base = cls.start('correct'), cls.start('wrong')
        phase(cls.KIND + ' service-containers-ready', started)

    @classmethod
    def start(cls, which):
        name = 'missions-' + cls.KIND + '-' + which + '-' + cls.run_id
        password = cls.password if which == 'correct' else 'Wrong' + secrets.token_hex(6)
        url = 'jdbc:oracle:thin:@//' + cls.database_host + ':1521/' + cls.pdb
        env = dict(os.environ, MISSIONS_DB_PASSWORD=password)
        # Created on the default bridge for the ephemeral loopback port, then joined to the internal Oracle network
        # before it starts. Oracle itself publishes nothing and is not changed.
        docker(['create', '--name', name, '--label', 'starfleet.missions.service-validation=' + cls.run_id,
                '-p', '127.0.0.1::8083', '-e', 'MISSIONS_JDBC_URL=' + url, '-e', 'MISSIONS_DB_USER=' + cls.login,
                '-e', 'MISSIONS_DB_PASSWORD', '-e', 'MISSIONS_DB_SCHEMA=' + cls.schema, IMAGE['tag']], env=env)
        cls.containers.append(name)
        docker(['network', 'connect', cls.network, name])
        docker(['start', name])
        binding = json.loads(docker(['inspect', name]))[0]['NetworkSettings']['Ports']['8083/tcp'][0]
        if binding['HostIp'] != '127.0.0.1':
            raise RuntimeError('Service publication must be loopback only')
        base = ('127.0.0.1', int(binding['HostPort']))
        deadline = time.monotonic() + 90
        while True:
            try:
                if cls.get(base, '/nothing-here').status == 404:
                    return base
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError('Service failed readiness: ' + docker(['logs', '--tail', '60', name], check=False))
            time.sleep(.25)

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()
        TIMINGS[cls.KIND + ' class total'] = round(time.monotonic() - cls.started, 1)
        print('missions-service timings (seconds): ' + json.dumps(TIMINGS), flush=True)

    @classmethod
    def cleanup(cls):
        problems = []

        def attempt(label, action):
            try:
                action()
            except Exception as error:
                problems.append(label + ': ' + str(error))
        for name in cls.containers:
            attempt('container ' + name, lambda n=name: docker(['rm', '-f', n]))
        if 'login' in cls.owned:
            attempt('login', lambda: operator.sql('DROP USER ' + cls.login + ' CASCADE;'))
        if 'schema' in cls.owned:
            attempt('schema', lambda: operator.drop_test_schema(cls.schema))
        if problems:
            raise RuntimeError('Cleanup of owned resources failed: ' + '; '.join(problems))

    # --- helpers -----------------------------------------------------------------------------------------

    @staticmethod
    def get(base, path, method='GET', headers=(), body=None):
        connection = http.client.HTTPConnection(base[0], base[1], timeout=60)
        try:
            connection.putrequest(method, path, skip_accept_encoding=True)
            for name, value in headers:
                connection.putheader(name, value)
            if body is not None:
                connection.putheader('Content-Length', str(len(body)))
            connection.endheaders(body)
            reply = connection.getresponse()
            return Response(reply.status, reply.getheaders(), reply.read())
        finally:
            connection.close()

    def call(self, path, method='GET', headers=(), body=None):
        return self.get(self.base, path, method, headers, body)

    def ok_xml(self, response, root):
        self.assertEqual(response.status, 200, response.body[:300])
        self.assert_xml(response, root)
        return response.xml()

    def assert_xml(self, response, root):
        content_type = response.header('Content-Type')
        self.assertEqual(len(content_type), 1)
        self.assertEqual(re.sub(r'\s+', '', content_type[0]).lower(), 'application/xml;charset=utf-8')
        document = response.xml()
        self.assertTrue(SCHEMA.validate(document), SCHEMA.error_log)
        self.assertEqual(document.tag, q(root))
        self.assertTrue(response.body.startswith(b'<?xml'))

    def assert_error(self, response, status, code):
        self.assertEqual(response.status, status, response.body[:300])
        self.assert_xml(response, 'error')
        self.assertEqual(response.xml().findtext(q('code')), code)
        text = response.body.decode('utf-8')
        for leak in ('Exception', 'java.', 'org.glassfish', 'ORA-', 'SQLException', 'at lab.', 'cvc-', 'xerces', '/etc/passwd'):
            self.assertNotIn(leak, text)

    def assert_bodyless(self, response, status):
        self.assertEqual(response.status, status)
        self.assertEqual(response.body, b'')
        self.assertEqual(response.header('Content-Type'), [])

    @staticmethod
    def mission_dict(element):
        text = element.findtext
        result = {'missionId': text(q('missionId')), 'title': text(q('title')), 'type': text(q('type')),
                  'classification': text(q('classification')), 'status': text(q('status')),
                  'priority': int(text(q('priority'))), 'stardate': text(q('stardate')),
                  'durationHours': int(text(q('durationHours'))), 'objective': text(q('objective')),
                  'issuingAuthority': text(q('issuingAuthority')), 'lastUpdated': text(q('lastUpdated'))}
        location = element.find(q('location'))
        result['location'] = {'type': location.findtext(q('type')), 'name': location.findtext(q('name'))}
        for key in ('coordinates', 'travelVector'):
            if location.find(q(key)) is not None:
                result['location'][key] = location.findtext(q(key))
        for key in ('commandingOfficerId', 'estimatedCostCredits', 'actualCostCredits', 'outcome'):
            if element.find(q(key)) is not None:
                result[key] = text(q(key))
        for key in ('assignedCrewIds', 'participantIds', 'assignedAssetIds'):
            result[key] = [child.text for child in element.find(q(key))]
        return result

    @staticmethod
    def change_dict(element):
        return {etree.QName(child).localname: child.text for child in element}

    def expected(self, mission):
        return {k: v for k, v in mission.items() if k not in ('currentChangeId', 'cancelledWithoutEstimateAllowed')}

    def ordered(self, missions=None):
        return sorted(self.data['missions'] if missions is None else missions,
                      key=lambda m: (Decimal(m['stardate']), m['priority'], m['missionId']))

    def listing(self, query=''):
        document = self.ok_xml(self.call('/missions' + query), 'missionList')
        meta = [document.findtext(q(n)) for n in ('page', 'pageSize', 'totalCount', 'totalPages')]
        return meta, [self.mission_dict(m) for m in document.findall(q('mission'))]

    @classmethod
    def query(cls, sql):
        """Runs SQL as the database administrator inside this class's disposable schema; returns the output lines."""
        return operator.sql(sql, cls.schema).splitlines()
