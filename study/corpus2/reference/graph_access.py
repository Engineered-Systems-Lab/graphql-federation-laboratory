"""The access layers of the three GraphQL arms, through the one tool `graphql_query` and nothing else.

- GraphQL Adapters (Gamma, study/mcp/adapters_server.py): the four adapters as separate APIs, named by the tool's `service` argument.
  The mapping adapter's plain lookups (`personnelReferences`, `assetReferences`, at most 100 references a call) map references; no
  `_entities`, no router.
- Apollo Federation (Delta) and Cosmo Federation (Epsilon) (study/mcp/graph_server.py): one router and its supergraph. The plain lookups
  are not in the supergraph's API, so a reference is mapped only through a mission: `Mission.commandingOfficer(release)`,
  `Mission.crew(release)` and `Mission.assets(release)`. A crew reference with no mission at hand is mapped through a mission that
  names it (found with the `commandingOfficerId` or `assignedCrewId` filter).

Every query is a named operation with variables, so the offline fakes answer by operation name. Lists page with offset and limit (at
most 100). A root field that comes back null with an errors entry is a service that did not answer: Unavailable for the service that
owns the field. A mapping outcome RELEASE_REFUSED is ReleaseRefused; NO_ENTRY is no identifier.
"""
import json

from common import (ASSET_FILTERS, MISSION_FILTERS, PERSON_FILTERS, Access, ReleaseRefused, ToolFailure, Unavailable, check_filters,
                    staff_refs)

PAGE = 100
BATCH = 20
MISSION_FIELDS = ('missionId title type classification status priority stardate durationHours issuingAuthority location { type name } '
                  'commandingOfficerId assignedCrewIds participantIds assignedAssetIds estimatedCostCredits actualCostCredits')
ASSET_FIELDS = 'assetId kind category name status parentAssetId'
PERSON_FIELDS = ('personnelId displayName positionTitle dutyStatus details { __typename ... on CrewDetails { rank department '
                 'securityClearance supervisorPersonnelId } }')
REF_FIELDS = 'localRef personnelId mappingOutcome'
OWNER = {'missions': 'missions', 'mission': 'missions', 'assets': 'assets', 'asset': 'assets', 'personnelMembers': 'personnel',
         'personnel': 'personnel', 'personnelReferences': 'mapping', 'assetReferences': 'mapping', 'mappingReleases': 'mapping'}
ARG_TYPES = {'type': 'MissionType', 'classification': 'Classification', 'status': 'MissionStatus', 'priority': 'Int',
             'issuingAuthority': 'IssuingAuthority', 'commandingOfficerId': 'String', 'assignedCrewId': 'String', 'assignedAssetId': 'String',
             'locationType': 'LocationType', 'kind': 'AssetKind', 'category': 'AssetCategory', 'parentAssetId': 'ID',
             'department': 'Department', 'dutyStatus': 'DutyStatus'}
ASSET_ARG_TYPES = {'status': 'AssetStatus'}


def mission_from_graph(node):
    return {'missionId': node['missionId'], 'title': node['title'], 'type': node['type'], 'classification': node['classification'],
            'status': node['status'], 'priority': node['priority'], 'stardate': node['stardate'], 'durationHours': node['durationHours'],
            'issuingAuthority': node['issuingAuthority'], 'locationType': node['location']['type'], 'locationName': node['location']['name'],
            'co': node.get('commandingOfficerId'), 'crew': list(node['assignedCrewIds']), 'participants': list(node['participantIds']),
            'assetRefs': list(node['assignedAssetIds']), 'est': node.get('estimatedCostCredits'), 'act': node.get('actualCostCredits')}


def asset_from_graph(node):
    return {'assetId': node['assetId'], 'kind': node['kind'], 'category': node['category'], 'name': node['name'], 'status': node['status'],
            'parentAssetId': node.get('parentAssetId')}


def person_from_graph(node):
    details = node.get('details') or {}
    crew = details.get('__typename') == 'CrewDetails'
    return {'personnelId': node['personnelId'], 'displayName': node['displayName'], 'positionTitle': node['positionTitle'],
            'dutyStatus': node['dutyStatus'], 'civilian': not crew, 'rank': details.get('rank') if crew else None,
            'department': details.get('department') if crew else None,
            'securityClearance': details.get('securityClearance') if crew else None,
            'supervisor': details.get('supervisorPersonnelId') if crew else None}


def ref_id(ref, field):
    """The identifier of a mapping reference, raising on a refused release."""
    if ref is None:
        return None
    if ref.get('mappingOutcome') == 'RELEASE_REFUSED':
        raise ReleaseRefused(ref.get('release'))
    return ref.get(field) if ref.get('mappingOutcome') == 'MAPPED' else None


