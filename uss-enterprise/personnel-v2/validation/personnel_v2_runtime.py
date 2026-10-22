"""Personnel v2 checkpoint gates. No Git mutations or application-source changes."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
COMPONENT = ROOT / 'uss-enterprise/personnel-v2'
IMAGE = 'personnel-v2-validation:local'
NS = 'urn:graphql-federation-lab:personnel:v2'
SOAP = 'http://schemas.xmlsoap.org/soap/envelope/'


def run(argv, capture=False, timeout=900):
    result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=capture, timeout=timeout)
    if result.returncode:
        if capture:
            print(result.stdout, end=''); print(result.stderr, file=sys.stderr, end='')
        raise RuntimeError('Command failed: ' + repr(argv))
    return result.stdout.strip() if capture else None


def require(condition, message):
    if not condition:
        raise ValueError(message)


MAVEN_IMAGE = 'maven:3.9.11-eclipse-temurin-17@sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82'


def java():
    # JDK 17 and Maven run inside the image the components' Dockerfiles pin, so the host needs only Docker.
    result = subprocess.run(['docker', 'run', '--rm', MAVEN_IMAGE, 'java', '-version'], capture_output=True, text=True,
                            timeout=900)
    require(result.returncode == 0 and re.search(r'version "17[.\"]', result.stdout + result.stderr), 'JDK 17 is required')
    print(result.stdout + result.stderr, flush=True)
    for component in ('crew-personnel', 'personnel-v2'):
        run(['docker', 'run', '--rm', '-v', str(ROOT) + ':/work', '-v', 'personnel-v2-maven-cache:/root/.m2', '-w', '/work',
             MAVEN_IMAGE, 'mvn', '-B', '-ntp', '-f', 'uss-enterprise/' + component + '/pom.xml', 'clean', 'verify'])
    print('PASS: JDK 17 clean verify for unchanged v1 and Personnel v2.')


def container():
    print('Docker server: ' + run(['docker', 'version', '--format', '{{.Server.Version}}'], True))
    config = json.loads(run(['docker', 'compose', '-f', str(COMPONENT / 'compose.yaml'), 'config', '--format', 'json'], True))
    service = config['services']['personnel-v2']
    require(all(p['host_ip'] == '127.0.0.1' and p['target'] == 8082 for p in service['ports']), 'Compose must publish loopback only')
    run(['docker', 'build', '--progress=plain', '-t', IMAGE, str(COMPONENT)])
    metadata = json.loads(run(['docker', 'image', 'inspect', IMAGE], True))[0]
    require(metadata['Config']['User'] == '10001:10001', 'Container must run as the specified nonroot user')
    require('8082/tcp' in metadata['Config']['ExposedPorts'], 'Container port missing')
    print('PASS: pinned Dockerfile build, Compose loopback publication and nonroot image; image=' + metadata['Id'])


def http(url, data=None, action=None, timeout=10):
    headers = {'Content-Type': 'text/xml; charset=utf-8'}
    if action:
        headers['SOAPAction'] = '"' + NS + ':' + action + '"'
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


@contextmanager
def serving(version, profile='normal'):
    cid = run(['docker', 'run', '-d', '-p', '127.0.0.1::8082',
               '-e', 'PERSONNEL_DATASET_VERSION=' + version,
               '-e', 'PERSONNEL_FAILURE_PROFILE=' + profile, IMAGE], True)
    try:
        metadata = json.loads(run(['docker', 'inspect', cid], True))[0]
        binding = metadata['NetworkSettings']['Ports']['8082/tcp'][0]
        require(binding['HostIp'] == '127.0.0.1', 'Test publication must be loopback')
        address = 'http://127.0.0.1:' + binding['HostPort'] + '/soap/personnel-v2'
        deadline = time.monotonic() + 45
        while True:
            try:
                if http(address + '?wsdl', timeout=2)[0] == 200:
                    break
            except (URLError, TimeoutError, ConnectionError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError('Container failed readiness: ' + run(['docker', 'logs', cid], True))
            time.sleep(.25)
        yield address
    finally:
        run(['docker', 'rm', '-f', cid], True)


def soap():
    sys.path.insert(0, str(ROOT / 'uss-enterprise/crew-personnel/validation'))
    from xml_validation import E, parse, read
    xsd = E.XMLSchema(read(COMPONENT / 'contracts/personnel-v2.xsd'))
    q = lambda name: '{' + NS + '}' + name
    exchanges = 0

    def semantic(element):
        return element.tag, element.text if len(element) == 0 else None, tuple(semantic(e) for e in element)

    def call(address, operation, children='', fault=None, field=None):
        nonlocal exchanges
        payload = '<s:Envelope xmlns:s="' + SOAP + '"><s:Body><' + operation + 'Request xmlns="' + NS + '">' + children + '</' + operation + 'Request></s:Body></s:Envelope>'
        status, raw = http(address, payload.encode(), operation)
        exchanges += 1
        require(status == (500 if fault else 200), 'Unexpected HTTP status: ' + str(status))
        body = parse(raw).find('{' + SOAP + '}Body')
        require(body is not None and len(body) == 1, 'Expected one SOAP payload')
        result = body[0]
        if fault:
            require(result.tag == '{' + SOAP + '}Fault', 'Expected SOAP fault')
            detail = result.find('detail')
            require(detail is not None and len(detail) == 1, 'Expected one fault detail')
            xsd.assertValid(detail[0])
            require(detail[0].findtext(q('code')) == fault and detail[0].findtext(q('field')) == field, 'Wrong declared fault')
            code = result.find('faultcode')
            prefix, local = code.text.split(':')
            require(code.nsmap[prefix] == SOAP and local == ('Client' if fault in ('InvalidRequest', 'PersonnelNotFound') else 'Server'), 'Wrong SOAP fault QName')
        else:
            xsd.assertValid(result)
            require(result.tag == q(operation + 'Response'), 'Wrong response operation')
            require(len(result.findall(q('personnelMember'))) <= 100, 'Response exceeds ceiling')
        return result

    def ids(element):
        return [m.findtext(q('personnelId')) for m in element.findall(q('personnelMember'))]

    def snapshot(version):
        """The authoritative fixture of a snapshot: the whole response element and the members of a single-file snapshot, or only the
        members, in page order, of the paged package personnel-v2-large-004 (ten pages of 100 and a manifest)."""
        single = COMPONENT / 'datasets' / (version + '.xml')
        if single.is_file():
            root = read(single)
            return root, root.findall(q('personnelMember'))
        pages = sorted((COMPONENT / 'datasets' / version).glob('page-*.xml'))
        require(len(pages) == 10, 'The paged package must hold ten pages')
        return None, [member for page in pages for member in read(page).findall(q('personnelMember'))]

    # The default page of a list call is 20 members (the service's default limit).
    versions = ['personnel-v2-small-001', 'personnel-v2-small-002', 'personnel-v2-small-003', 'personnel-v2-large-004']
    wesley = []
    page_versions = []
    for version in versions:
        with serving(version) as address:
            whole, members = snapshot(version)
            total = len(members)
            actual = call(address, 'ListPersonnelMembers')
            if whole is not None:
                require(semantic(actual) == semantic(whole), 'Container snapshot differs from authoritative fixture')
            else:
                require(total == 1000 and actual.findtext(q('totalCount')) == str(total), 'Paged snapshot must hold 1000 people')
                require([semantic(m) for m in actual.findall(q('personnelMember'))] == [semantic(m) for m in members[:20]],
                        'The first page of the paged snapshot differs from authoritative fixture')
            page_versions.append(actual.findtext(q('datasetVersion')))
            for member in members:
                fetched = call(address, 'GetPersonnelMember', '<personnelId>' + member.findtext(q('personnelId')) + '</personnelId>')
                require(semantic(fetched.find(q('personnelMember'))) == semantic(member), 'Get differs from fixture')
                if member.findtext(q('personnelId')) == 'PRS-0714':
                    wesley.append(fetched.find(q('personnelMember')))
            for limit in (1, 2, 20, 100):
                accumulated = []
                for offset in range(0, total, limit):
                    page = call(address, 'ListPersonnelMembers', f'<offset>{offset}</offset><limit>{limit}</limit>')
                    accumulated += ids(page)
                    require(page.findtext(q('totalCount')) == str(total) and page.findtext(q('offset')) == str(offset) and page.findtext(q('limit')) == str(limit), 'Page metadata mismatch')
                    require(page.findtext(q('hasMore')) == str(offset + len(ids(page)) < total).lower(), 'hasMore mismatch')
                require(accumulated == [m.findtext(q('personnelId')) for m in members], 'Page traversal mismatch')
            for offset in (total, 2147483647):
                page = call(address, 'ListPersonnelMembers', f'<offset>{offset}</offset>')
                require(not ids(page) and page.findtext(q('hasMore')) == 'false', 'Beyond-end pagination mismatch')
            for department in (None, 'COMMAND', 'OPERATIONS', 'ENGINEERING', 'SCIENCE', 'MEDICAL', 'SECURITY', 'FLIGHT_OPERATIONS'):
                for status in (None, 'ACTIVE', 'ON_LEAVE', 'INACTIVE', 'DECEASED'):
                    children = (f'<department>{department}</department>' if department else '') + (f'<dutyStatus>{status}</dutyStatus>' if status else '')
                    page = call(address, 'ListPersonnelMembers', children)
                    matches = [m.findtext(q('personnelId')) for m in members
                               if (department is None or m.findtext(q('crewDetails') + '/' + q('department')) == department)
                               and (status is None or m.findtext(q('dutyStatus')) == status)]
                    require(ids(page) == matches[:20] and int(page.findtext(q('totalCount'))) == len(matches), 'Filter mismatch')
                    if total > 20:
                        everything = call(address, 'ListPersonnelMembers', children + '<limit>100</limit>')
                        require(ids(everything) == matches[:100] and int(everything.findtext(q('totalCount'))) == len(matches), 'Filter mismatch at the largest page')
            call(address, 'GetPersonnelMember', '<personnelId>PRS-0000</personnelId>', 'InvalidRequest', 'personnelId')
            call(address, 'GetPersonnelMember', '<personnelId>PRS-9999</personnelId>', 'PersonnelNotFound', 'personnelId')
            call(address, 'ListPersonnelMembers', '<limit>101</limit>', 'InvalidRequest', 'limit')
            document = parse(http(address + '?wsdl')[1])
            w = {'w': 'http://schemas.xmlsoap.org/wsdl/', 'x': 'http://www.w3.org/2001/XMLSchema'}
            require(not any(document.findall('w:' + n, w) for n in ('types','message','portType','binding')), 'Deployment redeclares binding')
            imported = document.find('w:import', w)
            status, raw = http(urljoin(address, imported.get('location')))
            require(status == 200, 'Imported WSDL unavailable')
            contract = parse(raw)
            require(contract.xpath('w:portType/w:operation/@name', namespaces=w) == ['GetPersonnelMember','ListPersonnelMembers'], 'Wrong WSDL operations')
            include = contract.find('w:types/x:schema/x:include', w)
            status, raw = http(urljoin(address, include.get('schemaLocation')))
            require(status == 200 and parse(raw).get('targetNamespace') == NS, 'Published schema unavailable')
    require(page_versions == versions, 'Version selection failed')
    require(wesley[0].find(q('civilianDetails')) is not None and wesley[1].find(q('crewDetails')) is not None, 'Wesley subtype transition failed')
    require(wesley[0].findtext(q('personnelId')) == wesley[1].findtext(q('personnelId')) == 'PRS-0714', 'Wesley stable identity failed')
    with serving(versions[1], 'unavailable') as address:
        call(address, 'ListPersonnelMembers', fault='ServiceUnavailable')
        call(address, 'GetPersonnelMember', '<personnelId>PRS-0000</personnelId>', 'InvalidRequest', 'personnelId')
    with serving(versions[1], 'slow') as address:
        started = time.monotonic()
        call(address, 'GetPersonnelMember', '<personnelId>PRS-9999</personnelId>', 'PersonnelNotFound', 'personnelId')
        require(time.monotonic() - started >= 2, 'Slow profile did not delay lookup miss')
    cid = run(['docker', 'run', '-d', '-e', 'PERSONNEL_DATASET_VERSION=unregistered', IMAGE], True)
    try:
        require(int(run(['docker', 'wait', cid], True, timeout=30)) != 0, 'Invalid dataset must fail startup')
    finally:
        run(['docker', 'rm', '-f', cid], True)
    print(f'PASS: {exchanges} container SOAP exchanges; all four snapshots (the paged package personnel-v2-large-004 of 1,000 people included), Get/List, all filters, page traversal, identity transition, faults, profiles, WSDL/XSD retrieval and invalid-dataset startup. All owned containers removed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gate', choices=['java', 'container', 'soap'])
    args = parser.parse_args()
    try:
        {'java': java, 'container': container, 'soap': soap}[args.gate]()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
