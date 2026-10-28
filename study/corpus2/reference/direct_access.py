"""The access layer of Direct Access (internal identifier Alpha): the raw legacy interfaces through the raw MCP server's three tools,
`http_request`, `soap_request` and `read_mapping_release` (study/mcp/raw_server.py), and nothing else.

- Missions: REST/XML, GET /missions with the contract's filters and page/pageSize (1 to 50), GET /missions/{id} (404 when absent).
- Assets: REST/JSON, GET /assets with kind, category, status, parentAssetId and offset/limit (1 to 50), GET /assets/{id}.
- Personnel v2: SOAP 1.1, ListPersonnelMembers (department, dutyStatus, offset, limit up to 100) and GetPersonnelMember.
- The mapping: the release files as raw JSON (`<release>/assets.json`, `<release>/crew.json`).

A tool error from http_request or soap_request that says the service did not answer is a stopped service: Unavailable.
"""
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

from common import (ASSET_FILTERS, MISSION_FILTERS, PERSON_FILTERS, Access, ReleaseRefused, ToolFailure, Unavailable, check_filters,
                    staff_refs)

MISSIONS_URL = 'http://127.0.0.1:8083'
ASSETS_URL = 'http://127.0.0.1:8084'
PERSONNEL_URL = 'http://127.0.0.1:8082/soap/personnel-v2'
PERSONNEL_NS = 'urn:graphql-federation-lab:personnel:v2'
SOAP_ACTION = 'urn:graphql-federation-lab:personnel:v2:'
NOT_ANSWERING = 'did not answer'


def local(tag):
    return tag.rsplit('}', 1)[-1]


def child(node, name):
    for item in node:
        if local(item.tag) == name:
            return item
    return None


def children(node, name):
    return [item for item in node if local(item.tag) == name]


def text_of(node, name):
    found = child(node, name)
    return found.text if found is not None and found.text not in (None, '') else None


def find_all(root, name):
    return [node for node in root.iter() if local(node.tag) == name]


def mission_from_xml(node):
    location = child(node, 'location')
    return {'missionId': text_of(node, 'missionId'), 'title': text_of(node, 'title'), 'type': text_of(node, 'type'),
            'classification': text_of(node, 'classification'), 'status': text_of(node, 'status'),
            'priority': int(text_of(node, 'priority')), 'stardate': text_of(node, 'stardate'),
            'durationHours': int(text_of(node, 'durationHours')), 'issuingAuthority': text_of(node, 'issuingAuthority'),
            'locationType': text_of(location, 'type'), 'locationName': text_of(location, 'name'),
            'co': text_of(node, 'commandingOfficerId'),
            'crew': [n.text for n in children(child(node, 'assignedCrewIds'), 'crewId')] if child(node, 'assignedCrewIds') is not None else [],
            'participants': [n.text for n in children(child(node, 'participantIds'), 'participantId')] if child(node, 'participantIds') is not None else [],
            'assetRefs': [n.text for n in children(child(node, 'assignedAssetIds'), 'assetId')] if child(node, 'assignedAssetIds') is not None else [],
            'est': text_of(node, 'estimatedCostCredits'), 'act': text_of(node, 'actualCostCredits')}


def asset_from_json(item):
    return {'assetId': item['assetId'], 'kind': item['kind'], 'category': item['category'], 'name': item['name'], 'status': item['status'],
            'parentAssetId': item.get('parentAssetId')}


def person_from_xml(node):
    crew = child(node, 'crewDetails')
    return {'personnelId': text_of(node, 'personnelId'), 'displayName': text_of(node, 'displayName'),
            'positionTitle': text_of(node, 'positionTitle'), 'dutyStatus': text_of(node, 'dutyStatus'), 'civilian': crew is None,
            'rank': text_of(crew, 'rank') if crew is not None else None,
            'department': text_of(crew, 'department') if crew is not None else None,
            'securityClearance': text_of(crew, 'securityClearance') if crew is not None else None,
            'supervisor': text_of(crew, 'supervisorPersonnelId') if crew is not None else None}


def envelope(operation, fields):
    body = ''.join('<%s>%s</%s>' % (name, value, name) for name, value in fields)
    return ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
            '<%sRequest xmlns="%s">%s</%sRequest></soapenv:Body></soapenv:Envelope>' % (operation, PERSONNEL_NS, body, operation))