class GraphAccess(Access):
    """What the adapters arm and the federation arms share: the same type names, fields and paging."""

    def endpoint(self, root):
        """The tool arguments that select the endpoint of a root field (the adapter, on the adapters server)."""
        raise NotImplementedError

    def query(self, root, operation, text, variables=None):
        arguments = dict(self.endpoint(root), query=text, operation_name=operation)
        if variables:
            arguments['variables'] = variables
        result, is_error = self.call('graphql_query', arguments)
        owner = OWNER.get(root, root)
        if is_error:
            raise ToolFailure('graphql_query refused: %s' % result)
        outer = json.loads(result)
        if outer.get('truncated'):
            raise ToolFailure('graphql_query answer truncated')
        try:
            body = json.loads(outer['body'])
        except ValueError:
            raise ToolFailure('graphql_query body is not JSON (status %s)' % outer.get('status'))
        data = body.get('data') or {}
        if body.get('errors') and (not data or any(value is None for value in data.values())):
            if owner in ('missions', 'assets', 'personnel'):
                raise Unavailable(owner, json.dumps(body['errors'])[:300])
            raise ToolFailure('errors: %s' % json.dumps(body['errors'])[:300])
        return data

    def _page(self, root, operation, fields, filters, arg_types):
        names = [name for name in filters]
        decl = ''.join(', $%s: %s' % (name, arg_types.get(name) or ARG_TYPES[name]) for name in names)
        args = ''.join('%s: $%s, ' % (name, name) for name in names)
        text = 'query %s($offset: Int, $limit: Int%s) { %s(%soffset: $offset, limit: $limit) { %s } }' % (operation, decl, root, args, fields)
        out, offset = [], 0
        while True:
            data = self.query(root, operation, text, dict(filters, offset=offset, limit=PAGE))
            batch = data.get(root)
            if batch is None:
                raise Unavailable(OWNER[root])
            items = batch['items'] if isinstance(batch, dict) else batch
            out += items
            offset += len(items)
            more = batch.get('hasMore') if isinstance(batch, dict) else len(items) == PAGE
            if not items or not more:
                return out

    # ---------------------------------------------------------------- missions, assets, personnel
    def list_missions(self, **filters):
        check_filters(filters, MISSION_FILTERS)
        return [mission_from_graph(n) for n in self._page('missions', 'Missions', MISSION_FIELDS, filters, {})]

    def get_mission(self, mission_id):
        data = self.query('mission', 'Mission', 'query Mission($id: ID!) { mission(missionId: $id) { %s } }' % MISSION_FIELDS, {'id': mission_id})
        return mission_from_graph(data['mission']) if data.get('mission') else None

    def list_assets(self, **filters):
        check_filters(filters, ASSET_FILTERS)
        return [asset_from_graph(n) for n in self._page('assets', 'Assets', ASSET_FIELDS, filters, ASSET_ARG_TYPES)]

    def get_asset(self, asset_id):
        data = self.query('asset', 'Asset', 'query Asset($id: ID!) { asset(assetId: $id) { %s } }' % ASSET_FIELDS, {'id': asset_id})
        return asset_from_graph(data['asset']) if data.get('asset') else None

    def list_people(self, **filters):
        check_filters(filters, PERSON_FILTERS)
        fields = 'totalCount hasMore items { %s }' % PERSON_FIELDS
        return [person_from_graph(n) for n in self._page('personnelMembers', 'PersonnelMembers', fields, filters, {})]

    def get_person(self, personnel_id):
        data = self.query('personnel', 'Personnel', 'query Personnel($id: ID!) { personnel(personnelId: $id) { %s } }' % PERSON_FIELDS,
                          {'id': personnel_id})
        return person_from_graph(data['personnel']) if data.get('personnel') else None

    def release_sections(self):
        data = self.query('mappingReleases', 'MappingReleases', 'query MappingReleases { mappingReleases { release sections } }')
        return {item['release']: set(item['sections']) for item in data['mappingReleases']}


