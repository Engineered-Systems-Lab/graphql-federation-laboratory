"""Offline fixture and WSDL checks. Python standard library; no service implementation."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'fixtures'
NS = 'urn:graphql-federation-lab:crew-personnel:v1'
SOAP = 'http://schemas.xmlsoap.org/soap/envelope/'
WSDL = 'http://schemas.xmlsoap.org/wsdl/'
BIND = 'http://schemas.xmlsoap.org/wsdl/soap/'
XS = 'http://www.w3.org/2001/XMLSchema'
XMLWS = ' \t\r\n'
# Canonical Git-content (LF) SHA-256 of the immutable datasets, as recorded in docs/INTEGRATION-NOTES.md. The manifest's
# raw-byte pins depend on the checkout's line endings, so identity is checked on the bytes with each CR that precedes an
# LF skipped, like the Java startup loader (D017); every other byte stays significant.
CANONICAL_LF_SHA256 = {
    'canonical/crew-v1-small-001.xml': 'daeebe24706e3345d3f14c320a8fb9eb866fcfea7ce2dc8f01ce1977bbc0a35e',
    'canonical/crew-v1-small-002.xml': '6cf7e7ec590fa247aa8f884916a4014ce86aa27276c7bcbe409abd65465da8b9',
}
Q = lambda name: f'{{{NS}}}{name}'
W = lambda name: f'{{{WSDL}}}{name}'
X = lambda name: f'{{{XS}}}{name}'
B = lambda name: f'{{{BIND}}}{name}'
S = lambda name: f'{{{SOAP}}}{name}'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    raw = path.read_bytes()
    # Reject DTDs before parsing. The XSD runner independently prohibits DTDs
    # and external resolution; neither checker retrieves external resources.
    require(b'<!DOCTYPE' not in raw.upper(), 'DTD prohibited')
    namespaces, stack, pending = {}, [{}], []
    for event, value in E.iterparse(path, events=('start-ns', 'start', 'end')):
        if event == 'start-ns':
            pending.append(value)
        elif event == 'start':
            current = dict(stack[-1]); current.update(pending); pending.clear()
            namespaces[id(value)] = current; stack.append(current)
            if len(stack) == 2:
                root = value
        else:
            stack.pop()
    return root, namespaces


def resolve(value, element, namespaces):
    if ':' in value:
        prefix, local = value.split(':', 1)
        require(prefix in namespaces[id(element)], 'Unbound QName prefix')
    else:
        prefix, local = '', value
    return '{' + namespaces[id(element)].get(prefix, '') + '}' + local


def text(root, name):
    node = root.find(Q(name))
    require(node is not None, f'Missing {name}')
    return node.text or ''


def boolean(value):
    v = value.strip(XMLWS)
    require(v in ('true', 'false', '1', '0'), 'Invalid boolean')
    return v in ('true', '1')


def semantic(element):
    """Expanded names/order/presence; preserve strings, type numeric/boolean values."""
    value = element.text or ''
    if len(element):
        require(not value.strip(XMLWS), 'Mixed content')
        value = ''
    elif element.tag in {Q(x) for x in ('offset', 'limit', 'totalCount')}:
        value = int(value)
    elif element.tag == Q('hasMore'):
        value = boolean(value)
    for child in element:
        require(not (child.tail or '').strip(XMLWS), 'Mixed child tail')
    return element.tag, value, tuple(semantic(child) for child in element)


def dataset(root):
    require(root.tag == Q('ListCrewMembersResponse'), 'Dataset container')
    records = root.findall(Q('crewMember'))
    ids = [text(r, 'crewId') for r in records]
    require(len(ids) == len(set(ids)), 'Duplicate crew keys')
    require(ids == sorted(ids), 'Dataset order')
    require(int(text(root, 'totalCount')) == len(records), 'Dataset count')
    require(int(text(root, 'offset')) == 0, 'Complete dataset offset')
    require(len(records) <= int(text(root, 'limit')) and not boolean(text(root, 'hasMore')), 'Incomplete dataset')
    parents = {}
    for r in records:
        key = text(r, 'crewId')
        s = r.find(Q('supervisorCrewId'))
        if s is not None:
            require(s.text in ids, 'Dangling supervisor')
            require(s.text != key, 'Self-reference')
            parents[key] = s.text
    for key in ids:
        seen = set()
        while key in parents:
            require(key not in seen, 'Supervisor cycle')
            seen.add(key); key = parents[key]
    return records


def soap(root, namespaces):
    require(root.tag == S('Envelope'), 'SOAP 1.1 Envelope required')
    require([x.tag for x in root] in ([S('Body')], [S('Header'), S('Body')]), 'Envelope structure')
    body = root.find(S('Body'))
    require(len(body) == 1, 'Exactly one body payload')
    payload = body[0]
    if payload.tag != S('Fault'):
        require(payload.tag in {Q(op + direction) for op in ('GetCrewMember', 'ListCrewMembers') for direction in ('Request', 'Response')}, 'Unknown wrapper')
        return
    require([x.tag for x in payload] == ['faultcode', 'faultstring', 'detail'], 'SOAP fault child order/qualification')
    detail = payload.find('detail')
    require(len(detail) == 1 and detail[0].tag == Q('CrewServiceFault'), 'Exactly one declared detail')
    code = text(detail[0], 'code')
    expected = 'Client' if code in ('InvalidRequest', 'CrewNotFound') else 'Server'
    fcode = payload.find('faultcode')
    require(resolve(fcode.text, fcode, namespaces) == S(expected), 'Wrong SOAP faultcode')
    if code == 'CrewNotFound':
        require(text(detail[0], 'field') == 'crewId', 'CrewNotFound field')


def wsdl():
    root, namespaces = read(ROOT / 'contracts/crew-personnel-v1.wsdl')
    schema, sn = read(ROOT / 'contracts/crew-personnel-v1.xsd')
    require(root.tag == W('definitions') and root.get('targetNamespace') == NS, 'WSDL namespace')
    require(schema.get('targetNamespace') == NS and schema.get('elementFormDefault') == 'qualified' and schema.get('attributeFormDefault') == 'unqualified', 'XSD namespace/form')
    require(not schema.findall('.//' + X('import')) and not schema.findall('.//' + X('include')), 'External schema dependencies')
    for node in schema.findall('.//' + X('element')):
        require(node.get('nillable') == 'false', 'Element must explicitly prohibit nil')
        require(node.get('default') is None and node.get('fixed') is None, 'Omission must not become empty/default')
    require(all(not schema.findall('.//' + X(x)) for x in ('any', 'anyAttribute', 'attribute', 'choice', 'all')), 'Unexpected XSD extension/order constructs')
    inline = root.find(W('types'))
    require(len(inline) == 1 and inline[0].tag == X('schema') and inline[0].get('targetNamespace') == NS, 'Inline schema')
    require(len(inline[0]) == 1 and inline[0][0].tag == X('include') and inline[0][0].get('schemaLocation') == 'crew-personnel-v1.xsd', 'Same-namespace include')
    ops = ('GetCrewMember', 'ListCrewMembers')
    expected_elements = {op + d for op in ops for d in ('Request', 'Response')} | {'CrewServiceFault'}
    require({e.get('name') for e in schema.findall(X('element'))} == expected_elements, 'Global wrapper set')
    messages = {e.get('name'): e for e in root.findall(W('message'))}
    require(set(messages) == {e + 'Message' for e in expected_elements}, 'WSDL messages')
    for name, message in messages.items():
        require(len(message) == 1 and message[0].tag == W('part'), 'Single part')
        require(resolve(message[0].get('element'), message[0], namespaces) == Q(name.removesuffix('Message')), 'Element-based wrapped part')
        require(message[0].get('type') is None, 'No type-based parts')
    ports = root.findall(W('portType')); bindings = root.findall(W('binding'))
    require(len(ports) == len(bindings) == 1, 'One portType and binding')
    require(resolve(bindings[0].get('type'), bindings[0], namespaces) == Q(ports[0].get('name')), 'Binding portType reference')
    sb = bindings[0].find(B('binding'))
    require(sb.attrib == {'style': 'document', 'transport': 'http://schemas.xmlsoap.org/soap/http'}, 'SOAP HTTP document binding')
    for parent in (ports[0], bindings[0]):
        operations = parent.findall(W('operation'))
        require([o.get('name') for o in operations] == list(ops), 'Exactly two operations')
        for op in operations:
            name = op.get('name')
            require(len(op.findall(W('input'))) == len(op.findall(W('output'))) == len(op.findall(W('fault'))) == 1, 'Operation messages and fault')
            f = op.find(W('fault')); require(f.get('name') == 'CrewServiceFault', 'Shared declared fault')
            if parent is ports[0]:
                for direction, suffix in [('input', 'Request'), ('output', 'Response'), ('fault', None)]:
                    n = op.find(W(direction)); expected = (name + suffix if suffix else 'CrewServiceFault') + 'Message'
                    require(resolve(n.get('message'), n, namespaces) == Q(expected), 'Message QName')
            else:
                require(op.find(B('operation')).attrib == {'soapAction': NS + ':' + name, 'style': 'document'}, 'SOAPAction')
                for direction in ('input', 'output'):
                    require(op.find(W(direction)).find(B('body')).attrib == {'use': 'literal'}, 'Literal body')
                require(f.find(B('fault')).attrib == {'name': 'CrewServiceFault', 'use': 'literal'}, 'Literal fault')
    require(not root.findall(W('service')), 'Deployment host/port are not contract choices')


def exchanges(manifest):
    for pair in manifest['exchanges']:
        req, _ = read(FIXTURES / pair['request']); res, _ = read(FIXTURES / pair['response']); source, _ = read(FIXTURES / pair['dataset'])
        records = dataset(source)
        require(text(res, 'datasetVersion') == text(source, 'datasetVersion'), pair['name'] + ': version')
        if req.tag == Q('GetCrewMemberRequest'):
            expected = [r for r in records if text(r, 'crewId') == text(req, 'crewId')]
        else:
            expected = records
            for field in ('department', 'dutyStatus'):
                n = req.find(Q(field))
                if n is not None:
                    expected = [r for r in expected if text(r, field) == n.text]
            expected.sort(key=lambda r: text(r, 'crewId'))
            count = len(expected)
            offset = int(text(req, 'offset')) if req.find(Q('offset')) is not None else 0
            limit = int(text(req, 'limit')) if req.find(Q('limit')) is not None else 20
            expected = expected[offset:offset + limit]
            require([int(text(res, k)) for k in ('totalCount', 'offset', 'limit')] == [count, offset, limit], pair['name'] + ': pagination metadata')
            require(boolean(text(res, 'hasMore')) == (offset + len(expected) < count), pair['name'] + ': hasMore')
            require(text(res, 'hasMore') in ('true', 'false'), 'Emit canonical boolean')
        require([semantic(x) for x in res.findall(Q('crewMember'))] == [semantic(x) for x in expected], pair['name'] + ': records')
        for n in res.iter():
            if n.tag in {Q(x) for x in ('totalCount', 'offset', 'limit')}:
                require(re.fullmatch(r'[0-9]+', n.text) is not None, 'Emit plain decimal')


def main():
    manifest = json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))
    expected_paths = {c['path'] for c in manifest['cases']}
    require(len(expected_paths) == len(manifest['cases']), 'Duplicate manifest path')
    require(expected_paths == {str(p.relative_to(FIXTURES)).replace('\\', '/') for p in FIXTURES.rglob('*.xml')}, 'Manifest covers every XML fixture')
    probes = json.loads((FIXTURES / manifest['scalarProbes']).read_text(encoding='utf-8'))
    require(len(probes) == 67 and len({p['name'] for p in probes}) == 67, '67 named scalar probes')
    for probe in probes:
        require(probe['base'] in expected_paths and probe['mutations'], 'Scalar base and edits')
        require(isinstance(probe['valid'], bool), 'Explicit scalar outcome')
    for fault in manifest['faultExpectations']:
        require(fault.get('request') in expected_paths or fault.get('requestProbe') in {p['name'] for p in probes}, 'Fault request reference')
    require(set(manifest['immutableSha256']) == set(CANONICAL_LF_SHA256), 'Immutable dataset set changed')
    for path, digest in CANONICAL_LF_SHA256.items():
        require(hashlib.sha256((FIXTURES / path).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == digest, 'Immutable dataset bytes changed: ' + path)
    wsdl()
    structural = 0
    versions = {}
    for case in manifest['cases']:
        if case['kind'] == 'payload':
            continue  # XSD checks, including expected rejections, belong to validate.py.
        error = None
        try:
            root, namespaces = read(FIXTURES / case['path'])
            if case['kind'] == 'dataset':
                records = dataset(root)
                if case['valid']:
                    version = text(root, 'datasetVersion')
                    content = tuple(semantic(r) for r in records)
                    require(version not in versions or versions[version] == content, 'Version reused with different dataset content')
                    versions[version] = content
            else:
                soap(root, namespaces)
        except (ValueError, E.ParseError) as exc:
            error = str(exc)
        require(bool(error) != case['valid'], f"Unexpected result for {case['path']}: {error or 'accepted'}")
        structural += 1
    # Compare the canonical record values directly to the authoritative Markdown table.
    specification = (ROOT.parents[1] / 'docs/CREW-PERSONNEL-V1.md').read_text(encoding='utf-8')
    frozen_rows = [[v.strip() for v in line.strip().strip('|').split('|')] for line in specification.splitlines() if line.startswith('| CRW-10')]
    base, _ = read(FIXTURES / manifest['canonical'])
    fields = 'crewId displayName rank department positionTitle dutyStatus supervisorCrewId'.split()
    actual = [[text(r, f) if r.find(Q(f)) is not None else 'omitted' for f in fields] for r in dataset(base)]
    require(len(frozen_rows) == 6 and actual == frozen_rows, 'Canonical data differs from frozen specification')
    expanded, _ = read(FIXTURES / manifest['expanded'])
    expanded_records = dataset(expanded)
    require(len(expanded_records) == 12, 'Expanded dataset must have 12 records')
    require([semantic(r) for r in expanded_records[:6]] == [semantic(r) for r in dataset(base)], 'Original six changed in 002')
    require([text(r, 'crewId') for r in expanded_records[6:]] == [f'CRW-{n}' for n in range(1053, 1059)], 'New permanent IDs')
    require(text(expanded_records[10], 'displayName') == 'Reginald Barclay', 'Barclay identity')
    exchanges(manifest)
    for fault in manifest['faultExpectations']:
        root, namespaces = read(FIXTURES / fault['response']); soap(root, namespaces)
        detail = root.find('.//' + Q('CrewServiceFault'))
        require(text(detail, 'code') == fault['code'] and fault['httpStatus'] == 500, 'Fault expectation')
        field = detail.find(Q('field'))
        require((field.text if field is not None else None) == fault.get('field'), 'Fault field expectation')
    trace = manifest['datasetReplacement']
    pages = [read(FIXTURES / p)[0] for p in trace['pages']]
    require([text(p, 'datasetVersion') for p in pages] == ['crew-v1-small-001', 'crew-v1-small-002'], '001 to 002 replacement')
    require([int(text(p, 'offset')) for p in pages] == [0, 2], 'Replacement offsets')
    require(int(text(pages[0], 'limit')) == 2 and len(pages[0].findall(Q('crewMember'))) == 2, 'Initial page size')
    # Model client accumulation with provenance: a repeated ID cannot hide stale data.
    accumulated = [(text(pages[0], 'datasetVersion'), semantic(r)) for r in pages[0].findall(Q('crewMember'))]
    version = text(pages[0], 'datasetVersion')
    if text(pages[1], 'datasetVersion') != version:
        accumulated.clear()
        version = text(pages[1], 'datasetVersion')
    require(accumulated == [], 'Discard old data and do not append changed-version offset 2')
    restart, _ = read(FIXTURES / trace['restartRequest'])
    require(int(text(restart, 'offset')) == 0, 'Replacement restart offset')
    restarted, _ = read(FIXTURES / trace['restartResponse'])
    require(text(restarted, 'datasetVersion') == version and int(text(restarted, 'offset')) == 0, 'Restart response version/offset')
    accumulated.extend((version, semantic(r)) for r in restarted.findall(Q('crewMember')))
    require(accumulated == [(version, semantic(r)) for r in expanded_records[:2]], 'Restart contains only first 002 page')
    print(f"PASS: WSDL QNames/binding/include; {structural} structure/readiness/protocol cases; six frozen records plus 12-record 002; {len(manifest['exchanges'])} semantic exchanges; fault and replacement expectations.")
    print('LIMITS: no service, HTTP calls, Java generation, WSDL-specific validator, restart/timing or consumer runtime tests. Dataset history/non-reuse is not provable from these snapshots.')


if __name__ == '__main__':
    main()