class RawAccess(Access):
    arm = 'alpha'

    def __init__(self, call):
        super().__init__(call)
        self._mapping = {}

    # ---------------------------------------------------------------- the tools
    def _result(self, service, tool, arguments):
        text, is_error = self.call(tool, arguments)
        if is_error:
            if NOT_ANSWERING in text:
                raise Unavailable(service, text)
            raise ToolFailure('%s refused: %s' % (tool, text))
        outer = json.loads(text)
        if outer.get('truncated'):
            raise ToolFailure('%s answer truncated' % tool)
        return outer['status'], outer['body']

    def _get(self, service, url):
        return self._result(service, 'http_request', {'method': 'GET', 'url': url})

    def _soap(self, operation, fields):
        return self._result('personnel', 'soap_request', {'url': PERSONNEL_URL, 'envelope': envelope(operation, fields),
                                                          'soap_action': SOAP_ACTION + operation})

    # ---------------------------------------------------------------- missions
    def list_missions(self, **filters):
        check_filters(filters, MISSION_FILTERS)
        out, page = [], 1
        while True:
            query = urllib.parse.urlencode(list(filters.items()) + [('page', page), ('pageSize', 50)])
            status, body = self._get('missions', '%s/missions?%s' % (MISSIONS_URL, query))
            if status != 200:
                raise ToolFailure('GET /missions answered %s' % status)
            root = ET.fromstring(body)
            out += [mission_from_xml(node) for node in children(root, 'mission')]
            if page >= int(text_of(root, 'totalPages') or 0):
                return out
            page += 1

    def get_mission(self, mission_id):
        status, body = self._get('missions', '%s/missions/%s' % (MISSIONS_URL, urllib.parse.quote(mission_id)))
        if status == 404:
            return None
        if status != 200:
            raise ToolFailure('GET /missions/%s answered %s' % (mission_id, status))
        root = ET.fromstring(body)
        return mission_from_xml(root if local(root.tag) == 'mission' else child(root, 'mission'))

    # ---------------------------------------------------------------- assets
    def list_assets(self, **filters):
        check_filters(filters, ASSET_FILTERS)
        out, offset = [], 0
        while True:
            query = urllib.parse.urlencode(list(filters.items()) + [('offset', offset), ('limit', 50)])
            status, body = self._get('assets', '%s/assets?%s' % (ASSETS_URL, query))
            if status != 200:
                raise ToolFailure('GET /assets answered %s' % status)
            data = json.loads(body)
            out += [asset_from_json(item) for item in data['items']]
            offset += len(data['items'])
            if offset >= data['total'] or not data['items']:
                return out

    def get_asset(self, asset_id):
        status, body = self._get('assets', '%s/assets/%s' % (ASSETS_URL, urllib.parse.quote(asset_id)))
        if status == 404:
            return None
        if status != 200:
            raise ToolFailure('GET /assets/%s answered %s' % (asset_id, status))
        return asset_from_json(json.loads(body))

    # ---------------------------------------------------------------- personnel
    def list_people(self, **filters):
        check_filters(filters, PERSON_FILTERS)
        out, offset = [], 0
        while True:
            fields = [(name, filters[name]) for name in PERSON_FILTERS if name in filters] + [('offset', offset), ('limit', 100)]
            status, body = self._soap('ListPersonnelMembers', fields)
            if status != 200:
                raise ToolFailure('ListPersonnelMembers answered %s' % status)
            root = ET.fromstring(body)
            members = find_all(root, 'personnelMember')
            out += [person_from_xml(node) for node in members]
            offset += len(members)
            more = find_all(root, 'hasMore')
            if not members or not more or more[0].text != 'true':
                return out

    def get_person(self, personnel_id):
        status, body = self._soap('GetPersonnelMember', [('personnelId', personnel_id)])
        root = ET.fromstring(body)
        if status != 200:
            codes = [node.text for node in find_all(root, 'code')]
            if 'PersonnelNotFound' in codes:
                return None
            if 'ServiceUnavailable' in codes:
                raise Unavailable('personnel', 'ServiceUnavailable fault')
            raise ToolFailure('GetPersonnelMember answered %s %s' % (status, codes))
        members = find_all(root, 'personnelMember')
        return person_from_xml(members[0]) if members else None

    # ---------------------------------------------------------------- the mapping release files
    def _release_file(self, release, name):
        """The parsed file, or None when the release has no such file; ReleaseRefused when the release does not exist."""
        key = (release, name)
        if key not in self._mapping:
            text, is_error = self.call('read_mapping_release', {'release': release, 'file': name})
            if is_error:
                if 'no mapping release' in text:
                    raise ReleaseRefused(release)
                if 'has no file' in text:
                    self._mapping[key] = None
                    return None
                raise ToolFailure('read_mapping_release refused: ' + text)
            outer = json.loads(text)
            if outer.get('truncated'):
                raise ToolFailure('mapping file truncated')
            self._mapping[key] = json.loads(outer['content'])
        return self._mapping[key]

    def _entries(self, release, section):
        data = self._release_file(release, section + '.json')
        return None if data is None else data['entries']

    def staff_map(self, missions, release):
        entries = self._entries(release, 'crew') or {}
        return {m['missionId']: [(ref, entries.get(ref)) for ref in staff_refs(m)] for m in missions}

    def asset_map(self, missions, release):
        entries = self._entries(release, 'assets') or {}
        return {m['missionId']: [(ref, entries.get(ref)) for ref in m['assetRefs']] for m in missions}

    def crew_ref_map(self, refs, release):
        entries = self._entries(release, 'crew') or {}
        return {ref: entries.get(ref) for ref in refs}

    def release_sections(self):
        text, is_error = self.call('read_mapping_release', {'release': '0.0'})
        found = re.search(r'Releases present: ([0-9., ]+?)\.\s*$', text) if is_error else None
        if not found:
            raise ToolFailure('the mapping tool did not name its releases')
        out = {}
        for release in [r.strip() for r in found.group(1).split(',') if r.strip()]:
            text, is_error = self.call('read_mapping_release', {'release': release})
            if is_error:
                raise ToolFailure(text)
            files = json.loads(json.loads(text)['content'])['files']
            out[release] = {name[:-5] for name in files if name != 'manifest.json'}
        return out


ARM = 'alpha'
NAME = 'Direct Access'
ACCESS = RawAccess
MCP_URL = 'http://127.0.0.1:8191/mcp'
TOOLS = ('http_request', 'soap_request', 'read_mapping_release')