class AdaptersAccess(GraphAccess):
    """GraphQL Adapters (Gamma): one adapter per call; references mapped by the mapping adapter's plain lookups."""

    arm = 'gamma'
    SERVICE = {'missions': 'missions', 'assets': 'assets', 'personnel': 'personnel', 'mapping': 'mapping'}

    def endpoint(self, root):
        return {'service': OWNER[root]}

    def _lookup(self, root, operation, field, refs, release):
        out = {}
        unique = list(dict.fromkeys(refs))
        for start in range(0, len(unique), PAGE):
            chunk = unique[start:start + PAGE]
            text = ('query %s($release: String!, $refs: [ID!]!) { %s(release: $release, localRefs: $refs) { localRef %s mappingOutcome } }'
                    % (operation, root, field))
            data = self.query(root, operation, text, {'release': release, 'refs': chunk})
            for ref in data.get(root) or []:
                out[ref['localRef']] = ref_id(dict(ref, release=release), field)
        return out

    def crew_ref_map(self, refs, release):
        found = self._lookup('personnelReferences', 'PersonnelReferences', 'personnelId', refs, release)
        return {ref: found.get(ref) for ref in refs}

    def staff_map(self, missions, release):
        found = self.crew_ref_map([r for m in missions for r in staff_refs(m)], release) if missions else {}
        return {m['missionId']: [(ref, found.get(ref)) for ref in staff_refs(m)] for m in missions}

    def asset_map(self, missions, release):
        refs = [r for m in missions for r in m['assetRefs']]
        found = self._lookup('assetReferences', 'AssetReferences', 'assetId', refs, release) if refs else {}
        return {m['missionId']: [(ref, found.get(ref)) for ref in m['assetRefs']] for m in missions}


class FederationAccess(GraphAccess):
    """Apollo Federation (Delta) and Cosmo Federation (Epsilon): one router; references mapped through missions."""

    arm = 'delta'

    def endpoint(self, root):
        return {}

    def _per_mission(self, operation, selection, missions, release):
        """Run `selection` (a Mission selection using $r) for each mission in batches of aliased mission(...) fields."""
        out = {}
        ids = [m['missionId'] for m in missions]
        for start in range(0, len(ids), BATCH):
            chunk = ids[start:start + BATCH]
            decl = ''.join(', $id%d: ID!' % i for i in range(len(chunk)))
            fields = ' '.join('m%d: mission(missionId: $id%d) { missionId %s }' % (i, i, selection) for i in range(len(chunk)))
            variables = {'r': release, **{'id%d' % i: mid for i, mid in enumerate(chunk)}}
            data = self.query('mission', operation, 'query %s($r: String!%s) { %s }' % (operation, decl, fields), variables)
            for i, mid in enumerate(chunk):
                node = data.get('m%d' % i)
                if node is None:
                    raise Unavailable('missions')
                out[mid] = node
        return out

    def staff_map(self, missions, release):
        nodes = self._per_mission('Staff', 'commandingOfficer(release: $r) { %s } crew(release: $r) { %s }' % (REF_FIELDS, REF_FIELDS),
                                  missions, release)
        out = {}
        for m in missions:
            node = nodes[m['missionId']]
            ids = {}
            for ref in ([node['commandingOfficer']] if node.get('commandingOfficer') else []) + list(node.get('crew') or []):
                ids[ref['localRef']] = ref_id(dict(ref, release=release), 'personnelId')
            out[m['missionId']] = [(ref, ids.get(ref)) for ref in staff_refs(m)]
        return out

    def asset_map(self, missions, release):
        nodes = self._per_mission('MissionAssets', 'assets(release: $r) { localRef assetId mappingOutcome }', missions, release)
        out = {}
        for m in missions:
            ids = {ref['localRef']: ref_id(dict(ref, release=release), 'assetId') for ref in nodes[m['missionId']].get('assets') or []}
            out[m['missionId']] = [(ref, ids.get(ref)) for ref in m['assetRefs']]
        return out

    def crew_ref_map(self, refs, release):
        out = {}
        for ref in refs:
            out[ref] = None
            for filter_name, selection in (('commandingOfficerId', 'commandingOfficer(release: $r) { %s }' % REF_FIELDS),
                                           ('assignedCrewId', 'crew(release: $r) { %s }' % REF_FIELDS)):
                text = ('query RefVia%s($ref: String!, $r: String!) { missions(%s: $ref, offset: 0, limit: 1) { missionId %s } }'
                        % (filter_name[0].upper() + filter_name[1:], filter_name, selection))
                data = self.query('missions', 'RefVia' + filter_name[0].upper() + filter_name[1:], text, {'ref': ref, 'r': release})
                found = data.get('missions') or []
                if not found:
                    continue
                node = found[0]
                candidates = [node['commandingOfficer']] if 'commandingOfficer' in node else list(node.get('crew') or [])
                for item in candidates:
                    if item and item['localRef'] == ref:
                        out[ref] = ref_id(dict(item, release=release), 'personnelId')
                break
        return out
