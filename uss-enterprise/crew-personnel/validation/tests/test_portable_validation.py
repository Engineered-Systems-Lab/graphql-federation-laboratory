"""Portability, XML security, failure propagation and SOAP transport regressions."""
import importlib.util
import copy
import json
from pathlib import Path
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
VALIDATION = ROOT / 'uss-enterprise/crew-personnel/validation'
sys.path.insert(0, str(VALIDATION))
import xml_validation as xml
import smoke
sys.path.pop(0)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PortableValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.xsd = xml.schema()
        cls.fixtures = xml.COMPONENT / 'fixtures'

    def fault(self):
        return (self.fixtures / 'faults/CrewNotFound-crewId.xml').read_bytes()

    def check_fault(self, raw, status=500):
        return smoke.check_response(raw, status, 'GetCrewMember', 'CrewNotFound', 'crewId', 'crew-v1-small-002', self.xsd)

    def test_dtd_rejected_across_encodings(self):
        text = '<?xml version="1.0" encoding="{}"?><!DOCTYPE x [<!ENTITY a "secret">]><x>&a;</x>'
        for encoding in ('utf-8', 'utf-16', 'utf-32'):
            with self.subTest(encoding=encoding), self.assertRaises((ValueError, xml.E.XMLSyntaxError)):
                xml.parse(text.format(encoding).encode(encoding))

    def test_external_dtd_and_entity_rejected(self):
        for text in ('<!DOCTYPE x SYSTEM "file:///definitely-absent.dtd"><x/>',
                     '<!DOCTYPE x [<!ENTITY a SYSTEM "http://127.0.0.1:1/secret">]><x>&a;</x>'):
            with self.subTest(text=text), self.assertRaises((ValueError, xml.E.XMLSyntaxError)):
                xml.parse(text.encode())

    def test_external_schema_include_rejected(self):
        root = xml.parse(b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:include schemaLocation="file:///absent.xsd"/></xs:schema>')
        with self.assertRaises((ValueError, xml.E.XMLSchemaParseError)):
            xml.E.XMLSchema(root)

    def test_instance_schema_hint_not_loaded(self):
        root = xml.read(self.fixtures / 'requests/get-picard.xml')
        root.set('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation', xml.NS + ' http://127.0.0.1:1/not-used.xsd')
        self.xsd.assertValid(root)

    def test_unicode_boundary(self):
        root = xml.read(self.fixtures / 'responses/get-picard.xml')
        node = root.find('.//' + smoke.Q('displayName'))
        for count, expected in ((100, True), (101, False)):
            node.text = '\U0001f680' * count
            self.assertEqual(self.xsd.validate(root), expected)

    def test_fault_http_status(self):
        self.check_fault(self.fault())
        with self.assertRaisesRegex(ValueError, 'HTTP status'):
            self.check_fault(self.fault(), 200)

    def test_fault_qname_and_field(self):
        for target, value in (('faultcode', 'wrong:Client'), ('.//' + smoke.Q('field'), 'limit')):
            root = xml.parse(self.fault())
            node = root.find('.//' + target) if target == 'faultcode' else root.find(target)
            node.text = value
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.check_fault(xml.E.tostring(root))

    def test_duplicate_soap_payload_rejected(self):
        root = xml.parse(self.fault())
        root.find(smoke.S('Body')).append(xml.E.Element(smoke.Q('GetCrewMemberResponse')))
        with self.assertRaisesRegex(ValueError, 'Exactly one'):
            self.check_fault(xml.E.tostring(root))

    def test_schema_invalid_fault_rejected(self):
        root = xml.parse(self.fault())
        node = root.find('.//' + smoke.Q('message'))
        node.getparent().remove(node)
        with self.assertRaises(xml.E.DocumentInvalid):
            self.check_fault(xml.E.tostring(root))

    def test_wrong_dataset_and_operation_rejected(self):
        payload = (self.fixtures / 'responses/get-picard.xml').read_bytes()
        raw = b'<s:Envelope xmlns:s="' + xml.SOAP.encode() + b'"><s:Body>' + xml.E.tostring(xml.parse(payload)) + b'</s:Body></s:Envelope>'
        for operation, version in (('GetCrewMember', 'wrong'), ('ListCrewMembers', 'crew-v1-small-001')):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                smoke.check_response(raw, 200, operation, None, None, version, self.xsd)

    def test_package_propagates_generator_failure(self):
        runner = load('package_validation', VALIDATION / 'validate_003.py')
        with patch.object(sys, 'argv', ['validate_003.py', '--package', 'path with spaces']), patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 9)) as run:
            self.assertEqual(runner.main(), 9)
            self.assertEqual(run.call_args.args[0][-1], 'path with spaces')

    def test_checkpoint_policy_and_profile_use_same_python_command(self):
        policy = json.loads((ROOT / 'project-governance/config/checkpoint-policy.json').read_text())
        profiles = json.loads((ROOT / 'project-governance/config/checkpoint-profiles.json').read_text())
        check = next(c for c in profiles['profiles']['crew-offline']['checks'] if c['id'] == 'component-offline')
        self.assertEqual(check['argv'], policy['commands']['component-offline'])
        self.assertEqual(check['argv'], ['{python}', '-B', 'uss-enterprise/crew-personnel/validation/validate.py'])

    def run_smoke(self, profile, version):
        fixtures = self.fixtures
        requests = []
        large = []
        if version.endswith('003'):
            for index in range(8):
                large.extend(xml.read(xml.COMPONENT / f'datasets/released/crew-v1-large-003/page-{index:03}.xml').findall(smoke.Q('crewMember')))

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                request = xml.parse(self.rfile.read(int(self.headers['Content-Length'])))
                payload = request.find(smoke.S('Body'))[0]
                operation = xml.E.QName(payload).localname.removesuffix('Request')
                requests.append((self.headers.get('SOAPAction'), operation))
                if payload.findtext(smoke.Q('limit')) == '0':
                    path = 'faults/InvalidRequest-limit.xml'
                elif profile == 'unavailable':
                    path = 'faults/ServiceUnavailable.xml'
                elif payload.findtext(smoke.Q('crewId')) == 'CRW-9999':
                    path = 'faults/CrewNotFound-crewId.xml'
                else:
                    path = 'responses/get-picard.xml' if operation == 'GetCrewMember' else 'responses/page-2.xml'
                root = xml.read(fixtures / path)
                status = 500 if path.startswith('faults/') else 200
                if status == 200:
                    if large:
                        root = xml.E.Element(smoke.Q(operation + 'Response'), nsmap={None: xml.NS})
                        xml.E.SubElement(root, smoke.Q('datasetVersion')).text = version
                        if operation == 'GetCrewMember':
                            crew_id = payload.findtext(smoke.Q('crewId'))
                            root.append(copy.deepcopy(next(r for r in large if r.findtext(smoke.Q('crewId')) == crew_id)))
                        else:
                            duty = payload.findtext(smoke.Q('dutyStatus'))
                            matches = [r for r in large if duty is None or r.findtext(smoke.Q('dutyStatus')) == duty]
                            offset = int(payload.findtext(smoke.Q('offset'), '0'))
                            limit = int(payload.findtext(smoke.Q('limit'), '20'))
                            page = matches[offset:offset + limit]
                            root.extend(copy.deepcopy(page))
                            for key, value in [('totalCount', len(matches)), ('offset', offset), ('limit', limit),
                                               ('hasMore', str(offset + len(page) < len(matches)).lower())]:
                                xml.E.SubElement(root, smoke.Q(key)).text = str(value)
                    root.find(smoke.Q('datasetVersion')).text = version
                    count = root.find(smoke.Q('totalCount'))
                    if count is not None and not large:
                        count.text = '6' if version.endswith('001') else '12'
                    envelope = xml.E.Element(smoke.S('Envelope'), nsmap={'s': xml.SOAP})
                    xml.E.SubElement(envelope, smoke.S('Body')).append(root)
                    root = envelope
                self.send_response(status)
                self.send_header('Content-Type', 'text/xml; charset=utf-8')
                self.end_headers()
                self.wfile.write(xml.E.tostring(root))

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run([sys.executable, '-B', str(VALIDATION / 'smoke.py'), '--endpoint',
                                     f'http://127.0.0.1:{server.server_port}/soap/crew-personnel',
                                     '--profile', profile, '--dataset-version', version], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(requests), (21 if large else 4) if profile == 'normal' else 3)
            for action, operation in requests:
                self.assertEqual(action, f'"{xml.NS}:{operation}"')
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_normal_http_cli_001(self):
        self.run_smoke('normal', 'crew-v1-small-001')

    def test_normal_http_cli_002(self):
        self.run_smoke('normal', 'crew-v1-small-002')

    def test_normal_http_cli_003(self):
        self.run_smoke('normal', 'crew-v1-large-003')

    def test_unavailable_http_cli_003(self):
        self.run_smoke('unavailable', 'crew-v1-large-003')

    def test_unavailable_http_cli(self):
        self.run_smoke('unavailable', 'crew-v1-small-002')


if __name__ == '__main__':
    unittest.main()
