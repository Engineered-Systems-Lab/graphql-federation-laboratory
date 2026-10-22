"""Offline Missions contract 1.0 checks: XSD structure, lexical forms and negative probes."""
from copy import deepcopy
from pathlib import Path
import re
import sys

# Reuse the secure offline parser, not the v1 schema or domain model.
COMPONENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT.parent / 'crew-personnel/validation'))
from xml_validation import E, read, require, expect_schema, cli

NS = 'urn:starfleet:missions:v1'
Q = lambda name: '{' + NS + '}' + name
FIXTURES = COMPONENT / 'fixtures/valid'
ENUMS = {
    'MissionType': 'DIPLOMATIC EXPLORATION SCIENTIFIC FIRST_CONTACT MEDICAL RESCUE HUMANITARIAN SECURITY TACTICAL TRANSPORT',
    'Classification': 'UNCLASSIFIED SECRET TOP_SECRET',
    'Status': 'PLANNED AUTHORIZED ACTIVE POSTPONED COMPLETED FAILED CANCELLED',
    'LocationType': 'PLANET STARBASE VESSEL SECTOR DEEP_SPACE ENTERPRISE OTHER',
    'IssuingAuthority': 'STARFLEET_COMMAND ENTERPRISE_COMMAND STARFLEET_MEDICAL STARFLEET_SCIENCE STARFLEET_SECURITY FEDERATION_COUNCIL',
    'Operation': 'CREATED UPDATED',
    'ErrorCode': 'INVALID_REQUEST INVALID_MISSION_ID MISSION_NOT_FOUND METHOD_NOT_ALLOWED RESOURCE_CONFLICT '
                 'ETAG_MISMATCH UNSUPPORTED_MEDIA_TYPE DOMAIN_VALIDATION_FAILED PRECONDITION_REQUIRED INTERNAL_ERROR',
}
MISSION_ORDER = ['missionId', 'title', 'type', 'classification', 'status', 'priority', 'stardate', 'durationHours',
                 'objective', 'location', 'issuingAuthority', 'commandingOfficerId', 'assignedCrewIds',
                 'participantIds', 'assignedAssetIds', 'estimatedCostCredits', 'actualCostCredits', 'outcome',
                 'lastUpdated']
CHANGE_ORDER = ['changeId', 'missionId', 'operation', 'changedAt', 'changedBy', 'orderedBy', 'previousStatus',
                'newStatus', 'estimatedCostCredits', 'estimatedCostCreditsChange', 'actualCostCredits',
                'actualCostCreditsChange', 'summary']


def child(root, name):
    return root.find(Q(name))


def set_text(root, path, value):
    node = root
    for part in path.split('/'):
        node = node.find(Q(part))
        require(node is not None, 'Probe path missing: ' + path)
    node.text = value
    return root


def remove(root, name):
    node = child(root, name)
    require(node is not None, 'Probe element missing: ' + name)
    root.remove(node)
    return root


def probe(xsd, base, label, valid, mutate):
    sample = deepcopy(base)
    mutate(sample)
    expect_schema(xsd, sample, valid, label)


def check_text(xsd, base, path, cases):
    for value, valid in cases:
        probe(xsd, base, f'{path}={value!r}', valid, lambda root, v=value: set_text(root, path, v))


