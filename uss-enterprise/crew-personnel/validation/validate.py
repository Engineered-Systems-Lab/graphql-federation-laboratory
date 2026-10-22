"""Frozen-XSD fixture, scalar, nil and Unicode checks plus structural validation."""
import json
import subprocess
import sys
from xml_validation import COMPONENT, NS, E, read, schema, require, expect_schema, cli

FIXTURES = COMPONENT / 'fixtures'
Q = lambda name: '{' + NS + '}' + name


def main():
    xsd = schema()
    manifest = json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))
    checked = 0
    for case in manifest['cases']:
        path = FIXTURES / case['path']
        if case['kind'] == 'protocol':
            if case['path'] == 'protocol/soap12.xml':
                continue
            try:
                read(path)
            except (ValueError, E.XMLSyntaxError):
                pass
            else:
                raise ValueError(f'Unsafe or malformed XML accepted: {case["path"]}')
        else:
            root = read(path)
            if case['kind'] == 'soap':
                names = {Q(n) for n in ('GetCrewMemberRequest', 'GetCrewMemberResponse',
                         'ListCrewMembersRequest', 'ListCrewMembersResponse', 'CrewServiceFault')}
                for node in root.iter():
                    if node.tag in names:
                        expect_schema(xsd, node, True, case['path'])
            else:
                expect_schema(xsd, root, case['valid'] or case['kind'] == 'dataset', case['path'])
        checked += 1
    scalars = json.loads((FIXTURES / manifest['scalarProbes']).read_text(encoding='utf-8'))
    for case in scalars:
        doc = read(FIXTURES / case['base'])
        roots = list(doc.iter(Q(case['payload'])))
        require(len(roots) == 1, f'Missing scalar base payload: {case["name"]}')
        root = roots[0]
        for edit in case['mutations']:
            if edit.get('append'):
                node = E.SubElement(root, Q(edit['append']))
            else:
                relative = '.' + edit['target'][edit['target'].index('/', 1):]
                nodes = root.xpath(relative, namespaces={'cp': NS})
                require(len(nodes) == 1, f'Missing scalar target: {case["name"]} / {edit["target"]}')
                node = nodes[0]
            node.text = edit['value']
        expect_schema(xsd, root, case['valid'], case['name'])
    probes = 0
    for relative in ('requests/get-picard.xml', 'requests/list-defaults.xml',
                     'requests/list-engineering-active.xml', 'requests/page-0.xml',
                     'canonical/crew-v1-small-001.xml', 'responses/get-picard.xml',
                     'faults/InvalidRequest-limit.xml'):
        doc = read(FIXTURES / relative)
        root = next(doc.iter(Q('CrewServiceFault'))) if relative.startswith('faults/') else doc
        for node in doc.iter():
            if not isinstance(node.tag, str) or not node.tag.startswith('{' + NS + '}'):
                continue
            for value in ('true', '1', 'false', '0'):
                key = '{http://www.w3.org/2001/XMLSchema-instance}nil'
                node.set(key, value)
                expect_schema(xsd, root, False, f'xsi:nil={value} on {node.tag} in {relative}')
                del node.attrib[key]
                probes += 1
    doc = read(FIXTURES / 'responses/get-picard.xml')
    name = next(doc.iter(Q('displayName')))
    for count, valid in ((100, True), (101, False)):
        name.text = '\U0001f680' * count
        expect_schema(xsd, doc, valid, f'{count} supplementary XML characters')
    print('PASS: 100 supplementary XML characters accepted; 101 rejected.', flush=True)
    print(f'PASS: XSD 1.0 compiled; {checked} fixture schema/security checks; '
          f'{probes} xsi:nil position/value probes; {len(scalars)} named scalar probes.', flush=True)
    return subprocess.run([sys.executable, '-B', str(COMPONENT / 'validation/validate_structure.py')]).returncode


if __name__ == '__main__':
    sys.exit(cli(main))
