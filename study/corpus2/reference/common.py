"""The access interface every arm's reference solution is written against, and what it shares.

An arm's access layer (direct_access.py, graph_access.py) implements these operations with that arm's MCP tools and nothing else: it gets
one function, `call(tool, arguments) -> (text, is_error)`, which the runner connects to the arm's MCP server (or a test connects to a
fake). The task solutions (solutions.py) are written once against this interface, so a task's reference solution in an arm is its
solution run over that arm's access layer: every record it uses came through that arm's own tools.

A stopped service is the exception `Unavailable(service)`. A release that the mapping refuses (one that does not exist) is
`ReleaseRefused`. Anything else unexpected (a refusal by the sandbox, a truncated answer, a body that does not parse) is `ToolFailure`,
which makes the task fail in that arm instead of guessing.

The normalized records:
  mission: missionId, title, type, classification, status, priority (int), stardate (text), durationHours (int), issuingAuthority,
           locationType, locationName, co (crew reference or None), crew, participants, assetRefs (lists), est and act (text or None)
  asset:   assetId, kind, category, name, status, parentAssetId (or None)
  person:  personnelId, displayName, positionTitle, dutyStatus, civilian (bool), rank, department, securityClearance, supervisor
"""

SERVICES = ('missions', 'assets', 'personnel')
MISSION_FILTERS = ('type', 'classification', 'status', 'priority', 'issuingAuthority', 'commandingOfficerId', 'assignedCrewId',
                   'assignedAssetId', 'locationType')
ASSET_FILTERS = ('kind', 'category', 'status', 'parentAssetId')
PERSON_FILTERS = ('department', 'dutyStatus')


class Unavailable(Exception):
    """A service did not answer (in category D, the stopped one)."""

    def __init__(self, service, detail=''):
        super().__init__('%s did not answer%s' % (service, (': ' + detail) if detail else ''))
        self.service = service


class ReleaseRefused(Exception):
    """The mapping refused the release (it does not exist)."""


class ToolFailure(Exception):
    """A tool answered in a way the reference cannot use: a refusal, a truncated or malformed answer."""


def check_filters(filters, allowed):
    unknown = set(filters) - set(allowed)
    if unknown:
        raise ValueError('unknown filters %s' % sorted(unknown))


def staff_refs(mission):
    """The commanding officer and the assigned crew, each reference once, commanding officer first."""
    out = []
    for ref in ([mission['co']] if mission['co'] else []) + list(mission['crew']):
        if ref not in out:
            out.append(ref)
    return out


class Access:
    """The operations of an arm. Subclasses implement them with the arm's tools only."""

    arm = None

    def __init__(self, call):
        self.call = call

    # missions
    def list_missions(self, **filters):
        raise NotImplementedError

    def get_mission(self, mission_id):
        raise NotImplementedError

    # assets
    def list_assets(self, **filters):
        raise NotImplementedError

    def get_asset(self, asset_id):
        raise NotImplementedError

    # personnel
    def list_people(self, **filters):
        raise NotImplementedError

    def get_person(self, personnel_id):
        raise NotImplementedError

    # the mapping
    def staff_map(self, missions, release):
        """{missionId: [(crew reference, Personnel identifier or None)]} for the staff of each mission, in staff order."""
        raise NotImplementedError

    def asset_map(self, missions, release):
        """{missionId: [(asset reference, Assets identifier or None)]} for the asset references of each mission, in their order."""
        raise NotImplementedError

    def crew_ref_map(self, refs, release):
        """{crew reference: Personnel identifier or None}."""
        raise NotImplementedError

    def release_sections(self):
        """{release: set of the sections it holds, such as 'assets' and 'crew'}."""
        raise NotImplementedError