def main():
    xsd_path = COMPONENT / 'contracts/missions-v1.0.xsd'
    schema_doc = read(xsd_path)
    require(schema_doc.get('targetNamespace') == NS and schema_doc.get('version') == '1.0', 'Namespace/version')
    xsd = E.XMLSchema(schema_doc)

    # Contract surface: roots, enums and fixed sequences.
    require(sorted(e.get('name') for e in schema_doc.findall('{http://www.w3.org/2001/XMLSchema}element'))
            == ['changeList', 'error', 'mission', 'missionList'], 'Root representations')
    for name, tokens in ENUMS.items():
        found = schema_doc.xpath("//x:simpleType[@name=$n]//x:enumeration/@value",
                                 namespaces={'x': 'http://www.w3.org/2001/XMLSchema'}, n=name)
        require(found == tokens.split(), 'Enum drift: ' + name)
    for type_name, order in (('Mission', MISSION_ORDER), ('Change', CHANGE_ORDER)):
        found = schema_doc.xpath("//x:complexType[@name=$n]/x:sequence/x:element/@name",
                                 namespaces={'x': 'http://www.w3.org/2001/XMLSchema'}, n=type_name)
        require(found == order, 'Element order drift: ' + type_name)
    require(not schema_doc.xpath('//x:attribute|//x:any|//x:anyAttribute|//x:unique|//x:key|//x:keyref|//@nillable',
                                 namespaces={'x': 'http://www.w3.org/2001/XMLSchema'}), 'No attributes, wildcards, identity constraints or nil')

    # Valid fixtures.
    docs = {path.name: read(path) for path in sorted(FIXTURES.glob('*.xml'))}
    require(len(docs) == 6, 'Fixture inventory')
    for name, doc in docs.items():
        expect_schema(xsd, doc, True, name)
    mission = docs['mission-response.xml']
    post = docs['mission-post-input.xml']
    changes = docs['change-list.xml']

    # Whole-document structure.
    probe(xsd, mission, 'unknown element', False, lambda r: E.SubElement(r, Q('extra')))
    probe(xsd, mission, 'unknown attribute', False, lambda r: r.set('extra', '1'))
    probe(xsd, mission, 'wrong namespace', False, lambda r: r.__setattr__('tag', '{urn:other}mission'))
    probe(xsd, mission, 'wrong order', False, lambda r: r.insert(0, r.find(Q('lastUpdated'))))
    probe(xsd, mission, 'xsi:nil', False, lambda r: r.find(Q('outcome')).set('{http://www.w3.org/2001/XMLSchema-instance}nil', 'true'))
    for required in ('title', 'type', 'classification', 'status', 'priority', 'stardate', 'durationHours',
                     'objective', 'location', 'issuingAuthority', 'assignedCrewIds', 'participantIds', 'assignedAssetIds'):
        probe(xsd, mission, 'missing ' + required, False, lambda r, n=required: remove(r, n))
    for optional in ('missionId', 'commandingOfficerId', 'estimatedCostCredits', 'actualCostCredits', 'outcome', 'lastUpdated'):
        probe(xsd, mission, 'omitted ' + optional, True, lambda r, n=optional: remove(r, n))
    probe(xsd, mission, 'repeated scalar', False, lambda r: r.insert(2, deepcopy(r.find(Q('title')))))
    probe(xsd, mission, 'repeated container', False, lambda r: r.append(deepcopy(r.find(Q('assignedAssetIds')))))
    probe(xsd, mission, 'location missing name', False, lambda r: r.find(Q('location')).remove(r.find(Q('location')).find(Q('name'))))
    probe(xsd, mission, 'location order', False,
          lambda r: r.find(Q('location')).insert(0, r.find(Q('location')).find(Q('name'))))
    for optional in ('coordinates', 'travelVector'):
        probe(xsd, mission, 'omitted ' + optional, True,
              lambda r, n=optional: r.find(Q('location')).remove(r.find(Q('location')).find(Q(n))))

    # Enumerations are exact and case-sensitive.
    for path, tokens in (('type', ENUMS['MissionType']), ('classification', ENUMS['Classification']),
                         ('status', ENUMS['Status']), ('location/type', ENUMS['LocationType']),
                         ('issuingAuthority', ENUMS['IssuingAuthority'])):
        check_text(xsd, mission, path, [(t, True) for t in tokens.split()]
                   + [(tokens.split()[0].lower(), False), (' ' + tokens.split()[0], False), ('', False), ('UNKNOWN', False)])

    # Identifiers.
    check_text(xsd, mission, 'missionId', [
        ('ST-000000000', True), ('ST-ZZZZZZZZZ', True), ('ST-0000000a1', False), ('ST-00000000', False),
        ('ST-0000000000', False), ('XX-000000001', False), (' ST-000000001', False), ('ST-000000001\n', False)])
    check_text(xsd, mission, 'commandingOfficerId', [
        ('C-1', True), ('C-2047', True), ('C-0', False), ('C-01', False), ('C-', False), ('c-1', False),
        ('C--1', False), ('C-+1', False), ('P-1', False), ('O-1', False), ('CRW-2047', False), (' C-1', False), ('C-1 ', False)])

    def collection(container, member, ok, bad):
        def build(values):
            def apply(root):
                holder = root.find(Q(container))
                for old in list(holder):
                    holder.remove(old)
                for value in values:
                    E.SubElement(holder, Q(member)).text = value
            return apply
        for value in ok:
            probe(xsd, mission, f'{container}:{value}', True, build([value]))
        for value in bad:
            probe(xsd, mission, f'{container}:{value!r}', False, build([value]))
        probe(xsd, mission, container + ' empty', True, build([]))
        return build

    collection('assignedCrewIds', 'crewId', ['C-1', 'C-100000'], ['P-1', 'O-1', 'C-0', 'C-01', 'SH-1'])
    collection('participantIds', 'participantId', ['P-1', 'O-1', 'P-99'], ['C-1', 'P-0', 'O-01', 'SH-1', 'p-1'])
    collection('assignedAssetIds', 'assetId', ['SH-17', 'AB-1', 'ABCDE-1'], ['A-1', 'ABCDEF-1', 'sh-17', 'SH-0', 'SH-017', 'C-1'])
    # Wrong member element name for a container is a schema failure.
    probe(xsd, mission, 'generic id member', False,
          lambda r: r.find(Q('assignedCrewIds')).append(E.Element(Q('id'))))
    # Cardinality maxima: crew 0..100, assets 0..50, participants unbounded. Duplicates are NOT schema errors.
    def many(container, member, prefix, count):
        def apply(root):
            holder = root.find(Q(container))
            for old in list(holder):
                holder.remove(old)
            for number in range(1, count + 1):
                E.SubElement(holder, Q(member)).text = f'{prefix}-{number}'
        return apply
    probe(xsd, mission, 'crew 100', True, many('assignedCrewIds', 'crewId', 'C', 100))
    probe(xsd, mission, 'crew 101', False, many('assignedCrewIds', 'crewId', 'C', 101))
    probe(xsd, mission, 'assets 50', True, many('assignedAssetIds', 'assetId', 'SH', 50))
    probe(xsd, mission, 'assets 51', False, many('assignedAssetIds', 'assetId', 'SH', 51))
    probe(xsd, mission, 'participants 500', True, many('participantIds', 'participantId', 'P', 500))
    def duplicate_crew(root):
        holder = root.find(Q('assignedCrewIds'))
        holder.append(deepcopy(holder[0]))
    probe(xsd, mission, 'duplicates are a domain failure, not a schema failure', True, duplicate_crew)

    # Text: code-point bounds; whitespace-only is domain-level (schema-valid).
    astral = '\U0001F680'
    for path, limit in (('title', 120), ('objective', 2000), ('location/name', 120), ('outcome', 2000)):
        check_text(xsd, mission, path, [
            ('x' * limit, True), ('x' * (limit + 1), False), ('', False),
            (astral * limit, True), (astral * (limit + 1), False),
            ('   ', True), (' lead and trail ', True)])
    for path in ('location/coordinates', 'location/travelVector'):
        check_text(xsd, mission, path, [('x' * 120, True), ('x' * 121, False), ('', False), (astral * 120, True), (astral * 121, False)])

    # Numbers and dates.
    check_text(xsd, mission, 'priority', [(str(n), True) for n in range(1, 6)]
               + [('0', False), ('6', False), ('01', False), ('+1', False), ('1.0', False), (' 1', False), ('', False)])
    check_text(xsd, mission, 'durationHours', [
        ('1', True), ('9', True), ('10', True), ('999', True), ('1000', True), ('8699', True), ('8700', True),
        ('8759', True), ('8760', True), ('0', False), ('8761', False), ('8800', False), ('9999', False),
        ('01', False), ('+5', False), ('1e2', False), ('72.0', False), (' 72', False), ('72 ', False), ('-1', False)])
    check_text(xsd, mission, 'stardate', [
        ('43000.00', True), ('43125.80', True), ('43125.85', True), ('48999.95', True), ('45000.05', True),
        ('42999.95', False), ('49000.00', False), ('43125.8', False), ('43125.81', False), ('43125.805', False),
        ('4312.80', False), ('43125', False), ('+43125.80', False), ('-43125.80', False), ('43125,80', False), (' 43125.80', False)])
    cost_ok = ['0.00', '0.01', '10.50', '140000.00', '9999999999999.99', '1234567890123.45']
    cost_bad = ['0', '0.0', '1.5', '1.500', '00.00', '01.00', '-0.00', '-1.00', '+1.00', '1e3', 'NaN', 'INF', '1,00',
                '10000000000000.00', '99999999999999.99', ' 1.00', '1.00 ', '.50']
    for path in ('estimatedCostCredits', 'actualCostCredits'):
        check_text(xsd, mission, path, [(v, True) for v in cost_ok] + [(v, False) for v in cost_bad])
    check_text(xsd, mission, 'lastUpdated', [
        ('2366-10-14T19:42:31.472Z', True), ('2366-02-29T00:00:00.000Z', True), ('2366-12-31T23:59:59.999Z', True),
        ('2366-10-14T19:42:31Z', False), ('2366-10-14T19:42:31.47Z', False), ('2366-10-14T19:42:31.4720Z', False),
        ('2366-10-14T19:42:31.472+00:00', False), ('2366-10-14T19:42:31.472', False), ('2366-10-14 19:42:31.472Z', False),
        ('2366-13-14T19:42:31.472Z', False), ('2366-04-31T19:42:31.472Z', False), ('2366-02-30T19:42:31.472Z', False),
        ('2366-10-14T24:00:00.000Z', False), ('2366-10-14T19:60:00.000Z', False), ('0000-10-14T19:42:31.472Z', False),
        ('2366-10-14T19:42:31.472z', False),
        ('2010-06-01T00:00:00.000Z', True), ('1999-12-31T23:59:59.999Z', True), ('9999-12-31T23:59:59.999Z', True),
        ('0001-01-01T00:00:00.000Z', True)])

    # POST input is a mission without service-owned fields; PUT input carries missionId only.
    require(child(post, 'missionId') is None and child(post, 'lastUpdated') is None, 'POST fixture shape')
    probe(xsd, post, 'PUT shape with missionId', True,
          lambda r: r.insert(0, E.fromstring('<missionId xmlns="%s">ST-000000001</missionId>' % NS)))

    # Change representation.
    first = changes.findall(Q('change'))[0]
    check_change = lambda label, valid, fn: probe(xsd, changes, label, valid, lambda r: fn(r.findall(Q('change'))[0]))
    for name in ('changeId', 'missionId', 'operation', 'changedAt', 'changedBy', 'orderedBy', 'newStatus', 'summary'):
        check_change('missing ' + name, False, lambda c, n=name: remove(c, n))
    for name in ('previousStatus', 'estimatedCostCredits', 'estimatedCostCreditsChange'):
        probe(xsd, changes, 'omitted ' + name, True,
              lambda r, n=name: [c.remove(c.find(Q(n))) for c in r.findall(Q('change')) if c.find(Q(n)) is not None])
    for value, valid in (('1', True), ('17', True), ('0', False), ('01', False), ('+1', False), ('-1', False), ('1.0', False), (' 1', False), ('', False)):
        check_change('changeId=' + repr(value), valid, lambda c, v=value: set_text(c, 'changeId', v))
    for value, valid in (('C-1', True), ('P-1', False), ('O-1', False), ('C-0', False)):
        check_change('changedBy=' + value, valid, lambda c, v=value: set_text(c, 'changedBy', v))
        check_change('orderedBy=' + value, valid, lambda c, v=value: set_text(c, 'orderedBy', v))
    for value, valid in (('CREATED', True), ('UPDATED', True), ('DELETED', False), ('created', False)):
        check_change('operation=' + value, valid, lambda c, v=value: set_text(c, 'operation', v))
    for value, valid in (('x' * 256, True), ('x' * 257, False), (astral * 256, True), (astral * 257, False), ('', False),
                         (' ', False), ('\t\n ', False), ('   a   ', True),
                         ('\u3000', False), ('\u2003 \u1680', False), ('\u2028\u2029\u205f', False),
                         ('\u2000\u2006\u2008\u200a', False),
                         ('\u00a0', True), ('\u2007', True), ('\u202f', True), ('\u0085', True), ('\u180e', True),
                         ('\u200b', True), ('\ufeff', True), ('\u3000x', True)):
        check_change('summary len', valid, lambda c, v=value: set_text(c, 'summary', v))
    second = changes.findall(Q('change'))[1]
    for value, valid in (('15000.00', True), ('0.00', True), ('-15000.00', True), ('-0.01', True), ('-0.10', True),
                         ('9999999999999.99', True), ('-9999999999999.99', True), ('-0.00', False), ('+1.00', False),
                         ('1.0', False), ('-', False), ('--1.00', False), ('-00.10', False), ('10000000000000.00', False),
                         ('-10000000000000.00', False)):
        for name in ('estimatedCostCreditsChange',):
            probe(xsd, changes, f'{name}={value}', valid,
                  lambda r, v=value, n=name: set_text(r.findall(Q('change'))[1], n, v))
    probe(xsd, changes, 'actual change field', True, lambda r: None)
    # Negative signed values are not allowed in the resulting (non-negative) amount fields.
    probe(xsd, changes, 'negative resulting cost', False,
          lambda r: set_text(r.findall(Q('change'))[1], 'estimatedCostCredits', '-1.00'))

    # Lists: metadata first, then direct members; no wrapper; empty page valid.
    listing = docs['mission-list.xml']
    probe(xsd, listing, 'members before metadata', False, lambda r: r.insert(0, r.find(Q('mission'))))
    probe(xsd, listing, 'extra wrapper', False,
          lambda r: (lambda w: (r.remove(r.find(Q('mission'))), r.append(w)))(E.Element(Q('missions'))))
    for path, cases in (
            ('page', [('1', True), ('999999', True), ('0', False), ('01', False), ('-1', False), ('+1', False), ('', False)]),
            ('pageSize', [('1', True), ('20', True), ('50', True), ('0', False), ('51', False), ('050', False), ('+5', False)]),
            ('totalCount', [('0', True), ('21', True), ('00', False), ('-1', False), ('1.0', False)]),
            ('totalPages', [('0', True), ('2', True), ('01', False), ('-1', False)])):
        check_text(xsd, listing, path, cases)
    for name in ('page', 'pageSize', 'totalCount', 'totalPages'):
        probe(xsd, listing, 'missing ' + name, False, lambda r, n=name: remove(r, n))
        probe(xsd, changes, 'changeList missing ' + name, False, lambda r, n=name: remove(r, n))
    probe(xsd, changes, 'changeList with mission member', False,
          lambda r: r.append(deepcopy(listing.find(Q('mission')))))
    probe(xsd, listing, 'missionList with change member', False,
          lambda r: r.append(deepcopy(first)))

    # Errors.
    error = docs['error.xml']
    probe(xsd, error, 'empty message', False, lambda r: set_text(r, 'message', ''))
    for value, valid in (('x' * 1000, True), ('x' * 1001, False), (astral * 1000, True), (astral * 1001, False)):
        probe(xsd, error, 'message length', valid, lambda r, v=value: set_text(r, 'message', v))
    probe(xsd, error, 'unknown code', False, lambda r: set_text(r, 'code', 'INVALID_STATUS_TRANSITION'))
    probe(xsd, error, 'retired 503 code', False, lambda r: set_text(r, 'code', 'SERVICE_UNAVAILABLE'))
    probe(xsd, error, 'missing code', False, lambda r: remove(r, 'code'))
    probe(xsd, error, 'swapped order', False, lambda r: r.insert(0, r.find(Q('message'))))

    # Fixture hygiene.
    for path in FIXTURES.glob('*.xml'):
        text = path.read_text(encoding='utf-8')
        require('<!DOCTYPE' not in text and '<!ENTITY' not in text, 'DTD/entity in fixture: ' + path.name)
        require(re.search(r'xsi:|schemaLocation', text) is None, 'Schema hints in fixture: ' + path.name)

    # Compatible minor: every 1.0 wire document remains accepted, and the only
    # semantic schema addition is MAINTENANCE. Published 1.0 is never rewritten.
    minor_path = COMPONENT / 'contracts/missions-v1.1.xsd'
    minor_doc = read(minor_path)
    require(minor_doc.get('version') == '1.1' and minor_doc.get('targetNamespace') == NS, 'Minor version/namespace')
    minor = E.XMLSchema(minor_doc)
    for name, doc in docs.items(): expect_schema(minor, doc, True, '1.1:' + name)
    example = read(COMPONENT / 'fixtures/v1.1/maintenance-response.xml')
    expect_schema(minor, example, True, '1.1:MAINTENANCE')
    expect_schema(xsd, example, False, '1.0:MAINTENANCE remains unknown')
    maintenance = minor_doc.xpath("//x:simpleType[@name='MissionType']//x:enumeration[@value='MAINTENANCE']", namespaces={'x':'http://www.w3.org/2001/XMLSchema'})
    require(len(maintenance) == 1, 'Exactly one MAINTENANCE addition')
    maintenance[0].getprevious().tail = schema_doc.xpath("//x:simpleType[@name='MissionType']//x:enumeration[@value='TRANSPORT']", namespaces={'x':'http://www.w3.org/2001/XMLSchema'})[0].tail
    maintenance[0].getparent().remove(maintenance[0])
    minor_doc.set('version','1.0')
    # Documentation changes explain the minor; wire schema structure is exact.
    base_copy = deepcopy(schema_doc)
    for doc in (base_copy,minor_doc):
        for annotation in doc.findall('{http://www.w3.org/2001/XMLSchema}annotation'): doc.remove(annotation)
    require(E.tostring(base_copy,method='c14n') == E.tostring(minor_doc,method='c14n'), 'Unexpected 1.1 wire change')
    print('PASS: compatible 1.1 MAINTENANCE addition, 1.0 fixture compatibility and preserved 1.0 rejection.')

    print('PASS: Missions XSD 1.0 contract surface, six valid fixtures and enum/order/identifier/text/number/date/collection/list/change/error negative probes.')
    print('LIMITS: offline XSD 1.0 only. Status-dependent rules, duplicates, whitespace-only text, message-role presence, headers, '
          'media negotiation, HTTP and persistence belong to the implementation and are not established here.')


if __name__ == '__main__':
    sys.exit(cli(main))
