"""uss-enterprise/scripts/personnel.sh, uss-enterprise/scripts/missions.sh and uss-enterprise/scripts/assets.sh: the requests they build, their usage and exit codes, and the down message.

The Personnel request is compared with the one the acceptance test sends: the namespaces come from the service's own
Xml.java, and the test first checks that SoapHttpTest.java still builds its envelope and request elements the way this
test reconstructs them, so a change to either side fails here instead of drifting. Nothing needs Docker: a closed
loopback port stands for the down service and a throwaway local server for a running one. Run it from Git Bash."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import unittest

from lxml import etree

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'uss-enterprise' / 'scripts'
PERSONNEL = ROOT / 'uss-enterprise' / 'personnel-v2'
JAVA = PERSONNEL / 'src' / 'test' / 'java' / 'lab' / 'enterprise' / 'personnel' / 'SoapHttpTest.java'
XML_JAVA = PERSONNEL / 'src' / 'main' / 'java' / 'lab' / 'enterprise' / 'personnel' / 'Xml.java'
ASSETS_CONTRACT = ROOT / 'uss-enterprise' / 'assets' / 'contracts' / 'assets-v1.1.openapi.json'
MISSIONS_ACCEPTANCE = ROOT / 'uss-enterprise' / 'missions' / 'validation' / 'runtime' / 'service' / 'test_read_service.py'
ENVIRONMENT = {k: v for k, v in os.environ.items()
               if not k.startswith('GIT_') and k not in ('PERSONNEL_URL', 'MISSIONS_URL', 'ASSETS_URL')}


def constant(name):
    return re.search(r'static final String ' + name + r' = "([^"]+)";', XML_JAVA.read_text(encoding='utf-8')).group(1)


def closed_loopback_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


class Recorder(BaseHTTPRequestHandler):
    """Answers as the services do: pretty-printable XML with an ETag, a SOAP fault with 500, a bodyless 404, and for
    Assets compact JSON with no ETag and a JSON error body with 404."""
    seen = []

    def log_message(self, *args):
        pass

    def reply(self, status, body, headers=()):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.seen.append(('GET', self.path, dict(self.headers), b''))
        if self.path.startswith('/missions/ST-NONE'):
            return self.reply(404, b'')
        if self.path.startswith('/assets/AST-9999'):
            return self.reply(404, b'{"error":{"code":"ASSET_NOT_FOUND"}}', [('Content-Type', 'application/json')])
        if self.path.startswith('/assets'):
            return self.reply(200, '{"items":[{"assetId":"AST-0017","name":"Café"}]}'.encode('utf-8'),
                              [('Content-Type', 'application/json')])
        self.reply(200, '<mission><missionId>ST-1</missionId><title>Café</title></mission>'.encode('utf-8'),
                   [('Content-Type', 'application/xml'), ('ETag', '"c-7"')])

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        self.seen.append(('POST', self.path, dict(self.headers), body))
        if b'PRS-9999' in body:
            return self.reply(500, b'<s:Envelope xmlns:s="x"><s:Body><s:Fault/></s:Body></s:Envelope>')
        self.reply(200, b'<s:Envelope xmlns:s="x"><s:Body><member><id>PRS-0001</id></member></s:Body></s:Envelope>')


@unittest.skipUnless(shutil.which('bash') and shutil.which('curl'), 'Git Bash and curl required for the scripts')
class ServiceScriptsTest(unittest.TestCase):
    def run_script(self, name, args, **env):
        return subprocess.run([shutil.which('bash'), str(SCRIPTS / name), *args], cwd=str(ROOT.parent),
                              env={**ENVIRONMENT, **env}, capture_output=True, text=True, encoding='utf-8')

    def serve(self):
        Recorder.seen = []
        server = HTTPServer(('127.0.0.1', 0), Recorder)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return 'http://127.0.0.1:%d' % server.server_address[1]

    def dry(self, name, args):
        result = self.run_script(name, ['--dry-run', *args])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        head, _, body = result.stdout.rstrip('\n').partition('\n\n')
        return head.split('\n'), body.rstrip('\n')

    # --- the Personnel request is the one the acceptance test sends ------------------------------------------------

    def expected_body(self, name, children):
        # The shapes of SoapHttpTest.wrapper and SoapHttpTest.envelope.
        payload = '<' + name + " xmlns='" + constant('NS') + "'>" + children + '</' + name + '>'
        return "<s:Envelope xmlns:s='" + constant('SOAP') + "'><s:Body>" + payload + '</s:Body></s:Envelope>'

    def test_the_acceptance_test_still_builds_its_requests_the_way_this_test_does(self):
        source = JAVA.read_text(encoding='utf-8')
        for line in (
                '"<" + name + " xmlns=\'" + Xml.NS + "\'>" + children + "</" + name + ">"',
                '"<s:Envelope xmlns:s=\'" + Xml.SOAP + "\'><s:Body>" + payload + "</s:Body></s:Envelope>"',
                '"\\"" + Xml.NS + (xml.contains("GetPersonnelMemberRequest") ? ":GetPersonnelMember" : ":ListPersonnelMembers") + "\\""',
                'wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-0001</personnelId>")',
                'wrapper("ListPersonnelMembersRequest", "")',
                'wrapper("ListPersonnelMembersRequest", "<department>OPERATIONS</department><dutyStatus>ACTIVE</dutyStatus>")'):
            self.assertIn(line, source)

    def test_get_sends_the_acceptance_request(self):
        head, body = self.dry('personnel.sh', ['get', 'PRS-0001'])
        self.assertEqual(head, [
            'POST http://127.0.0.1:8082/soap/personnel-v2', 'Content-Type: text/xml; charset=utf-8',
            'SOAPAction: "' + constant('NS') + ':GetPersonnelMember"'])
        self.assertEqual(body, self.expected_body('GetPersonnelMemberRequest', '<personnelId>PRS-0001</personnelId>'))

    def test_list_sends_the_acceptance_requests(self):
        head, body = self.dry('personnel.sh', ['list'])
        self.assertEqual(head[2], 'SOAPAction: "' + constant('NS') + ':ListPersonnelMembers"')
        self.assertEqual(body, self.expected_body('ListPersonnelMembersRequest', ''))
        _, body = self.dry('personnel.sh', ['list', 'dutyStatus=ACTIVE', 'department=OPERATIONS'])
        self.assertEqual(body, self.expected_body(
            'ListPersonnelMembersRequest', '<department>OPERATIONS</department><dutyStatus>ACTIVE</dutyStatus>'))

    def test_list_filters_follow_the_sequence_of_the_contract_and_escape_text(self):
        _, body = self.dry('personnel.sh', ['list', 'limit=2', 'offset=1', 'dutyStatus=ACTIVE', 'department=A&B<'])
        self.assertEqual(body, self.expected_body(
            'ListPersonnelMembersRequest',
            '<department>A&amp;B&lt;</department><dutyStatus>ACTIVE</dutyStatus><offset>1</offset><limit>2</limit>'))

    def test_every_request_validates_against_the_frozen_schema(self):
        schema = etree.XMLSchema(etree.parse(str(PERSONNEL / 'contracts' / 'personnel-v2.xsd')))
        soap = '{' + constant('SOAP') + '}'
        for args in (['get', 'PRS-0001'], ['list'], ['list', 'department=OPERATIONS', 'dutyStatus=ON_LEAVE', 'offset=0', 'limit=100']):
            with self.subTest(args=args):
                _, body = self.dry('personnel.sh', args)
                envelope = etree.fromstring(body.encode('utf-8'))
                self.assertEqual(envelope.tag, soap + 'Envelope')
                request = envelope.find(soap + 'Body')[0]
                schema.assertValid(request)

    def test_the_url_comes_from_the_environment(self):
        result = self.run_script('personnel.sh', ['--dry-run', 'list'], PERSONNEL_URL='http://127.0.0.1:9/soap/x/')
        self.assertTrue(result.stdout.startswith('POST http://127.0.0.1:9/soap/x\n'), result.stdout)

    # --- the Missions requests --------------------------------------------------------------------------------------

    def test_missions_routes_are_the_ones_the_acceptance_test_calls(self):
        source = MISSIONS_ACCEPTANCE.read_text(encoding='utf-8')
        for fragment in ("'/missions/' + mission['missionId']", "'/missions?pageSize=1'", '/changes'):
            self.assertIn(fragment, source)

    def test_missions_requests(self):
        for args, line in (
                (['list'], 'GET http://127.0.0.1:8083/missions'),
                (['get', 'ST-ABC123'], 'GET http://127.0.0.1:8083/missions/ST-ABC123'),
                (['changes', 'ST-ABC123'], 'GET http://127.0.0.1:8083/missions/ST-ABC123/changes'),
                (['list', 'status=ACTIVE', 'pageSize=5'], 'GET http://127.0.0.1:8083/missions?status=ACTIVE&pageSize=5'),
                (['list', 'issuingAuthority=Star Fleet', 'page=2'],
                 'GET http://127.0.0.1:8083/missions?issuingAuthority=Star%20Fleet&page=2'),
                (['get', 'a/b?c'], 'GET http://127.0.0.1:8083/missions/a%2Fb%3Fc')):
            with self.subTest(args=args):
                head, body = self.dry('missions.sh', args)
                self.assertEqual(head, [line, 'Accept: application/xml'])
                self.assertEqual(body, '')

    def test_the_missions_url_comes_from_the_environment(self):
        result = self.run_script('missions.sh', ['--dry-run', 'get', 'X'], MISSIONS_URL='http://127.0.0.1:9/')
        self.assertEqual(result.stdout.split('\n')[0], 'GET http://127.0.0.1:9/missions/X')

    def test_the_scripts_wrap_no_write_method(self):
        for name in ('personnel.sh', 'missions.sh', 'assets.sh'):
            text = (SCRIPTS / name).read_text(encoding='utf-8')
            self.assertNotIn('PUT', text)
            self.assertNotIn('If-Match', text)
        for name in ('missions.sh', 'assets.sh'):
            self.assertNotIn('-X ', (SCRIPTS / name).read_text(encoding='utf-8'))

    # --- usage and exit codes ---------------------------------------------------------------------------------------

    def test_help_prints_the_usage_to_standard_output_and_succeeds(self):
        for name in ('personnel.sh', 'missions.sh', 'assets.sh'):
            for flag in ('--help', '-h'):
                with self.subTest(name=name, flag=flag):
                    result = self.run_script(name, [flag])
                    self.assertEqual(result.returncode, 0)
                    self.assertIn('Usage: uss-enterprise/scripts/' + name, result.stdout)
                    self.assertIn('--dry-run', result.stdout)
                    self.assertEqual(result.stderr, '')

    def test_bad_invocations_print_the_usage_and_exit_two(self):
        cases = {
            'personnel.sh': ([], ['bogus'], ['get'], ['get', 'a', 'b'], ['list', 'name=x'], ['list', 'limit=1', 'limit=2'],
                             ['list', 'positional'], ['--dry-run'], ['--dry-run', 'delete', 'PRS-0001']),
            'missions.sh': ([], ['bogus'], ['get'], ['changes'], ['get', 'a', 'b'], ['list', 'colour=red'], ['list', 'x'],
                            ['--dry-run'], ['post', 'x'], ['put', 'x']),
            'assets.sh': ([], ['bogus'], ['get'], ['get', 'a', 'b'], ['list', 'colour=red'], ['list', 'x'],
                          ['list', 'changes=1'], ['--dry-run'], ['post', 'x'], ['delete', 'AST-0017']),
        }
        for name, invocations in cases.items():
            for args in invocations:
                with self.subTest(name=name, args=args):
                    result = self.run_script(name, args)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, '')
                    self.assertIn('Usage: uss-enterprise/scripts/' + name, result.stderr)

    # --- a service that is not running ------------------------------------------------------------------------------

    def test_a_service_that_is_not_running_gets_one_clear_line_and_a_failure(self):
        url = 'http://127.0.0.1:%d' % closed_loopback_port()
        for name, argument, variable, compose in (
                ('personnel.sh', ['get', 'PRS-0001'], 'PERSONNEL_URL', 'uss-enterprise/personnel-v2/compose.yaml'),
                ('missions.sh', ['list'], 'MISSIONS_URL', 'uss-enterprise/missions/compose.yaml'),
                ('assets.sh', ['list'], 'ASSETS_URL', 'bash uss-enterprise/assets/start.sh start')):
            with self.subTest(name=name):
                result = self.run_script(name, argument, **{variable: url})
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(result.stdout, '')
                lines = result.stderr.strip().split('\n')
                self.assertEqual(len(lines), 1, result.stderr)
                self.assertIn('not running', lines[0])
                self.assertIn(url, lines[0])
                self.assertIn(compose if name == 'assets.sh' else 'docker compose -f ' + compose, lines[0])

    # --- a running service ------------------------------------------------------------------------------------------

    def test_missions_prints_pretty_xml_with_the_status_and_the_etag_on_standard_error(self):
        base = self.serve()
        result = self.run_script('missions.sh', ['get', 'ST-1'], MISSIONS_URL=base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.splitlines(), ['HTTP 200', 'ETag: "c-7"'])
        self.assertIn('\n  <missionId>ST-1</missionId>\n', result.stdout)
        self.assertIn('<title>Café</title>', result.stdout)
        method, path, headers, _ = Recorder.seen[0]
        self.assertEqual((method, path, headers['Accept']), ('GET', '/missions/ST-1', 'application/xml'))

    def test_missions_failure_status_exits_one_after_printing_it(self):
        result = self.run_script('missions.sh', ['get', 'ST-NONE'], MISSIONS_URL=self.serve())
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr.strip(), 'HTTP 404')

    # --- the Assets requests ----------------------------------------------------------------------------------------

    def test_assets_routes_and_filters_are_the_ones_of_the_contract(self):
        contract = json.loads(ASSETS_CONTRACT.read_text(encoding='utf-8'))
        reads = {path: sorted(parameter['name'] for parameter in (
            contract['components']['parameters'][reference['$ref'].rsplit('/', 1)[1]]
            for reference in item['get'].get('parameters', []))) for path, item in contract['paths'].items()}
        self.assertEqual(reads, {'/assets': ['category', 'kind', 'limit', 'offset', 'parentAssetId', 'status'],
                                 '/assets/{assetId}': ['assetId']})
        usage = (SCRIPTS / 'assets.sh').read_text(encoding='utf-8')
        for name in reads['/assets']:
            self.assertIn(name + '=', usage)

    def test_assets_requests(self):
        for args, line in (
                (['list'], 'GET http://127.0.0.1:8084/assets'),
                (['get', 'AST-0017'], 'GET http://127.0.0.1:8084/assets/AST-0017'),
                (['list', 'kind=SHUTTLE', 'limit=5'], 'GET http://127.0.0.1:8084/assets?kind=SHUTTLE&limit=5'),
                (['list', 'category=VEHICLE', 'status=ACTIVE', 'parentAssetId=AST-0001', 'offset=20', 'limit=50'],
                 'GET http://127.0.0.1:8084/assets?category=VEHICLE&status=ACTIVE&parentAssetId=AST-0001&offset=20&limit=50'),
                (['list', 'status=a b'], 'GET http://127.0.0.1:8084/assets?status=a%20b'),
                (['get', 'a/b?c'], 'GET http://127.0.0.1:8084/assets/a%2Fb%3Fc')):
            with self.subTest(args=args):
                head, body = self.dry('assets.sh', args)
                self.assertEqual(head, [line, 'Accept: application/json'])
                self.assertEqual(body, '')

    def test_the_assets_url_comes_from_the_environment(self):
        result = self.run_script('assets.sh', ['--dry-run', 'get', 'AST-0001'], ASSETS_URL='http://127.0.0.1:9/')
        self.assertEqual(result.stdout.split('\n')[0], 'GET http://127.0.0.1:9/assets/AST-0001')

    def test_assets_prints_pretty_json_with_the_status_on_standard_error_and_no_etag(self):
        result = self.run_script('assets.sh', ['list', 'kind=SHUTTLE'], ASSETS_URL=self.serve())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.splitlines(), ['HTTP 200'])
        self.assertEqual(json.loads(result.stdout), {'items': [{'assetId': 'AST-0017', 'name': 'Caf\u00e9'}]})
        self.assertIn('\n      "assetId": "AST-0017",\n', result.stdout)
        self.assertIn('Caf\u00e9', result.stdout)
        method, path, headers, _ = Recorder.seen[0]
        self.assertEqual((method, path, headers['Accept']), ('GET', '/assets?kind=SHUTTLE', 'application/json'))

    def test_assets_failure_status_exits_one_after_printing_the_body(self):
        result = self.run_script('assets.sh', ['get', 'AST-9999'], ASSETS_URL=self.serve())
        self.assertEqual(result.returncode, 1)
        self.assertIn('ASSET_NOT_FOUND', result.stdout)
        self.assertEqual(result.stderr.strip(), 'HTTP 404')

    def test_personnel_sends_exactly_what_the_dry_run_prints(self):
        base = self.serve() + '/soap/personnel-v2'
        _, expected = self.dry('personnel.sh', ['get', 'PRS-0001'])
        result = self.run_script('personnel.sh', ['get', 'PRS-0001'], PERSONNEL_URL=base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.strip(), 'HTTP 200')
        self.assertIn('\n      <id>PRS-0001</id>\n', result.stdout)
        method, path, headers, body = Recorder.seen[0]
        self.assertEqual((method, path), ('POST', '/soap/personnel-v2'))
        self.assertEqual(headers['Content-Type'], 'text/xml; charset=utf-8')
        self.assertEqual(headers['SOAPAction'], '"' + constant('NS') + ':GetPersonnelMember"')
        self.assertEqual(body.decode('utf-8'), expected)

    def test_personnel_fault_prints_the_body_and_exits_one(self):
        result = self.run_script('personnel.sh', ['get', 'PRS-9999'], PERSONNEL_URL=self.serve() + '/soap/personnel-v2')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Fault', result.stdout)
        self.assertEqual(result.stderr.strip(), 'HTTP 500')


if __name__ == '__main__':
    unittest.main()
