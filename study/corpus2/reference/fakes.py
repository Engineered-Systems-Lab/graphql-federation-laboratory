"""Offline fakes of the arms' MCP tools, answered from the released files, for the tests of the reference solutions and the runner.

FakeEnterprise(world, down=()).call(tool, arguments) answers like the MCP servers of study/mcp: the raw tools in the services' own wire
formats (Missions REST/XML, Assets REST/JSON, Personnel v2 SOAP, the mapping release files) and `graphql_query` for the adapters and the
router, which it answers by operation name from the same data (it is not a GraphQL engine: it knows the named operations of
graph_access.py). A service named in `down` answers as a stopped service does: the raw tools report that it did not answer, and a
GraphQL root field it owns is null with an errors entry. The fakes prove the solutions and the runner offline; the simulator-stack runs
prove them against the real servers.
"""
import json
import re
import urllib.parse
from xml.sax.saxutils import escape

MISSIONS_NS = 'urn:starfleet:missions:v1'
PERSONNEL_NS = 'urn:graphql-federation-lab:personnel:v2'
BASES = {'http://127.0.0.1:8083': 'missions', 'http://127.0.0.1:8084': 'assets', 'http://127.0.0.1:8082': 'personnel'}
OWNERS = {'missions': 'missions', 'mission': 'missions', 'assets': 'assets', 'asset': 'assets', 'personnelMembers': 'personnel',
          'personnel': 'personnel'}


def tool_text(status, body, content_type='application/xml'):
    return json.dumps({'status': status, 'contentType': content_type, 'truncated': False, 'body': body}), False


def el(name, value):
    return '<%s>%s</%s>' % (name, escape(str(value)), name) if value is not None else ''


def mission_xml(m):
    parts = [el('missionId', m['missionId']), el('title', m['title']), el('type', m['type']), el('classification', m['classification']),
             el('status', m['status']), el('priority', m['priority']), el('stardate', m['stardate']), el('durationHours', m['durationHours']),
             '<location>%s%s</location>' % (el('type', m['locationType']), el('name', m['locationName'])),
             el('issuingAuthority', m['issuingAuthority']), el('commandingOfficerId', m['co']),
             '<assignedCrewIds>%s</assignedCrewIds>' % ''.join(el('crewId', r) for r in m['crew']),
             '<participantIds>%s</participantIds>' % ''.join(el('participantId', r) for r in m['participants']),
             '<assignedAssetIds>%s</assignedAssetIds>' % ''.join(el('assetId', r) for r in m['assetRefs']),
             el('estimatedCostCredits', m['est']), el('actualCostCredits', m['act'])]
    return '<mission>%s</mission>' % ''.join(parts)


def person_xml(p):
    details = ('<civilianDetails/>' if p['civilian'] else
               '<crewDetails>%s%s%s%s</crewDetails>' % (el('rank', p['rank']), el('department', p['department']),
                                                       el('securityClearance', p['securityClearance']),
                                                       el('supervisorPersonnelId', p['supervisor'])))
    return '<personnelMember>%s%s%s%s%s</personnelMember>' % (el('personnelId', p['personnelId']), el('displayName', p['displayName']),
                                                             el('positionTitle', p['positionTitle']), el('dutyStatus', p['dutyStatus']), details)


def soap(body):
    return ('<?xml version="1.0" encoding="UTF-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
            '<soapenv:Body>%s</soapenv:Body></soapenv:Envelope>' % body)


def mission_graph(m):
    return {'missionId': m['missionId'], 'title': m['title'], 'type': m['type'], 'classification': m['classification'], 'status': m['status'],
            'priority': m['priority'], 'stardate': m['stardate'], 'durationHours': m['durationHours'], 'issuingAuthority': m['issuingAuthority'],
            'location': {'type': m['locationType'], 'name': m['locationName']}, 'commandingOfficerId': m['co'],
            'assignedCrewIds': list(m['crew']), 'participantIds': list(m['participants']), 'assignedAssetIds': list(m['assetRefs']),
            'estimatedCostCredits': m['est'], 'actualCostCredits': m['act']}


