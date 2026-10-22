"""Missions write acceptance: POST /missions and PUT /missions/{id} on the real Jersey/Tomcat service over plain JDBC
against real Oracle 18c.

Covers the write contract of the Missions design end to end: generated identity, the strong ETag and every If-Match form,
required mutation headers and the exact UTF-8 summary, the service-owned elements, the cost lifecycle matrix and the
cancellation provenance, every error of the error table, the audit trail with its cost population, media and encoding
rules, the transactional reference clock and global mutation order, atomic rollback on a forced failure, concurrency,
sequence overflow and the 405 Allow lists. Reads are covered by test_read_service.py.

The disposable image, schema, login and containers come from service_harness.py. The login holds only the grants a
service needs to write: no DELETE on missions or the audit, no UPDATE on the audit or the clock table.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from xml.sax.saxutils import escape
import re
import threading

import service_harness as harness
from service_harness import q

operator = harness.operator
BASELINE_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
MISSION_SEQUENCE_MAX = 101559956668415
# The cost lifecycle table of the design, as independent rows: (status, estimate, actual, allowed on creation).
COST_TABLE = [
    ('PLANNED', False, False, True), ('PLANNED', True, False, True), ('PLANNED', False, True, False), ('PLANNED', True, True, False),
    ('AUTHORIZED', False, False, False), ('AUTHORIZED', True, False, True), ('AUTHORIZED', False, True, False), ('AUTHORIZED', True, True, False),
    ('ACTIVE', False, False, False), ('ACTIVE', True, False, True), ('ACTIVE', False, True, False), ('ACTIVE', True, True, False),
    ('POSTPONED', False, False, False), ('POSTPONED', True, False, True), ('POSTPONED', False, True, False), ('POSTPONED', True, True, False),
    ('COMPLETED', False, False, False), ('COMPLETED', True, False, False), ('COMPLETED', False, True, False), ('COMPLETED', True, True, True),
    ('FAILED', False, False, False), ('FAILED', True, False, False), ('FAILED', False, True, False), ('FAILED', True, True, True),
    ('CANCELLED', False, False, False), ('CANCELLED', True, False, False), ('CANCELLED', False, True, False), ('CANCELLED', True, True, True)]
STATUSES = ('PLANNED', 'AUTHORIZED', 'ACTIVE', 'POSTPONED', 'COMPLETED', 'FAILED', 'CANCELLED')
TERMINAL = ('COMPLETED', 'FAILED', 'CANCELLED')
ALLOW = {'/missions': 'GET, POST', '/missions/{id}': 'GET, PUT', '/missions/{id}/changes': 'GET'}


class WriteServiceAcceptance(harness.ServiceCase):
    KIND = 'write'

    @classmethod
    def grants(cls):
        def grant(privileges, name):
            return 'GRANT ' + privileges + ' ON ' + cls.schema + '.' + name + ' TO ' + cls.login + ';'
        return [grant('SELECT, INSERT, UPDATE', 'missions'), grant('SELECT, INSERT, DELETE', 'mission_assigned_crew'),
                grant('SELECT, INSERT, DELETE', 'mission_participants'), grant('SELECT, INSERT, DELETE', 'mission_assigned_assets'),
                grant('SELECT, INSERT', 'mission_changes'), grant('SELECT', 'mission_id_seq'), grant('SELECT', 'change_id_seq'),
                grant('EXECUTE', 'missions_clock_tick')]

    @classmethod
    def prepare(cls):
        super().prepare()
        cls.lock = threading.Lock()
        cls.committed = 0
        cls.baseline = cls.query("SELECT TO_CHAR(baseline,'YYYY-MM-DD\"T\"HH24:MI:SS.FF3\"Z\"') FROM mission_clock;")[0].strip()
        cls.seed_missions = len(cls.data['missions'])
        cls.seed_changes = len(cls.data['changes'])
        cls.seed_max_change = max(int(c['changeId']) for c in cls.data['changes'])

    # --- builders and callers ---------------------------------------------------------------------------------

    @staticmethod
    def mission_xml(missionId=None, lastUpdated=None, title='Gate mission', kind='EXPLORATION', classification='UNCLASSIFIED',
                    status='PLANNED', priority=3, stardate='44100.05', durationHours=24, objective='Gate objective text.',
                    location=None, issuingAuthority='STARFLEET_COMMAND', commander=None, crew=(), participants=(), assets=(),
                    estimated=None, actual=None, outcome=None):
        """A mission document in schema element order; a missing optional element is omitted, an empty container kept."""
        location = location or {'type': 'PLANET', 'name': 'Gate location'}

        def element(name, value):
            return '' if value is None else '<' + name + '>' + escape(str(value)) + '</' + name + '>'

        def container(name, member, values):
            return '<' + name + '/>' if not values else '<' + name + '>' + ''.join(element(member, v) for v in values) + '</' + name + '>'
        text = ('<?xml version="1.0" encoding="UTF-8"?><mission xmlns="urn:starfleet:missions:v1">'
                + element('missionId', missionId) + element('title', title) + element('type', kind)
                + element('classification', classification) + element('status', status) + element('priority', priority)
                + element('stardate', stardate) + element('durationHours', durationHours) + element('objective', objective)
                + '<location>' + element('type', location['type']) + element('name', location['name'])
                + element('coordinates', location.get('coordinates')) + element('travelVector', location.get('travelVector')) + '</location>'
                + element('issuingAuthority', issuingAuthority) + element('commandingOfficerId', commander)
                + container('assignedCrewIds', 'crewId', crew) + container('participantIds', 'participantId', participants)
                + container('assignedAssetIds', 'assetId', assets) + element('estimatedCostCredits', estimated)
                + element('actualCostCredits', actual) + element('outcome', outcome) + element('lastUpdated', lastUpdated)
                + '</mission>')
        return text.encode('utf-8')

    @staticmethod
    def fields(d):
        """The builder arguments that reproduce a mission as the service returned it (lastUpdated left out)."""
        return dict(missionId=d['missionId'], title=d['title'], kind=d['type'], classification=d['classification'], status=d['status'],
                    priority=d['priority'], stardate=d['stardate'], durationHours=d['durationHours'], objective=d['objective'],
                    location=d['location'], issuingAuthority=d['issuingAuthority'], commander=d.get('commandingOfficerId'),
                    crew=d['assignedCrewIds'], participants=d['participantIds'], assets=d['assignedAssetIds'],
                    estimated=d.get('estimatedCostCredits'), actual=d.get('actualCostCredits'), outcome=d.get('outcome'))

    @staticmethod
    def valid_for(status, **extra):
        """Builder arguments that are valid for a status on creation."""
        base = {'status': status}
        if status != 'PLANNED' and status != 'CANCELLED':
            base['commander'] = 'C-71'
        if status != 'PLANNED':
            base['estimated'] = '1000.00'
        if status in TERMINAL:
            base['actual'] = '900.00'
        base.update(extra)
        return base

    def mutate(self, method, path, body, tag=None, ctype='application/xml', summary='Gate mutation', user='C-71', ordered='C-1',
               omit=(), extra=(), base=None):
        headers = [] if ctype is None else [('Content-Type', ctype)]
        if 'user' not in omit:
            headers.append(('X-Starfleet-User', user))
        if 'ordered' not in omit:
            headers.append(('X-Starfleet-Ordered-By', ordered))
        if 'summary' not in omit:
            headers.append(('X-Starfleet-Audit-Summary', summary if isinstance(summary, bytes) else summary.encode('utf-8')))
        if tag is not None:
            headers.append(('If-Match', tag))
        headers.extend(extra)
        response = self.get(base or self.base, path, method, headers, body)
        if response.status in (200, 201) and base is None:
            with self.lock:
                type(self).committed += 1
        return response

    def post(self, body, **kw):
        return self.mutate('POST', '/missions', body, **kw)

    def put(self, mission_id, body, tag, **kw):
        return self.mutate('PUT', '/missions/' + mission_id, body, tag=tag, **kw)

    def created(self, **kw):
        """Creates a mission and returns (mission dict, etag header value)."""
        response = self.post(self.mission_xml(**kw))
        self.assertEqual(response.status, 201, response.body[:400])
        return self.mission_dict(response.xml()), response.header('ETag')[0]

    def fetch(self, mission_id):
        response = self.call('/missions/' + mission_id)
        document = self.ok_xml(response, 'mission')
        return self.mission_dict(document), response.header('ETag')[0], response.body

    def changes(self, mission_id):
        document = self.ok_xml(self.call('/missions/' + mission_id + '/changes?pageSize=50'), 'changeList')
        return [self.change_dict(c) for c in document.findall(q('change'))]

    def snapshot(self):
        """(missions, changes, clock counter) as the database holds them right now."""
        line = self.query("SELECT (SELECT COUNT(*) FROM missions)||'|'||(SELECT COUNT(*) FROM mission_changes)||'|'||"
                          "(SELECT counter FROM mission_clock) FROM dual;")[0]
        return tuple(int(part) for part in line.strip().split('|'))

    def stamp(self, counter):
        instant = datetime.strptime(self.baseline, BASELINE_FORMAT) + timedelta(seconds=counter)
        return instant.strftime('%Y-%m-%dT%H:%M:%S.') + '%03d' % (instant.microsecond // 1000) + 'Z'

    def assert_unchanged(self, before):
        self.assertEqual(self.snapshot(), before, 'a refused or failed request must leave rows and the clock untouched')

    def reseed(self, sequence, start):
        operator.sql('DROP SEQUENCE ' + sequence + ';\nCREATE SEQUENCE ' + sequence + ' START WITH ' + str(start)
                     + ' MINVALUE 1 MAXVALUE ' + ('101559956668415' if sequence == 'mission_id_seq' else '9999999999999999999999999999')
                     + ' INCREMENT BY 1 NOCACHE NOCYCLE;', self.schema)
        operator.sql('GRANT SELECT ON ' + self.schema + '.' + sequence + ' TO ' + self.login + ';')

    # --- creation ------------------------------------------------------------------------------------------

    def test_01_post_creates_the_mission_with_generated_identity_and_strong_etag(self):
        self.assertEqual(self.snapshot(), (self.seed_missions, self.seed_changes, 0))
        body = self.mission_xml(title='Created by the gate', status='AUTHORIZED', commander='C-71', estimated='140000.00',
                                crew=['C-3', 'C-10', 'C-2'], participants=['P-9', 'O-5'], assets=['SHU-2', 'SH-17'],
                                location={'type': 'STARBASE', 'name': 'Starbase 74', 'coordinates': '12.5 / 8.1', 'travelVector': 'heading 090'})
        response = self.post(body, summary='Create the gate mission', user='C-71', ordered='C-1')
        self.assertEqual(response.status, 201, response.body[:400])
        self.assert_xml(response, 'mission')
        mission = self.mission_dict(response.xml())
        self.assertRegex(mission['missionId'], r'^ST-[A-Z0-9]{9}$')
        self.assertEqual(response.header('Location'), ['/missions/' + mission['missionId']])
        etag = response.header('ETag')
        self.assertEqual(len(etag), 1)
        self.assertRegex(etag[0], r'^"[1-9][0-9]*"$')
        self.assertEqual({k: v for k, v in mission.items() if k not in ('missionId', 'lastUpdated')},
                         {'title': 'Created by the gate', 'type': 'EXPLORATION', 'classification': 'UNCLASSIFIED', 'status': 'AUTHORIZED',
                          'priority': 3, 'stardate': '44100.05', 'durationHours': 24, 'objective': 'Gate objective text.',
                          'issuingAuthority': 'STARFLEET_COMMAND', 'commandingOfficerId': 'C-71', 'estimatedCostCredits': '140000.00',
                          'location': {'type': 'STARBASE', 'name': 'Starbase 74', 'coordinates': '12.5 / 8.1', 'travelVector': 'heading 090'},
                          # Serialized in canonical lexical order, whatever the caller's order: C-10 precedes C-2.
                          'assignedCrewIds': ['C-10', 'C-2', 'C-3'], 'participantIds': ['O-5', 'P-9'], 'assignedAssetIds': ['SH-17', 'SHU-2']})
        # The first runtime mutation is the clock baseline plus one second, with millisecond precision and a Z suffix.
        self.assertEqual(mission['lastUpdated'], self.stamp(1))
        self.assertRegex(mission['lastUpdated'], r'\.\d{3}Z$')
        self.assertEqual(self.snapshot(), (self.seed_missions + 1, self.seed_changes + 1, 1))
        # Read your write: the same bytes and the same strong tag.
        fetched, fetched_tag, fetched_body = self.fetch(mission['missionId'])
        self.assertEqual(fetched_body, response.body)
        self.assertEqual(fetched_tag, etag[0])
        log = self.changes(mission['missionId'])
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0], {'changeId': etag[0].strip('"'), 'missionId': mission['missionId'], 'operation': 'CREATED',
                                  'changedAt': mission['lastUpdated'], 'changedBy': 'C-71', 'orderedBy': 'C-1', 'newStatus': 'AUTHORIZED',
                                  'estimatedCostCredits': '140000.00', 'summary': 'Create the gate mission'})
        self.assertIn(mission['missionId'], [m['missionId'] for m in self.listing('?assignedCrewId=C-10&pageSize=50')[1]])

    def test_02_every_status_can_be_created_and_audits_its_costs(self):
        for status in STATUSES:
            kwargs = self.valid_for(status, title='Create ' + status)
            if status in TERMINAL:
                kwargs['outcome'] = 'Recorded for ' + status
            mission, etag = self.created(**kwargs)
            self.assertEqual(mission['status'], status)
            self.assertEqual(mission.get('estimatedCostCredits'), kwargs.get('estimated'))
            self.assertEqual(mission.get('actualCostCredits'), kwargs.get('actual'))
            self.assertEqual(mission.get('outcome'), kwargs.get('outcome'))
            log = self.changes(mission['missionId'])
            self.assertEqual(len(log), 1)
            entry = log[0]
            self.assertEqual(entry['operation'], 'CREATED')
            self.assertNotIn('previousStatus', entry)
            self.assertEqual(entry['newStatus'], status)
            # absent -> value records the value and never a change; absent -> absent records nothing.
            self.assertEqual(entry.get('estimatedCostCredits'), kwargs.get('estimated'))
            self.assertEqual(entry.get('actualCostCredits'), kwargs.get('actual'))
            self.assertNotIn('estimatedCostCreditsChange', entry)
            self.assertNotIn('actualCostCreditsChange', entry)
        zero = self.created(**self.valid_for('COMPLETED', estimated='0.00', actual='0.00', title='Zero is not absent'))[0]
        self.assertEqual((zero['estimatedCostCredits'], zero['actualCostCredits']), ('0.00', '0.00'))
        top = self.created(**self.valid_for('COMPLETED', estimated='9999999999999.99', actual='9999999999999.99', title='Largest amount'))[0]
        self.assertEqual(top['estimatedCostCredits'], '9999999999999.99')

    def test_03_cost_lifecycle_matrix_over_http(self):
        before = self.snapshot()
        accepted = 0
        for status, estimate, actual, allowed in COST_TABLE:
            kwargs = {'status': status, 'commander': 'C-71', 'estimated': '1000.00' if estimate else None,
                      'actual': '900.00' if actual else None, 'title': 'Matrix ' + status}
            response = self.post(self.mission_xml(**kwargs))
            label = status + ' estimate=' + str(estimate) + ' actual=' + str(actual)
            if allowed:
                self.assertEqual(response.status, 201, label + ' ' + str(response.body[:300]))
                accepted += 1
            else:
                self.assert_error(response, 422, 'DOMAIN_VALIDATION_FAILED')
        # Only the allowed rows were stored; every refusal left rows and the clock untouched.
        self.assert_unchanged((before[0] + accepted, before[1] + accepted, before[2] + accepted))
        # POST directly as CANCELLED has no PLANNED origin: the estimate is required even though actual is present.
        self.assert_error(self.post(self.mission_xml(status='CANCELLED', actual='0.00')), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assertEqual(self.post(self.mission_xml(status='CANCELLED', estimated='5.00', actual='0.00')).status, 201)

    def test_04_domain_failures_are_422_and_leave_nothing_behind(self):
        refused = [
            ('commander missing', 'AUTHORIZED', dict(estimated='1.00')), ('commander missing', 'ACTIVE', dict(estimated='1.00')),
            ('commander missing', 'POSTPONED', dict(estimated='1.00')),
            ('commander missing', 'COMPLETED', dict(estimated='1.00', actual='1.00')), ('commander missing', 'FAILED', dict(estimated='1.00', actual='1.00')),
            ('outcome while PLANNED', 'PLANNED', dict(outcome='too early')),
            ('outcome while AUTHORIZED', 'AUTHORIZED', dict(commander='C-1', estimated='1.00', outcome='too early')),
            ('outcome while ACTIVE', 'ACTIVE', dict(commander='C-1', estimated='1.00', outcome='too early')),
            ('outcome while POSTPONED', 'POSTPONED', dict(commander='C-1', estimated='1.00', outcome='too early')),
            ('duplicate crew', 'PLANNED', dict(crew=['C-1', 'C-2', 'C-1'])),
            ('duplicate participants', 'PLANNED', dict(participants=['P-1', 'O-1', 'P-1'])),
            ('duplicate assets', 'PLANNED', dict(assets=['SH-17', 'SH-17'])),
            ('blank title', 'PLANNED', dict(title=' ')), ('blank title ideographic', 'PLANNED', dict(title='　　')),
            ('blank title line separator', 'PLANNED', dict(title=' ')), ('blank title tab', 'PLANNED', dict(title='\t')),
            ('blank objective', 'PLANNED', dict(objective='   ')),
            ('blank location name', 'PLANNED', dict(location={'type': 'PLANET', 'name': '   '})),
            ('blank coordinates', 'PLANNED', dict(location={'type': 'PLANET', 'name': 'x', 'coordinates': ' '})),
            ('blank travelVector', 'PLANNED', dict(location={'type': 'PLANET', 'name': 'x', 'travelVector': ' '})),
            ('blank outcome', 'COMPLETED', dict(commander='C-1', estimated='1.00', actual='1.00', outcome='  ')),
            ('missionId on POST', 'PLANNED', dict(missionId='ST-000000001')), ('lastUpdated on POST', 'PLANNED', dict(lastUpdated='2366-10-14T19:42:31.472Z')),
            ('both service-owned', 'PLANNED', dict(missionId='ST-000000001', lastUpdated='2366-10-14T19:42:31.472Z'))]
        before = self.snapshot()
        for label, status, kwargs in refused:
            response = self.post(self.mission_xml(status=status, **kwargs))
            self.assert_error(response, 422, 'DOMAIN_VALIDATION_FAILED')
        # A client-supplied POST missionId is a forbidden field, never a uniqueness conflict.
        existing = self.data['missions'][0]['missionId']
        self.assert_error(self.post(self.mission_xml(missionId=existing)), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assert_unchanged(before)
        # Accepted: the commander need not be assigned, text keeps its whitespace and look-alikes, empty is allowed everywhere.
        mission, _ = self.created(title='  padded  title​ ', status='ACTIVE', commander='C-9', estimated='1.00', crew=['C-1'],
                                  objective=' ', location={'type': 'OTHER', 'name': '​', 'coordinates': ' x ', 'travelVector': ' '})
        self.assertEqual(mission['title'], '  padded  title​ ')
        self.assertEqual(mission['objective'], ' ')
        self.assertEqual(mission['location'], {'type': 'OTHER', 'name': '​', 'coordinates': ' x ', 'travelVector': ' '})
        self.assertEqual(mission['assignedCrewIds'], ['C-1'])

    def test_05_grammar_and_schema_failures_are_400(self):
        good = self.mission_xml(title='Grammar probe').decode('utf-8')

        def swap(old, new):
            self.assertIn(old, good)
            return good.replace(old, new).encode('utf-8')
        refused = {
            'priority range': swap('<priority>3</priority>', '<priority>6</priority>'),
            'priority spelling': swap('<priority>3</priority>', '<priority>03</priority>'),
            'stardate spelling': swap('<stardate>44100.05</stardate>', '<stardate>44100.5</stardate>'),
            'stardate lattice': swap('<stardate>44100.05</stardate>', '<stardate>44100.07</stardate>'),
            'stardate ceiling': swap('<stardate>44100.05</stardate>', '<stardate>49000.00</stardate>'),
            'stardate floor': swap('<stardate>44100.05</stardate>', '<stardate>42999.95</stardate>'),
            'duration range': swap('<durationHours>24</durationHours>', '<durationHours>8761</durationHours>'),
            'duration zero': swap('<durationHours>24</durationHours>', '<durationHours>0</durationHours>'),
            'enum case': swap('<type>EXPLORATION</type>', '<type>exploration</type>'),
            'unknown enum': swap('<type>EXPLORATION</type>', '<type>ENGINEERING</type>'),
            'unknown element': swap('</mission>', '<surprise/></mission>'),
            'unknown attribute': swap('<title>', '<title lang="en">'),
            'xsi:nil': swap('<priority>3</priority>', '<priority xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"/>'),
            'wrong order': swap('<priority>3</priority><stardate>44100.05</stardate>', '<stardate>44100.05</stardate><priority>3</priority>'),
            'excess scalar': swap('<priority>3</priority>', '<priority>3</priority><priority>3</priority>'),
            'missing required': swap('<priority>3</priority>', ''),
            'missing container': swap('<assignedCrewIds/>', ''),
            'empty title': swap('<title>Grammar probe</title>', '<title/>'),
            'title over 120 code points': swap('Grammar probe', '\U0001F680' * 121),
            'objective over 2000 code points': swap('Gate objective text.', 'x' * 2001),
            'participant class in crew': swap('<assignedCrewIds/>', '<assignedCrewIds><crewId>P-1</crewId></assignedCrewIds>'),
            'crew in participants': swap('<participantIds/>', '<participantIds><participantId>C-1</participantId></participantIds>'),
            'crew padded': swap('<assignedCrewIds/>', '<assignedCrewIds><crewId>C-01</crewId></assignedCrewIds>'),
            'asset lowercase': swap('<assignedAssetIds/>', '<assignedAssetIds><assetId>sh-17</assetId></assignedAssetIds>'),
            'commander class': swap('<issuingAuthority>STARFLEET_COMMAND</issuingAuthority>',
                                    '<issuingAuthority>STARFLEET_COMMAND</issuingAuthority><commandingOfficerId>P-1</commandingOfficerId>'),
            'more than 100 crew': swap('<assignedCrewIds/>', '<assignedCrewIds>' + '<crewId>C-1</crewId>' * 101 + '</assignedCrewIds>'),
            'more than 50 assets': swap('<assignedAssetIds/>', '<assignedAssetIds>' + '<assetId>SH-1</assetId>' * 51 + '</assignedAssetIds>'),
            'cost spelling': swap('<assignedAssetIds/>', '<assignedAssetIds/><estimatedCostCredits>5</estimatedCostCredits>'),
            'cost sign': swap('<assignedAssetIds/>', '<assignedAssetIds/><estimatedCostCredits>-5.00</estimatedCostCredits>'),
            'cost too large': swap('<assignedAssetIds/>', '<assignedAssetIds/><estimatedCostCredits>10000000000000.00</estimatedCostCredits>'),
            'lastUpdated spelling': swap('</mission>', '<lastUpdated>2366-10-14 19:42:31</lastUpdated></mission>'),
            'other namespace': swap('urn:starfleet:missions:v1', 'urn:starfleet:missions:v2'),
            'truncated': good[:-12].encode('utf-8'),
            'not xml': b'{"title": "json"}',
            'empty body': b'',
            'whitespace body': b'  \n ',
            'error root': b'<?xml version="1.0"?><error xmlns="urn:starfleet:missions:v1"><code>INVALID_REQUEST</code><message>m</message></error>',
            'list root': b'<?xml version="1.0"?><missionList xmlns="urn:starfleet:missions:v1"><page>1</page><pageSize>20</pageSize><totalCount>0</totalCount><totalPages>0</totalPages></missionList>',
        }
        before = self.snapshot()
        for label, body in refused.items():
            self.assert_error(self.post(body), 400, 'INVALID_REQUEST')
        self.assert_unchanged(before)
        # Fail-fast: a body with several defects yields exactly one error, never an aggregate.
        document = self.post(swap('<priority>3</priority>', '<priority>9</priority>').replace(b'EXPLORATION', b'NOPE')).xml()
        self.assertEqual(len(document.findall(q('code'))), 1)
        self.assertEqual(len(document.findall(q('message'))), 1)

    def test_06_every_header_form_and_the_exact_summary(self):
        body = self.mission_xml(title='Header probe')
        mission, tag = self.created(title='Header target')
        put_body = self.mission_xml(**dict(self.fields(mission), title='Header target changed'))
        before = self.snapshot()
        for omit in (('user',), ('ordered',), ('summary',), ('user', 'ordered', 'summary')):
            self.assert_error(self.post(body, omit=omit), 400, 'INVALID_REQUEST')
            self.assert_error(self.put(mission['missionId'], put_body, tag, omit=omit), 400, 'INVALID_REQUEST')
        for bad in ('P-71', 'O-1', 'c-71', 'C-0', 'C-071', 'C-', 'C71', 'C-7a', 'CRW-71', 'SH-17', 'C-7 7', '', 'C-1, C-2'):
            self.assert_error(self.post(body, user=bad), 400, 'INVALID_REQUEST')
            self.assert_error(self.post(body, ordered=bad), 400, 'INVALID_REQUEST')
            self.assert_error(self.put(mission['missionId'], put_body, tag, user=bad), 400, 'INVALID_REQUEST')
        # A repeated header line is ambiguous and refused, for each of the three headers.
        for name, value in (('X-Starfleet-User', 'C-1'), ('X-Starfleet-Ordered-By', 'C-1'), ('X-Starfleet-Audit-Summary', b'again')):
            self.assert_error(self.post(body, extra=[(name, value)]), 400, 'INVALID_REQUEST')
        for summary in (b'', b' ', '　'.encode('utf-8'), ' '.encode('utf-8'), '   '.encode('utf-8'),
                        ('x' * 257).encode('utf-8'), '\U0001F680'.encode('utf-8') * 257, b'\xc3\x28', b'\xff', b'\xc0\xaf', b'\xed\xa0\x80',
                        '￾'.encode('utf-8'), 'a￿b'.encode('utf-8')):
            self.assert_error(self.post(body, summary=summary), 400, 'INVALID_REQUEST')
            self.assert_error(self.put(mission['missionId'], put_body, tag, summary=summary), 400, 'INVALID_REQUEST')
        self.assert_unchanged(before)
        # Control characters (U+000B, U+000C, U+001C..U+001F, DEL) cannot be carried in an HTTP header value: the container
        # refuses them itself before the application runs, and its error valve answers the contract's XML error body.
        for control in (b'\x0b', b'\x0c', b'\x1c', b'\x1d', b'\x1e', b'\x1f', b'a\x01b', b'a\x7fb'):
            self.assert_error(self.post(body, summary=control), 400, 'INVALID_REQUEST')
            self.assert_error(self.put(mission['missionId'], put_body, tag, summary=control), 400, 'INVALID_REQUEST')
        self.assert_unchanged(before)
        # Nothing above touched the mission: same bytes, same strong tag.
        self.assertEqual(self.fetch(mission['missionId'])[1], tag)

    def test_07_the_summary_is_persisted_as_exact_utf8_text(self):
        summaries = ['Prüfung der Brücke', '日本語の概要', 'Rocket \U0001F680 launched', 'inner  double  spaces', 'tab\there', ' nbsp edges ',
                     '　ideographic edges　', '​zero-width​', 'a<b>&"c\'', 'combining é', '\U0001F680' * 256, 'x' * 256,
                     'Ω≈ç√∫ ' + 'ä' * 200, 'Ç']
        mission, tag = self.created(title='Summary target')
        for number, summary in enumerate(summaries):
            response = self.post(self.mission_xml(title='Summary ' + str(number)), summary=summary, user='C-5', ordered='C-6')
            self.assertEqual(response.status, 201, summary)
            created = self.mission_dict(response.xml())
            log = self.changes(created['missionId'])
            self.assertEqual(log[0]['summary'], summary)
            self.assertEqual((log[0]['changedBy'], log[0]['orderedBy']), ('C-5', 'C-6'))
            stored = self.query("SELECT RAWTOHEX(UTL_RAW.CAST_TO_RAW(summary)) FROM mission_changes WHERE change_id = " + log[0]['changeId'] + ";")
            self.assertEqual(stored[0].strip(), summary.encode('utf-8').hex().upper(), 'the database holds the exact UTF-8 bytes of ' + repr(summary))
        response = self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), title='Summary target changed')), tag,
                            summary='Ersetzt: Überprüfung \U0001F680', user='C-12', ordered='C-3')
        self.assertEqual(response.status, 200, response.body[:300])
        update = self.changes(mission['missionId'])[-1]
        self.assertEqual((update['operation'], update['summary'], update['changedBy'], update['orderedBy']),
                         ('UPDATED', 'Ersetzt: Überprüfung \U0001F680', 'C-12', 'C-3'))
        # Identical performer and orderer are allowed, and the orderer need not be the commander.
        response = self.post(self.mission_xml(title='Same actor', commander='C-99', status='ACTIVE', estimated='1.00'), user='C-4', ordered='C-4')
        self.assertEqual(response.status, 201)

    # --- replacement -----------------------------------------------------------------------------------------

    def test_08_put_replaces_everything_and_advances_the_etag(self):
        mission, tag = self.created(title='Replace me', status='ACTIVE', commander='C-1', estimated='500.00', crew=['C-1', 'C-2', 'C-3'],
                                    participants=['P-1', 'O-2'], assets=['SH-1', 'SH-2'], outcome=None,
                                    location={'type': 'VESSEL', 'name': 'NCC-1701-D', 'coordinates': '1,2', 'travelVector': 'out'})
        fields = dict(self.fields(mission), title='Replaced', kind='MEDICAL', classification='SECRET', priority=1, stardate='44200.10',
                      durationHours=48, objective='Replaced objective', location={'type': 'SECTOR', 'name': 'Sector 12'},
                      issuingAuthority='STARFLEET_MEDICAL', commander='C-88', crew=['C-9'], participants=[], assets=['SH-3'],
                      estimated='600.00', status='COMPLETED', actual='550.25', outcome='Done')
        before = self.snapshot()
        response = self.put(mission['missionId'], self.mission_xml(**fields), tag, summary='Replace everything', user='C-20', ordered='C-21')
        self.assertEqual(response.status, 200, response.body[:400])
        self.assert_xml(response, 'mission')
        replaced = self.mission_dict(response.xml())
        self.assertEqual({k: v for k, v in replaced.items() if k != 'lastUpdated'},
                         {'missionId': mission['missionId'], 'title': 'Replaced', 'type': 'MEDICAL', 'classification': 'SECRET', 'status': 'COMPLETED',
                          'priority': 1, 'stardate': '44200.10', 'durationHours': 48, 'objective': 'Replaced objective',
                          'location': {'type': 'SECTOR', 'name': 'Sector 12'}, 'issuingAuthority': 'STARFLEET_MEDICAL',
                          'commandingOfficerId': 'C-88', 'assignedCrewIds': ['C-9'], 'participantIds': [], 'assignedAssetIds': ['SH-3'],
                          'estimatedCostCredits': '600.00', 'actualCostCredits': '550.25', 'outcome': 'Done'})
        new_tag = response.header('ETag')[0]
        self.assertRegex(new_tag, r'^"[1-9][0-9]*"$')
        self.assertGreater(int(new_tag.strip('"')), int(tag.strip('"')))
        self.assertGreater(replaced['lastUpdated'], mission['lastUpdated'])
        self.assertEqual(self.snapshot(), (before[0], before[1] + 1, before[2] + 1))
        self.assertEqual(replaced['lastUpdated'], self.stamp(before[2] + 1))
        fetched, fetched_tag, fetched_body = self.fetch(mission['missionId'])
        self.assertEqual((fetched_body, fetched_tag), (response.body, new_tag))
        log = self.changes(mission['missionId'])
        self.assertEqual([entry['operation'] for entry in log], ['CREATED', 'UPDATED'])
        self.assertEqual(log[1], {'changeId': new_tag.strip('"'), 'missionId': mission['missionId'], 'operation': 'UPDATED',
                                  'changedAt': replaced['lastUpdated'], 'changedBy': 'C-20', 'orderedBy': 'C-21', 'previousStatus': 'ACTIVE',
                                  'newStatus': 'COMPLETED', 'estimatedCostCredits': '600.00', 'estimatedCostCreditsChange': '100.00',
                                  'actualCostCredits': '550.25', 'summary': 'Replace everything'})
        self.assertNotIn(mission['missionId'], [m['missionId'] for m in self.listing('?assignedCrewId=C-3&pageSize=50')[1]])
        self.assertIn(mission['missionId'], [m['missionId'] for m in self.listing('?assignedCrewId=C-9&pageSize=50')[1]])
        # The old tag is now stale: the same request is refused with 412 and changes nothing.
        before = self.snapshot()
        self.assert_error(self.put(mission['missionId'], self.mission_xml(**fields), tag), 412, 'ETAG_MISMATCH')
        self.assert_unchanged(before)

    def test_09_an_unchanged_put_still_advances_the_etag_and_audits(self):
        mission, tag = self.created(title='No change', status='AUTHORIZED', commander='C-1', estimated='250.00', crew=['C-2'], participants=['P-3'])
        unchanged = self.mission_xml(**self.fields(mission))
        first = self.put(mission['missionId'], unchanged, tag, summary='Resend the same values')
        self.assertEqual(first.status, 200, first.body[:300])
        second_tag = first.header('ETag')[0]
        self.assertGreater(int(second_tag.strip('"')), int(tag.strip('"')))
        again = self.mission_dict(first.xml())
        self.assertEqual({k: v for k, v in again.items() if k != 'lastUpdated'}, {k: v for k, v in mission.items() if k != 'lastUpdated'})
        self.assertGreater(again['lastUpdated'], mission['lastUpdated'])
        third = self.put(mission['missionId'], unchanged, second_tag, summary='And again')
        self.assertEqual(third.status, 200)
        self.assertGreater(int(third.header('ETag')[0].strip('"')), int(second_tag.strip('"')))
        log = self.changes(mission['missionId'])
        self.assertEqual([entry['operation'] for entry in log], ['CREATED', 'UPDATED', 'UPDATED'])
        for entry in log[1:]:
            self.assertEqual((entry['previousStatus'], entry['newStatus']), ('AUTHORIZED', 'AUTHORIZED'))
            self.assertEqual((entry['estimatedCostCredits'], entry['estimatedCostCreditsChange']), ('250.00', '0.00'))
            self.assertNotIn('actualCostCredits', entry)

    def test_10_every_if_match_form(self):
        mission, tag = self.created(title='Tag forms')
        body = self.mission_xml(**self.fields(mission))
        before = self.snapshot()
        self.assert_error(self.put(mission['missionId'], body, None), 428, 'PRECONDITION_REQUIRED')
        for bad in ('*', 'W/' + tag, 'w/' + tag, tag.strip('"'), '"0' + tag.strip('"') + '"', '"0"', '"-1"', '"1.0"', '"abc"', '""', '',
                    tag + ', "99999999"', tag + ',' + tag, tag + ' ' + tag, tag + ', *', ' W/' + tag, "'" + tag.strip('"') + "'", tag[:-1]):
            self.assert_error(self.put(mission['missionId'], body, bad), 400, 'INVALID_REQUEST')
        self.assert_error(self.put(mission['missionId'], body, None, extra=[('If-Match', tag), ('If-Match', tag)]), 400, 'INVALID_REQUEST')
        self.assert_error(self.put(mission['missionId'], body, None, extra=[('If-Match', tag), ('If-Match', '*')]), 400, 'INVALID_REQUEST')
        # Well formed but stale or never issued: 412, including a tag beyond any stored change id.
        for stale in ('"1"', '"' + str(int(tag.strip('"')) + 1000) + '"', '"' + '9' * 40 + '"'):
            self.assert_error(self.put(mission['missionId'], body, stale), 412, 'ETAG_MISMATCH')
        self.assert_unchanged(before)
        self.assertEqual(self.put(mission['missionId'], body, tag).status, 200)

    def test_11_put_target_errors(self):
        mission, tag = self.created(title='Target errors')
        other, other_tag = self.created(title='Other target')
        body = self.mission_xml(**self.fields(mission))
        before = self.snapshot()
        for bad in ('st-00000LD4O', 'ST-00000LD4', 'ST-00000LD4OO', 'x', 'ST-0000lD4OO'):
            self.assert_error(self.put(bad, body, tag), 400, 'INVALID_MISSION_ID')
        self.assert_error(self.put('ST-ZZZZZZZZY', self.mission_xml(**dict(self.fields(mission), missionId='ST-ZZZZZZZZY')), tag), 404, 'MISSION_NOT_FOUND')
        # The body must carry the URI's mission: absent is 422, different is 409, lastUpdated is 422.
        self.assert_error(self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), missionId=None)), tag), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assert_error(self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), missionId=other['missionId'])), tag), 409, 'RESOURCE_CONFLICT')
        self.assert_error(self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), lastUpdated=mission['lastUpdated'])), tag), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assert_error(self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), title=' ')), tag), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assert_error(self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), status='ACTIVE')), tag), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assert_error(self.put(mission['missionId'], b'<mission/>', tag), 400, 'INVALID_REQUEST')
        # A tag issued for another mission is just another stale tag.
        self.assert_error(self.put(mission['missionId'], body, other_tag), 412, 'ETAG_MISMATCH')
        self.assert_unchanged(before)
        self.assertEqual(self.fetch(mission['missionId'])[1], tag)
        self.assertEqual(self.fetch(other['missionId'])[1], other_tag)

    def test_12_cost_audit_trail_follows_the_population_table(self):
        mission, tag = self.created(title='Cost trail', status='PLANNED', commander='C-1')
        steps = [
            # (builder changes, expected audit estimate, estimate change, actual, actual change)
            (dict(status='PLANNED', estimated='10.00'), '10.00', None, None, None),           # absent -> value
            (dict(status='PLANNED', estimated='10.00'), '10.00', '0.00', None, None),          # value -> same value
            (dict(status='PLANNED', estimated='25.50'), '25.50', '15.50', None, None),         # increase
            (dict(status='AUTHORIZED', estimated='20.00'), '20.00', '-5.50', None, None),      # decrease, negative
            (dict(status='PLANNED', estimated=None), None, None, None, None),                  # value -> absent
            (dict(status='PLANNED', estimated='0.00'), '0.00', None, None, None),              # absent -> zero is a value
            (dict(status='COMPLETED', estimated='0.00', actual='0.00'), '0.00', '0.00', '0.00', None),
            (dict(status='COMPLETED', estimated='9999999999999.99', actual='0.01'), '9999999999999.99', '9999999999999.99', '0.01', '0.01'),
            (dict(status='COMPLETED', estimated='0.00', actual='9999999999999.99'), '0.00', '-9999999999999.99', '9999999999999.99', '9999999999999.98'),
            (dict(status='FAILED', estimated='0.00', actual='0.00'), '0.00', '0.00', '0.00', '-9999999999999.99')]
        for changes, estimate, estimate_change, actual, actual_change in steps:
            fields = dict(self.fields(mission), commander='C-1', outcome=None, estimated=None, actual=None)
            fields.update(changes)
            response = self.put(mission['missionId'], self.mission_xml(**fields), tag)
            self.assertEqual(response.status, 200, str(changes) + str(response.body[:300]))
            tag = response.header('ETag')[0]
            entry = self.changes(mission['missionId'])[-1]
            self.assertEqual(entry.get('estimatedCostCredits'), estimate, str(changes))
            self.assertEqual(entry.get('estimatedCostCreditsChange'), estimate_change, str(changes))
            self.assertEqual(entry.get('actualCostCredits'), actual, str(changes))
            self.assertEqual(entry.get('actualCostCreditsChange'), actual_change, str(changes))

    def test_13_cancellation_provenance_follows_the_immediate_predecessor(self):
        def replace(mission_id, tag, status, **kw):
            fields = {'missionId': mission_id, 'status': status, 'commander': 'C-1', 'estimated': None, 'actual': None, 'title': 'Provenance'}
            fields.update(kw)
            return self.put(mission_id, self.mission_xml(**fields), tag)

        def flag(mission_id):
            return self.query("SELECT cancelled_without_estimate_allowed FROM missions WHERE mission_id = '" + mission_id + "';")[0].strip()
        mission, tag = self.created(title='Provenance')
        mid = mission['missionId']
        # PLANNED -> CANCELLED establishes the exemption; repeated CANCELLED -> CANCELLED keeps it.
        response = replace(mid, tag, 'CANCELLED', actual='0.00')
        self.assertEqual(response.status, 200, response.body[:300])
        self.assertEqual(flag(mid), '1')
        tag = response.header('ETag')[0]
        response = replace(mid, tag, 'CANCELLED', actual='12.00')
        self.assertEqual(response.status, 200, response.body[:300])
        self.assertEqual(flag(mid), '1')
        tag = response.header('ETag')[0]
        self.assertNotIn('estimatedCostCredits', self.mission_dict(response.xml()))
        # Leaving CANCELLED clears it: ACTIVE -> CANCELLED without an estimate is refused, and the refusal changes nothing.
        response = replace(mid, tag, 'ACTIVE', estimated='100.00')
        self.assertEqual(response.status, 200)
        self.assertEqual(flag(mid), '0')
        tag = response.header('ETag')[0]
        before = self.snapshot()
        self.assert_error(replace(mid, tag, 'CANCELLED', actual='0.00'), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assert_unchanged(before)
        # ...and CANCELLED -> CANCELLED does not restore it.
        response = replace(mid, tag, 'CANCELLED', estimated='100.00', actual='3.00')
        self.assertEqual(response.status, 200)
        self.assertEqual(flag(mid), '0')
        tag = response.header('ETag')[0]
        self.assert_error(replace(mid, tag, 'CANCELLED', actual='3.00'), 422, 'DOMAIN_VALIDATION_FAILED')
        # Later re-entry evaluates the immediate predecessor anew: through PLANNED the exemption is available again.
        response = replace(mid, tag, 'PLANNED')
        self.assertEqual(response.status, 200)
        tag = response.header('ETag')[0]
        response = replace(mid, tag, 'CANCELLED', actual='0.00')
        self.assertEqual(response.status, 200, response.body[:300])
        self.assertEqual(flag(mid), '1')
        # A PLANNED origin that supplies an estimate still establishes the exemption for a later replacement.
        other, other_tag = self.created(title='Provenance with estimate', estimated='40.00')
        response = replace(other['missionId'], other_tag, 'CANCELLED', estimated='40.00', actual='1.00')
        self.assertEqual(response.status, 200)
        self.assertEqual(flag(other['missionId']), '1')
        response = replace(other['missionId'], response.header('ETag')[0], 'CANCELLED', actual='1.00')
        self.assertEqual(response.status, 200, response.body[:300])
        # A seeded cancelled mission that was ACTIVE before has no exemption.
        cancelled = [m for m in self.data['missions'] if m['status'] == 'CANCELLED'][0]
        current, current_tag, _ = self.fetch(cancelled['missionId'])
        fields = dict(self.fields(current), estimated=None)
        before = self.snapshot()
        self.assert_error(self.put(cancelled['missionId'], self.mission_xml(**fields), current_tag), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assert_unchanged(before)

    # --- protocol --------------------------------------------------------------------------------------------

    def test_14_media_types_encoding_and_negotiation(self):
        body = self.mission_xml(title='Media probe')
        mission, tag = self.created(title='Media target')
        put_body = self.mission_xml(**dict(self.fields(mission), title='Media target changed'))
        before = self.snapshot()
        refused = [None, 'text/xml', 'application/json', 'application/atom+xml', 'application/*', '*/*', 'application/x-www-form-urlencoded',
                   'multipart/form-data; boundary=x', 'application/xml; charset=ISO-8859-1', 'application/xml; charset=utf-16',
                   'application/xml; charset=utf8', 'application/xml; version=1.0', 'application/xml; charset=utf-8; charset=utf-8',
                   'application/xml; charset=utf-8; boundary=x', 'application/xml;', 'application', '']
        for content_type in refused:
            self.assert_error(self.post(body, ctype=content_type), 415, 'UNSUPPORTED_MEDIA_TYPE')
            self.assert_error(self.put(mission['missionId'], put_body, tag, ctype=content_type), 415, 'UNSUPPORTED_MEDIA_TYPE')
        self.assert_error(self.post(body, ctype=None, extra=[('Content-Type', 'application/xml'), ('Content-Type', 'application/xml')]),
                          415, 'UNSUPPORTED_MEDIA_TYPE')
        self.assert_unchanged(before)
        # An unusable Content-Type on any other request is ignored, so routing still decides: reads and refusals are unaffected.
        for unusable in ('application', '', 'application/xml; charset'):
            self.assertEqual(self.call('/missions?pageSize=1', headers=[('Content-Type', unusable)]).status, 200, repr(unusable))
            self.assert_error(self.call('/missions', 'DELETE', headers=[('Content-Type', unusable)]), 405, 'METHOD_NOT_ALLOWED')
            self.assert_bodyless(self.call('/nothing-here', 'POST', headers=[('Content-Type', unusable)], body=b'x'), 404)
        self.assertEqual(self.call('/missions?pageSize=1', headers=[('Content-Type', 'application/xml'), ('Content-Type', 'application/xml')]).status, 200)
        for accepted in ('application/xml', 'APPLICATION/XML', 'application/xml;charset=UTF-8', 'application/xml; charset=utf-8',
                         'Application/Xml; CHARSET="UTF-8"', 'application/xml ; charset=utf-8'):
            self.assertEqual(self.post(body, ctype=accepted).status, 201, accepted)
        # XML bytes are UTF-8: another declared encoding, UTF-16 bytes and a BOM'd UTF-16 document are 400.
        text = body.decode('utf-8')
        for label, payload in (('latin-1 declaration', text.replace('encoding="UTF-8"', 'encoding="ISO-8859-1"').encode('latin-1')),
                               ('utf-16 declaration', text.replace('encoding="UTF-8"', 'encoding="UTF-16"').encode('utf-16')),
                               ('utf-16 bytes', text.encode('utf-16-le')), ('utf-16 with bom', text.encode('utf-16'))):
            before = self.snapshot()
            self.assert_error(self.post(payload), 400, 'INVALID_REQUEST')
            self.assert_unchanged(before)
        self.assertEqual(self.post(b'\xef\xbb\xbf' + body).status, 201)
        # No DTD and no entity is ever processed, and no file content ever reaches a response.
        for label, payload in (
                ('internal entity', text.replace('?>', '?><!DOCTYPE mission [<!ENTITY x "y">]>', 1).encode('utf-8')),
                ('external entity', text.replace('?>', '?><!DOCTYPE mission [<!ENTITY x SYSTEM "file:///etc/passwd">]>', 1).replace('Media probe', '&x;').encode('utf-8')),
                ('external dtd', text.replace('?>', '?><!DOCTYPE mission SYSTEM "http://127.0.0.1:9/x.dtd">', 1).encode('utf-8')),
                ('entity expansion', text.replace('?>', '?><!DOCTYPE m [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>', 1).replace('Media probe', '&b;').encode('utf-8'))):
            before = self.snapshot()
            response = self.post(payload)
            self.assert_error(response, 400, 'INVALID_REQUEST')
            self.assert_unchanged(before)
        # Accept applies to a mutation's response too: no acceptable XML range is a bodyless 406 and nothing is written.
        before = self.snapshot()
        for accept in ('application/json', 'text/xml', 'application/xml;q=0', '*/*, application/xml;q=0'):
            self.assert_bodyless(self.post(body, extra=[('Accept', accept)]), 406)
            self.assert_bodyless(self.put(mission['missionId'], put_body, tag, extra=[('Accept', accept)]), 406)
        for malformed in ('application/xml;q=2', ',', ''):
            self.assert_error(self.post(body, extra=[('Accept', malformed)]), 400, 'INVALID_REQUEST')
        self.assert_unchanged(before)
        self.assertEqual(self.post(body, extra=[('Accept', 'application/xml;q=0.9, */*;q=0.1')]).status, 201)

    def test_15_unsupported_methods_answer_405_with_each_paths_own_allow_list(self):
        known = self.data['missions'][0]['missionId']
        paths = {'/missions': 'GET, POST', '/missions/' + known: 'GET, PUT', '/missions/' + known + '/changes': 'GET'}
        before = self.snapshot()
        for path, header in paths.items():
            supported = header.split(', ')
            for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'):
                if method in supported:
                    continue
                response = self.mutate(method, path, b'<x/>' if method != 'HEAD' and method != 'OPTIONS' else None, tag='"1"')
                self.assertEqual(response.status, 405, method + ' ' + path)
                self.assertEqual(response.header('Allow'), [header], method + ' ' + path)
                if method == 'HEAD':
                    self.assertEqual(response.body, b'')
                else:
                    self.assert_error(response, 405, 'METHOD_NOT_ALLOWED')
            self.assertNotIn('HEAD', supported)
            self.assertNotIn('OPTIONS', supported)
        # An unknown path is a bodyless 404 for every method, and a mutation never reaches a mission-less path.
        for method in ('POST', 'PUT'):
            for path in ('/missions/', '/', '/mission', '/missions/' + known + '/', '/missions/' + known + '/changes/1'):
                self.assert_bodyless(self.mutate(method, path, self.mission_xml()), 404)
        self.assert_unchanged(before)

    def test_16_limits_and_unicode_round_trip(self):
        title = '\U0001F680' * 120
        objective = '\U0001F680' * 2000
        outcome = 'é' * 2000
        mission, tag = self.created(title=title, objective=objective, status='COMPLETED', commander='C-1', estimated='1.00', actual='1.00', outcome=outcome,
                                    location={'type': 'OTHER', 'name': '日' * 120, 'coordinates': '\U0001F680' * 120, 'travelVector': 'ü' * 120},
                                    crew=['C-%d' % n for n in range(1, 101)], participants=['P-%d' % n for n in range(1, 301)],
                                    assets=['SH-%d' % n for n in range(1, 51)])
        self.assertEqual((mission['title'], mission['objective'], mission['outcome']), (title, objective, outcome))
        self.assertEqual(mission['location'], {'type': 'OTHER', 'name': '日' * 120, 'coordinates': '\U0001F680' * 120, 'travelVector': 'ü' * 120})
        self.assertEqual(mission['assignedCrewIds'], sorted('C-%d' % n for n in range(1, 101)))
        self.assertEqual(mission['participantIds'], sorted('P-%d' % n for n in range(1, 301)))
        self.assertEqual(mission['assignedAssetIds'], sorted('SH-%d' % n for n in range(1, 51)))
        fetched = self.fetch(mission['missionId'])[0]
        self.assertEqual(fetched, mission)
        # The same document replaces itself.
        self.assertEqual(self.put(mission['missionId'], self.mission_xml(**self.fields(mission)), tag).status, 200)

    def test_16b_a_body_beyond_the_size_limit_is_refused_before_parsing(self):
        limit = 8 * 1024 * 1024
        before = self.snapshot()
        self.assert_error(self.post(b'<' + b'a' * limit), 400, 'INVALID_REQUEST')
        self.assert_unchanged(before)
        # The largest accepted body is still parsed, and then refused for what it is.
        self.assert_error(self.post(b'<' + b'a' * (limit - 1)), 400, 'INVALID_REQUEST')

    # --- concurrency, atomicity and failure -------------------------------------------------------------------

    def test_17_concurrent_writers(self):
        mission, tag = self.created(title='Contended', status='ACTIVE', commander='C-1', estimated='10.00', crew=['C-1'])
        workers = 8
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda n: self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), title='Writer %d' % n)), tag,
                                                        summary='Writer %d' % n), range(workers)))
        winners = [r for r in results if r.status == 200]
        losers = [r for r in results if r.status == 412]
        self.assertEqual((len(winners), len(losers)), (1, workers - 1), [r.status for r in results])
        for loser in losers:
            self.assert_error(loser, 412, 'ETAG_MISMATCH')
        final, final_tag, _ = self.fetch(mission['missionId'])
        self.assertEqual(final_tag, winners[0].header('ETag')[0])
        self.assertEqual(final['title'], self.mission_dict(winners[0].xml())['title'])
        self.assertEqual([entry['operation'] for entry in self.changes(mission['missionId'])], ['CREATED', 'UPDATED'])
        # Parallel creations and replacements on other missions: distinct identities, a gapless clock, one global order.
        others = [self.created(title='Parallel %d' % n, status='PLANNED')[0:2] for n in range(4)]
        before = self.snapshot()

        def create(n):
            return self.post(self.mission_xml(title='Burst %d' % n), summary='Burst %d' % n)

        def replace(item):
            mission_id, current_tag = item
            return self.put(mission_id, self.mission_xml(**dict(self.fields(self.fetch(mission_id)[0]), title='Replaced in a burst')), current_tag)
        with ThreadPoolExecutor(max_workers=8) as pool:
            created_futures = [pool.submit(create, n) for n in range(12)]
            replaced_futures = [pool.submit(replace, (m['missionId'], t)) for m, t in others]
            created = [f.result() for f in created_futures]
            replaced = [f.result() for f in replaced_futures]
        self.assertEqual([r.status for r in created], [201] * 12)
        self.assertEqual([r.status for r in replaced], [200] * 4)
        ids = [self.mission_dict(r.xml())['missionId'] for r in created]
        self.assertEqual(len(set(ids)), 12)
        tags = [int(r.header('ETag')[0].strip('"')) for r in created + replaced]
        self.assertEqual(len(set(tags)), 16)
        after = self.snapshot()
        self.assertEqual(after, (before[0] + 12, before[1] + 16, before[2] + 16))

    def test_18_a_forced_failure_rolls_back_the_mutation_its_audit_event_and_the_clock(self):
        operator.sql("CREATE OR REPLACE TRIGGER force_audit_failure BEFORE INSERT ON mission_changes FOR EACH ROW\n"
                     "WHEN (NEW.summary LIKE 'FORCE-FAIL%')\nBEGIN\n  RAISE_APPLICATION_ERROR(-20999, 'forced audit failure');\nEND;\n/", self.schema)
        try:
            mission, tag = self.created(title='Rollback target', status='ACTIVE', commander='C-1', estimated='10.00', crew=['C-1', 'C-2'],
                                        participants=['P-1'], assets=['SH-1'])
            _, _, reference_body = self.fetch(mission['missionId'])
            log_before = self.changes(mission['missionId'])
            before = self.snapshot()
            sequences = self.query("SELECT last_number FROM all_sequences WHERE sequence_owner = '" + self.schema + "' AND sequence_name = 'CHANGE_ID_SEQ';")[0].strip()
            # POST: the mission row, its collections, the clock tick and the sequences are all inside the failed transaction.
            response = self.post(self.mission_xml(title='Never stored', crew=['C-9'], assets=['SH-9']), summary='FORCE-FAIL create')
            self.assert_error(response, 500, 'INTERNAL_ERROR')
            self.assert_unchanged(before)
            self.assertEqual(self.query("SELECT COUNT(*) FROM missions WHERE title = 'Never stored';")[0].strip(), '0')
            # PUT: the row update and the replaced collections are rolled back as well.
            response = self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), title='Half written', crew=['C-7'], participants=[],
                                                                              assets=['SH-8', 'SH-9'], estimated='99.00')), tag, summary='FORCE-FAIL replace')
            self.assert_error(response, 500, 'INTERNAL_ERROR')
            self.assert_unchanged(before)
            _, after_tag, after_body = self.fetch(mission['missionId'])
            self.assertEqual((after_tag, after_body), (tag, reference_body))
            self.assertEqual(self.changes(mission['missionId']), log_before)
            self.assertNotEqual(self.query("SELECT last_number FROM all_sequences WHERE sequence_owner = '" + self.schema + "' AND sequence_name = 'CHANGE_ID_SEQ';")[0].strip(), sequences,
                                'sequences are nontransactional: the failed attempts consumed values, which leaves permitted gaps')
        finally:
            operator.sql('DROP TRIGGER force_audit_failure;', self.schema)
        # With the fault gone the same request succeeds, and its change id leaves a gap, never a reuse.
        response = self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), title='Written after the fault')), tag)
        self.assertEqual(response.status, 200)
        self.assertGreater(int(response.header('ETag')[0].strip('"')), int(tag.strip('"')) + 1)

    def test_19_database_failure_is_a_clean_500_but_contract_answers_need_no_database(self):
        body = self.mission_xml(title='No database')
        existing = self.data['missions'][0]['missionId']
        mutate = lambda method, path, payload, **kw: self.mutate(method, path, payload, base=self.bad_base, **kw)
        self.assert_error(mutate('POST', '/missions', body), 500, 'INTERNAL_ERROR')
        self.assert_error(mutate('PUT', '/missions/' + existing, self.mission_xml(missionId=existing), tag='"1"'), 500, 'INTERNAL_ERROR')
        # Everything decided before the database is still answered precisely.
        self.assert_error(mutate('POST', '/missions', body, ctype='text/xml'), 415, 'UNSUPPORTED_MEDIA_TYPE')
        self.assert_error(mutate('POST', '/missions', body, omit=('summary',)), 400, 'INVALID_REQUEST')
        self.assert_error(mutate('POST', '/missions', b'<mission/>'), 400, 'INVALID_REQUEST')
        self.assert_error(mutate('POST', '/missions', self.mission_xml(title=' ')), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assert_error(mutate('PUT', '/missions/' + existing, self.mission_xml(missionId=existing), tag=None), 428, 'PRECONDITION_REQUIRED')
        self.assert_error(mutate('PUT', '/missions/' + existing, self.mission_xml(missionId=existing), tag='*'), 400, 'INVALID_REQUEST')
        self.assert_error(mutate('PUT', '/missions/bad', self.mission_xml(missionId=existing), tag='"1"'), 400, 'INVALID_MISSION_ID')
        self.assert_error(mutate('PUT', '/missions/' + existing, self.mission_xml(missionId='ST-000000001'), tag='"1"'), 409, 'RESOURCE_CONFLICT')

    def test_20_a_valid_reference_beyond_the_physical_capacity_is_422_and_never_truncated(self):
        # Decision of 2026-10-15: references have a 50-byte physical capacity while the wire grammar is unbounded. A valid
        # reference that cannot fit is refused as 422 DOMAIN_VALIDATION_FAILED with the XML body, counted in UTF-8 bytes;
        # nothing is truncated or stored and the clock is untouched.
        existing, tag = self.created(title='Capacity target')
        long_crew = 'C-' + '9' * 60
        before = self.snapshot()
        for name, response in (
                ('crew', self.post(self.mission_xml(title='Too wide', crew=[long_crew]))),
                ('participant', self.post(self.mission_xml(title='Too wide', participants=['P-' + '9' * 49]))),
                ('asset', self.post(self.mission_xml(title='Too wide', assets=['SH-' + '9' * 48]))),
                ('commander', self.post(self.mission_xml(title='Too wide', status='ACTIVE', commander='C-' + '9' * 49, estimated='1.00'))),
                ('user header', self.post(self.mission_xml(title='Too wide actor'), user=long_crew)),
                ('ordered-by header', self.post(self.mission_xml(title='Too wide actor'), ordered=long_crew))):
            self.assert_error(response, 422, 'DOMAIN_VALIDATION_FAILED')
            self.assertIn('storage capacity', response.xml().find(q('message')).text, name)
        put_body = self.mission_xml(**dict(self.fields(existing), crew=[long_crew]))
        self.assert_error(self.put(existing['missionId'], put_body, tag), 422, 'DOMAIN_VALIDATION_FAILED')
        self.assert_unchanged(before)
        self.assertEqual(self.fetch(existing['missionId'])[1], tag)
        self.assertEqual(self.query("SELECT COUNT(*) FROM missions WHERE title LIKE 'Too wide%';")[0].strip(), '0')
        fits = 'C-' + '9' * 48
        self.assertEqual(self.created(title='Widest stored', crew=[fits])[0]['assignedCrewIds'], [fits])

    # --- global invariants ----------------------------------------------------------------------------------

    def test_90_the_clock_is_gapless_and_change_order_is_global(self):
        counter = self.snapshot()[2]
        self.assertEqual(counter, type(self).committed, 'every committed mutation advanced the clock once and no refused request did')
        rows = [line.strip().split('|') for line in self.query(
            "SELECT TO_CHAR(change_id,'FM9999999999999999999999999990')||'|'||TO_CHAR(changed_at,'YYYY-MM-DD\"T\"HH24:MI:SS.FF3\"Z\"') "
            "FROM mission_changes WHERE change_id > " + str(self.seed_max_change) + " ORDER BY change_id;")]
        self.assertEqual(len(rows), counter)
        for position, (change_id, changed_at) in enumerate(rows, start=1):
            self.assertEqual(changed_at, self.stamp(position), 'change ' + change_id + ' must be baseline + ' + str(position) + ' s')
        self.assertEqual(len({int(r[0]) for r in rows}), len(rows))
        # The seeded history is untouched.
        self.assertEqual(self.query("SELECT COUNT(*) FROM mission_changes WHERE change_id <= " + str(self.seed_max_change) + ";")[0].strip(),
                         str(self.seed_changes))

    # --- sequences ------------------------------------------------------------------------------------------

    def test_95_change_id_sequence_overflow_fails_without_wrapping(self):
        mission, tag = self.created(title='Change sequence edge')
        self.reseed('change_id_seq', 9999999999999999999999999999)
        response = self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), title='Last change id')), tag)
        self.assertEqual(response.status, 200, response.body[:300])
        top_tag = response.header('ETag')[0]
        self.assertEqual(top_tag, '"' + '9' * 28 + '"')
        self.assertEqual(self.changes(mission['missionId'])[-1]['changeId'], '9' * 28)
        before = self.snapshot()
        self.assert_error(self.put(mission['missionId'], self.mission_xml(**dict(self.fields(mission), title='Past the end')), top_tag), 500, 'INTERNAL_ERROR')
        self.assert_error(self.post(self.mission_xml(title='Past the end')), 500, 'INTERNAL_ERROR')
        self.assert_unchanged(before)
        self.assertEqual(self.fetch(mission['missionId'])[1], top_tag)
        # Repair the disposable schema so the later sequence tests can still write.
        self.reseed('change_id_seq', 9999999)

    def test_96_a_generated_identifier_that_already_exists_is_409(self):
        first = self.data['missions'][0]['missionId']
        self.reseed('mission_id_seq', int(first[3:], 36))
        before = self.snapshot()
        self.assert_error(self.post(self.mission_xml(title='Collides with the release')), 409, 'RESOURCE_CONFLICT')
        self.assert_unchanged(before)
        highest = max(self.query("SELECT mission_id FROM missions;"))
        next_free = int(highest.strip()[3:], 36) + 1
        self.reseed('mission_id_seq', next_free)
        mission, _ = self.created(title='Generated after the conflict')
        self.assertEqual(int(mission['missionId'][3:], 36), next_free)

    def test_97_mission_identifier_overflow_fails_without_wrapping_or_reuse(self):
        self.reseed('mission_id_seq', MISSION_SEQUENCE_MAX)
        mission, _ = self.created(title='Last identifier')
        self.assertEqual(mission['missionId'], 'ST-ZZZZZZZZZ')
        before = self.snapshot()
        self.assert_error(self.post(self.mission_xml(title='Past the last identifier')), 500, 'INTERNAL_ERROR')
        self.assert_unchanged(before)
        self.assertEqual(self.fetch('ST-ZZZZZZZZZ')[0]['title'], 'Last identifier')
        self.assertEqual(self.query("SELECT COUNT(*) FROM missions WHERE title = 'Past the last identifier';")[0].strip(), '0')


if __name__ == '__main__':
    import unittest
    unittest.main()
