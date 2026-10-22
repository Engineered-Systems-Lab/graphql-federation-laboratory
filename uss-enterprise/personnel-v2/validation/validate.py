"""Offline Personnel v2 contract, dataset integrity and identity regression checks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

# Reuse the secure offline parser, not the v1 schema or domain model.
COMPONENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT.parent / 'crew-personnel/validation'))
from xml_validation import E, read, require, expect_schema, cli

NS = 'urn:graphql-federation-lab:personnel:v2'
Q = lambda name: '{' + NS + '}' + name
X = {'x': 'http://www.w3.org/2001/XMLSchema', 'w': 'http://schemas.xmlsoap.org/wsdl/',
     's': 'http://schemas.xmlsoap.org/wsdl/soap/'}
HASHES = {
    'personnel-v2-small-001': 'cecd2f407ccfd47356b07fc7d11b2cb84d4fb30a7701a241e067d51d36e174df',
    'personnel-v2-small-002': 'c7550f57350846f3a7833caf23461916ebef12ab26f34c631d92a115299168f8',
    'personnel-v2-small-003': 'd89651c9966108a57e109f8bb0b4879109b7cdaad64825b85ba4093db795293b',
}
COUNTS = {'personnel-v2-small-001': 7, 'personnel-v2-small-002': 7, 'personnel-v2-small-003': 14}
LARGE = 'personnel-v2-large-004'  # a paged package: pages of the unchanged contract (at most 100 members) plus a manifest
LARGE_COUNT, LARGE_PAGE = 1000, 100
RANK_CLEARANCE = {'CAPTAIN': 'TOP_SECRET', 'COMMANDER': 'SECRET', 'LIEUTENANT_COMMANDER': 'SECRET'}
# The people migrated from the v1 release into 003, with the supervisor each reports to (the cast of the federation crew mapping).
MIGRATED = {'PRS-1048': 'PRS-0001', 'PRS-1049': 'PRS-1048', 'PRS-1053': 'PRS-0001', 'PRS-1054': 'PRS-0001', 'PRS-1057': 'PRS-1049',
            'PRS-1058': 'PRS-1048', 'PRS-1100': 'PRS-1048'}


def check_reporting(by_id):
    """Known supervisors and no reporting cycle, over a whole snapshot."""
    for record in by_id.values():
        seen = set()
        current = record
        while current is not None:
            key = current.findtext(Q('personnelId'))
            require(key not in seen, 'Reporting cycle')
            seen.add(key)
            supervisor = current.findtext(Q('crewDetails') + '/' + Q('supervisorPersonnelId'))
            require(supervisor is None or supervisor in by_id, 'Dangling supervisor')
            current = by_id.get(supervisor)


def check_large(xsd, small_003):
    """The paged package: hashes against the manifest and Dataset.java, every page against the XSD, the paging fields, the ordering
    over all pages, readiness, the 14 people of the third snapshot byte for byte, clearance by rank, and the civilian range."""
    folder = COMPONENT / 'datasets' / LARGE
    source = (COMPONENT / 'src/main/java/lab/enterprise/personnel/Dataset.java').read_text()
    manifest_bytes = (folder / 'manifest.json').read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    require('"' + manifest_hash + '", ' + str(len(manifest_bytes)) + ', ' + str(LARGE_COUNT) in source, 'Runtime manifest registration mismatch')
    manifest = json.loads(manifest_bytes)
    require(manifest['datasetVersion'] == LARGE and manifest['count'] == LARGE_COUNT and manifest['pageSize'] == LARGE_PAGE, 'Manifest identity')
    names = ['page-%03d.xml' % i for i in range(LARGE_COUNT // LARGE_PAGE)]
    require(sorted(p.name for p in folder.iterdir()) == sorted(names + ['manifest.json']), 'Package files')
    require([p['filename'] for p in manifest['pages']] == names, 'Page names and order')
    by_id = {}
    last = None
    for index, descriptor in enumerate(manifest['pages']):
        data = (folder / descriptor['filename']).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        require(digest == descriptor['sha256'] and len(data) == descriptor['byteLength'], 'Page hash or length: ' + descriptor['filename'])
        require('"' + digest + '"' in source, 'Runtime page registration mismatch: ' + descriptor['filename'])
        page = read(folder / descriptor['filename'])
        expect_schema(xsd, page, True, descriptor['filename'])
        records = page.findall(Q('personnelMember'))
        require(page.findtext(Q('datasetVersion')) == LARGE and int(page.findtext(Q('totalCount'))) == LARGE_COUNT, 'Page identity')
        require(int(page.findtext(Q('offset'))) == descriptor['offset'] == index * LARGE_PAGE and int(page.findtext(Q('limit'))) == LARGE_PAGE, 'Page offset or limit')
        require(page.findtext(Q('hasMore')) == ('true' if index < len(names) - 1 else 'false'), 'Page hasMore')
        require(len(records) == descriptor['count'] == min(LARGE_PAGE, LARGE_COUNT - index * LARGE_PAGE), 'Page size')
        for record in records:
            key = record.findtext(Q('personnelId'))
            require(last is None or last < key, 'Ordering/uniqueness across pages')
            last = key
            by_id[key] = record
    require(len(by_id) == LARGE_COUNT, 'Large count mismatch')
    check_reporting(by_id)
    for key, record in small_003.items():
        require(E.tostring(record) == E.tostring(by_id[key]), 'The large snapshot changed a record of the third one: ' + key)
    civilians = [key for key, record in by_id.items() if record.find(Q('civilianDetails')) is not None]
    generated = [key for key in civilians if key >= 'PRS-3001']
    require(generated == ['PRS-%04d' % n for n in range(3001, 3200)], 'The generated civilians fill PRS-3001 to PRS-3199')
    require(all(key < 'PRS-3001' for key, record in by_id.items() if key not in generated), 'Nobody else takes the civilian range')
    require(len(civilians) == 219, 'Civilian count')
    for key, record in by_id.items():
        crew = record.find(Q('crewDetails'))
        if crew is None or not ('PRS-1047' <= key <= 'PRS-2785'):
            continue
        wanted = RANK_CLEARANCE.get(crew.findtext(Q('rank')), 'NONE')
        if crew.findtext(Q('department')) == 'SECURITY' and wanted == 'NONE':
            wanted = 'SECRET'
        require(crew.findtext(Q('securityClearance')) == wanted, 'Migrated clearance by rank: ' + key)
    return by_id


def main():
    schema_doc = read(COMPONENT / 'contracts/personnel-v2.xsd')
    xsd = E.XMLSchema(schema_doc)
    snapshots = []
    for version, digest in HASHES.items():
        path = COMPONENT / 'datasets' / (version + '.xml')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Immutable raw hash changed: ' + version)
        source = (COMPONENT / 'src/main/java/lab/enterprise/personnel/Dataset.java').read_text()
        require('"' + version + '", new Snapshot("' + digest + '")' in source, 'Runtime hash registration mismatch')
        snapshot = read(path)
        expect_schema(xsd, snapshot, True, version)
        require(snapshot.findtext(Q('datasetVersion')) == version, 'Version mismatch')
        records = snapshot.findall(Q('personnelMember'))
        require(len(records) == int(snapshot.findtext(Q('totalCount'))) == COUNTS[version], 'Count mismatch')
        ids = [r.findtext(Q('personnelId')) for r in records]
        require(ids == sorted(set(ids)), 'Ordering/uniqueness mismatch')
        by_id = dict(zip(ids, records))
        check_reporting(by_id)
        snapshots.append(by_id)
    earlier, later, migrated = snapshots
    require(earlier['PRS-0714'].find(Q('civilianDetails')) is not None, 'Earlier Wesley must be civilian')
    require(later['PRS-0714'].find(Q('crewDetails')) is not None, 'Later Wesley must be crew')
    require(earlier['PRS-0714'].findtext(Q('displayName')) == later['PRS-0714'].findtext(Q('displayName')) == 'Wesley Crusher', 'Wesley identity mismatch')
    for key in earlier:
        if key != 'PRS-0714':
            require(E.tostring(earlier[key]) == E.tostring(later[key]), 'Unrelated snapshot change: ' + key)
    require(sorted(migrated) == sorted(list(later) + list(MIGRATED)), 'The third snapshot holds the second one and the migrated people')
    for key in later:
        require(E.tostring(later[key]) == E.tostring(migrated[key]), 'The migration changed an existing record: ' + key)
    for key, supervisor in MIGRATED.items():
        require(migrated[key].findtext(Q('crewDetails') + '/' + Q('supervisorPersonnelId')) == supervisor, 'Migrated supervisor: ' + key)
        require(migrated[key].findtext(Q('crewDetails') + '/' + Q('securityClearance')) in ('NONE', 'SECRET'), 'Migrated clearance: ' + key)
    check_large(xsd, migrated)
    for id_value, valid in [('PRS-0001', True), ('PRS-9999', True), ('PRS-0000', False), ('PRS-00001', False), ('PRS-0001 ', False), ('P-0714', False)]:
        request = E.Element(Q('GetPersonnelMemberRequest'))
        E.SubElement(request, Q('personnelId')).text = id_value
        expect_schema(xsd, request, valid, id_value)
    for branches in [0, 2]:
        sample = read(COMPONENT / 'datasets/personnel-v2-small-001.xml')
        wesley = sample.findall(Q('personnelMember'))[-1]
        civilian = wesley.find(Q('civilianDetails'))
        if branches == 0:
            wesley.remove(civilian)
        else:
            wesley.append(deepcopy(later['PRS-0714'].find(Q('crewDetails'))))
        expect_schema(xsd, sample, False, 'required exclusive choice')
    wsdl = read(COMPONENT / 'contracts/personnel-v2.wsdl')
    require(wsdl.get('targetNamespace') == NS, 'WSDL namespace')
    require(wsdl.xpath('w:portType/w:operation/@name', namespaces=X) == ['GetPersonnelMember', 'ListPersonnelMembers'], 'Common operation set')
    require(wsdl.xpath('w:types/x:schema/x:include/@schemaLocation', namespaces=X) == ['personnel-v2.xsd'], 'Schema include')
    require(wsdl.xpath('w:binding/w:operation/s:operation/@soapAction', namespaces=X) == [NS+':GetPersonnelMember', NS+':ListPersonnelMembers'], 'SOAPActions')
    require(len(wsdl.findall('w:message', X)) == 5 and not wsdl.findall('w:service', X), 'Reusable binding layout')
    deployment = read(COMPONENT / 'src/main/resources/deployment.wsdl')
    require([E.QName(e).localname for e in deployment] == ['import', 'service'], 'Deployment metadata only')
    require(deployment.find('w:import', X).get('location') == 'contracts/personnel-v2.wsdl', 'Deployment import')
    print('PASS: Personnel v2 XSD/WSDL/deployment, three raw snapshot hashes/readiness, the paged package ' + LARGE + ' (ten pages, 1000 people), stable Wesley choice transition, the seven migrated people and ID/choice negative probes.')
    print('LIMITS: offline validation does not establish Java/HTTP/container or manual acceptance; run Maven verification separately.')


if __name__ == '__main__':
    sys.exit(cli(main))