def asset_graph(a):
    return {k: a[k] for k in ('assetId', 'kind', 'category', 'name', 'status', 'parentAssetId')}


def person_graph(p):
    details = ({'__typename': 'CivilianDetails'} if p['civilian'] else
               {'__typename': 'CrewDetails', 'rank': p['rank'], 'department': p['department'], 'securityClearance': p['securityClearance'],
                'supervisorPersonnelId': p['supervisor']})
    return {'personnelId': p['personnelId'], 'displayName': p['displayName'], 'positionTitle': p['positionTitle'],
            'dutyStatus': p['dutyStatus'], 'details': details}


class FakeEnterprise:
    def __init__(self, world, down=()):
        self.w = world
        self.down = set(down)
        self.calls = []

    def call(self, tool, arguments):
        self.calls.append((tool, arguments))
        handler = {'http_request': self.http, 'soap_request': self.soap_request, 'read_mapping_release': self.mapping_file,
                   'graphql_query': self.graphql}.get(tool)
        if handler is None:
            return 'Unknown tool ' + tool, True
        return handler(arguments)

    # ---------------------------------------------------------------- raw
    def _service(self, url):
        for base, name in BASES.items():
            if url.startswith(base + '/'):
                return name
        return None

    def http(self, args):
        url = args['url']
        service = self._service(url)
        if service is None:
            return 'Address refused: only these base addresses are reachable', True
        if service in self.down:
            return 'The service did not answer: ConnectionRefusedError: [Errno 111] Connection refused', True
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query))
        path = urllib.parse.unquote(parts.path)
        if service == 'missions':
            if path == '/missions':
                page, size = int(query.pop('page', 1)), int(query.pop('pageSize', 20))
                found = self._missions({k: (int(v) if k == 'priority' else v) for k, v in query.items()})
                pages = (len(found) + size - 1) // size
                rows = found[(page - 1) * size:page * size]
                return tool_text(200, '<?xml version="1.0" encoding="UTF-8"?><missionList xmlns="%s"><page>%d</page><pageSize>%d</pageSize>'
                                      '<totalCount>%d</totalCount><totalPages>%d</totalPages>%s</missionList>'
                                      % (MISSIONS_NS, page, size, len(found), pages, ''.join(mission_xml(m) for m in rows)))
            m = self.w.by_id.get(path.rsplit('/', 1)[-1])
            if m is None:
                return tool_text(404, '<error xmlns="%s"><code>MISSION_NOT_FOUND</code></error>' % MISSIONS_NS)
            return tool_text(200, '<?xml version="1.0" encoding="UTF-8"?>' + mission_xml(m).replace('<mission>', '<mission xmlns="%s">' % MISSIONS_NS, 1))
        if path == '/assets':
            offset, limit = int(query.pop('offset', 0)), int(query.pop('limit', 20))
            found = self._assets(query)
            return tool_text(200, json.dumps({'items': found[offset:offset + limit], 'offset': offset, 'limit': limit, 'total': len(found)}),
                             'application/json')
        a = self.w.assets.get(path.rsplit('/', 1)[-1])
        if a is None:
            return tool_text(404, json.dumps({'code': 'ASSET_NOT_FOUND', 'message': 'not found'}), 'application/json')
        return tool_text(200, json.dumps(a), 'application/json')

    def soap_request(self, args):
        if self._service(args['url']) != 'personnel':
            return 'Address refused', True
        if 'personnel' in self.down:
            return 'The service did not answer: ConnectionRefusedError: [Errno 111] Connection refused', True
        envelope = args['envelope']

        def field(name):
            found = re.search(r'<%s>([^<]*)</%s>' % (name, name), envelope)
            return found.group(1) if found else None
        if 'GetPersonnelMemberRequest' in envelope:
            p = self.w.people.get(field('personnelId'))
            if p is None:
                return tool_text(500, soap('<soapenv:Fault><faultcode>soapenv:Client</faultcode><detail><PersonnelServiceFault xmlns="%s">'
                                           '<code>PersonnelNotFound</code><message>no such member</message></PersonnelServiceFault>'
                                           '</detail></soapenv:Fault>' % PERSONNEL_NS), 'text/xml')
            return tool_text(200, soap('<GetPersonnelMemberResponse xmlns="%s"><datasetVersion>personnel-v2-large-004</datasetVersion>%s'
                                       '</GetPersonnelMemberResponse>' % (PERSONNEL_NS, person_xml(p))), 'text/xml')
        offset, limit = int(field('offset') or 0), int(field('limit') or 20)
        found = self._people({k: field(k) for k in ('department', 'dutyStatus') if field(k)})
        rows = found[offset:offset + limit]
        return tool_text(200, soap('<ListPersonnelMembersResponse xmlns="%s"><datasetVersion>personnel-v2-large-004</datasetVersion>%s'
                                   '<totalCount>%d</totalCount><offset>%d</offset><limit>%d</limit><hasMore>%s</hasMore>'
                                   '</ListPersonnelMembersResponse>' % (PERSONNEL_NS, ''.join(person_xml(p) for p in rows), len(found),
                                                                       offset, limit, 'true' if offset + limit < len(found) else 'false')),
                         'text/xml')

    def mapping_file(self, args):
        release, name = args.get('release'), args.get('file')
        if release not in self.w.releases:
            return "There is no mapping release %r. Releases present: %s." % (release, ', '.join(self.w.releases)), True
        files = ['assets.json'] + (['crew.json'] if self.w.crew_map[release] is not None else []) + ['manifest.json']
        if name is None:
            return json.dumps({'truncated': False, 'content': json.dumps({'release': release, 'files': files})}), False
        if name not in files:
            return 'Release %s has no file %r. Files present: %s.' % (release, name, ', '.join(files)), True
        if name == 'manifest.json':
            return json.dumps({'truncated': False, 'content': json.dumps({'release': release})}), False
        entries = self.w.asset_map[release] if name == 'assets.json' else self.w.crew_map[release]
        return json.dumps({'truncated': False, 'content': json.dumps({'section': name[:-5], 'entries': entries})}), False

    # ---------------------------------------------------------------- shared filtering
    def _missions(self, filters):
        out = []
        for m in self.w.missions:
            ok = True
            for k, v in filters.items():
                if k == 'commandingOfficerId':
                    ok = ok and m['co'] == v
                elif k == 'assignedCrewId':
                    ok = ok and v in m['crew']
                elif k == 'assignedAssetId':
                    ok = ok and v in m['assetRefs']
                else:
                    ok = ok and m[k] == v
            if ok:
                out.append(m)
        return out

    def _assets(self, filters):
        return [a for a in sorted(self.w.assets.values(), key=lambda a: a['assetId']) if all(a.get(k) == v for k, v in filters.items())]

    def _people(self, filters):
        return [p for p in sorted(self.w.people.values(), key=lambda p: p['personnelId']) if all(p[k] == v for k, v in filters.items())]

    # ---------------------------------------------------------------- GraphQL by operation name
    def graphql(self, args):
        op, v = args.get('operation_name'), args.get('variables') or {}
        service = args.get('service')
        data, errors = self._operation(op, v, service)
        body = {'data': data}
        if errors:
            body['errors'] = errors
        return tool_text(200, json.dumps(body), 'application/json')

    def _down(self, root):
        return OWNERS.get(root) in self.down

    def _crew_ref(self, ref, release):
        if release not in self.w.releases:
            return {'localRef': ref, 'personnelId': None, 'mappingOutcome': 'RELEASE_REFUSED'}
        pid = self.w.person_id(ref, release)
        return {'localRef': ref, 'personnelId': pid, 'mappingOutcome': 'MAPPED' if pid else 'NO_ENTRY'}

    def _asset_ref(self, ref, release):
        if release not in self.w.releases:
            return {'localRef': ref, 'assetId': None, 'mappingOutcome': 'RELEASE_REFUSED'}
        asset_id = self.w.asset_map[release].get(ref)
        return {'localRef': ref, 'assetId': asset_id, 'mappingOutcome': 'MAPPED' if asset_id else 'NO_ENTRY'}

    def _operation(self, op, v, service):
        unavailable = [{'message': 'the service did not answer', 'extensions': {'code': 'SERVICE_UNAVAILABLE'}}]
        page = lambda rows: rows[v.get('offset', 0):v.get('offset', 0) + v.get('limit', 20)]  # noqa: E731
        filters = {k: x for k, x in v.items() if k not in ('offset', 'limit', 'r', 'ref') and not re.fullmatch(r'id[0-9]+', k)}
        if op == 'Missions':
            return ({'missions': None}, unavailable) if self._down('missions') else ({'missions': [mission_graph(m) for m in page(self._missions(filters))]}, None)
        if op == 'Mission':
            if self._down('mission'):
                return {'mission': None}, unavailable
            m = self.w.by_id.get(v['id'])
            return {'mission': mission_graph(m) if m else None}, None
        if op == 'Assets':
            return ({'assets': None}, unavailable) if self._down('assets') else ({'assets': [asset_graph(a) for a in page(self._assets(filters))]}, None)
        if op == 'Asset':
            if self._down('asset'):
                return {'asset': None}, unavailable
            a = self.w.assets.get(v['id'])
            return {'asset': asset_graph(a) if a else None}, None
        if op == 'PersonnelMembers':
            if self._down('personnelMembers'):
                return {'personnelMembers': None}, unavailable
            found = self._people(filters)
            rows = page(found)
            return {'personnelMembers': {'totalCount': len(found), 'hasMore': v.get('offset', 0) + len(rows) < len(found),
                                         'items': [person_graph(p) for p in rows]}}, None
        if op == 'Personnel':
            if self._down('personnel'):
                return {'personnel': None}, unavailable
            p = self.w.people.get(v['id'])
            return {'personnel': person_graph(p) if p else None}, None
        if op == 'MappingReleases':
            return {'mappingReleases': [{'release': r, 'sections': ['assets'] + (['crew'] if self.w.crew_map[r] is not None else [])}
                                        for r in self.w.releases]}, None
        if op == 'PersonnelReferences':
            assert service in (None, 'mapping')
            refs = [self._crew_ref(ref, v['release']) for ref in v['refs']]
            return {'personnelReferences': refs}, ([{'message': 'MAPPING_RELEASE_NOT_FOUND'}] if v['release'] not in self.w.releases else None)
        if op == 'AssetReferences':
            refs = [self._asset_ref(ref, v['release']) for ref in v['refs']]
            return {'assetReferences': refs}, ([{'message': 'MAPPING_RELEASE_NOT_FOUND'}] if v['release'] not in self.w.releases else None)
        if op in ('Staff', 'MissionAssets'):
            ids = {k: x for k, x in v.items() if re.fullmatch(r'id[0-9]+', k)}
            if self._down('mission'):
                return {'m' + k[2:]: None for k in ids}, unavailable
            data = {}
            for k, mid in ids.items():
                m = self.w.by_id[mid]
                node = {'missionId': mid}
                if op == 'Staff':
                    node['commandingOfficer'] = self._crew_ref(m['co'], v['r']) if m['co'] else None
                    node['crew'] = [self._crew_ref(r, v['r']) for r in m['crew']]
                else:
                    node['assets'] = [self._asset_ref(r, v['r']) for r in m['assetRefs']]
                data['m' + k[2:]] = node
            return data, None
        if op in ('RefViaCommandingOfficerId', 'RefViaAssignedCrewId'):
            if self._down('missions'):
                return {'missions': None}, unavailable
            name = 'commandingOfficerId' if op.endswith('CommandingOfficerId') else 'assignedCrewId'
            found = self._missions({name: v['ref']})[:1]
            nodes = []
            for m in found:
                node = {'missionId': m['missionId']}
                if name == 'commandingOfficerId':
                    node['commandingOfficer'] = self._crew_ref(m['co'], v['r'])
                else:
                    node['crew'] = [self._crew_ref(r, v['r']) for r in m['crew']]
                nodes.append(node)
            return {'missions': nodes}, None
        raise AssertionError('the fake does not know the operation %r' % op)
