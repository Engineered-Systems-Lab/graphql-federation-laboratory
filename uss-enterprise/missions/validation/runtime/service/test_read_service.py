"""Missions read acceptance: the real Jersey/Tomcat service over plain JDBC against real Oracle 18c.

GET /missions, GET /missions/{id} and GET /missions/{id}/changes with filters, paging, negotiation and error mapping,
through a login that can only SELECT, so no read path can write. The write operations (POST and PUT) have their own
gate in test_write_service.py; here they are exercised only on the paths where they are not supported (405).

The disposable image, schema, login and containers come from service_harness.py. The reviewed Oracle container must
already be provisioned; missing Docker, Oracle or Maven (inside the image build) is a failure, never a skip.
"""

import service_harness as harness
from service_harness import q
from lxml import etree

operator = harness.operator


class ReadServiceAcceptance(harness.ServiceCase):
    KIND = 'read'

    @classmethod
    def grants(cls):
        # A login that can only read the six tables.
        return ['GRANT SELECT ON ' + cls.schema + '.' + table + ' TO ' + cls.login + ';' for table in operator.TABLES]

    # --- acceptance ---------------------------------------------------------------------------------------

    def test_01_every_mission_equals_the_release_with_its_strong_etag(self):
        self.assertEqual(len(self.data['missions']), 31)
        for mission in self.data['missions']:
            response = self.call('/missions/' + mission['missionId'])
            document = self.ok_xml(response, 'mission')
            self.assertEqual(self.mission_dict(document), self.expected(mission), mission['missionId'])
            self.assertEqual(response.header('ETag'), ['"' + mission['currentChangeId'] + '"'])
            self.assertEqual(len(response.xml().findall(q('assignedCrewIds'))), 1)

    def test_02_list_order_paging_and_beyond_end(self):
        ordered = [self.expected(m) for m in self.ordered()]
        meta, first = self.listing()
        self.assertEqual(meta, ['1', '20', '31', '2'])
        meta, second = self.listing('?page=2')
        self.assertEqual(meta, ['2', '20', '31', '2'])
        self.assertEqual(first + second, ordered)
        meta, beyond = self.listing('?page=3')
        self.assertEqual((meta, beyond), (['3', '20', '31', '2'], []))
        meta, beyond = self.listing('?page=99999999999999999999')
        self.assertEqual((meta, beyond), (['99999999999999999999', '20', '31', '2'], []))
        collected = []
        for page in range(1, 8):
            meta, rows = self.listing('?pageSize=5&page=' + str(page))
            self.assertEqual(meta[1:], ['5', '31', '7'])
            collected += rows
        self.assertEqual(collected, ordered)
        meta, one = self.listing('?pageSize=50')
        self.assertEqual(one, ordered)
        # The list carries no per-mission concurrency token; the member list is direct, with no wrapper element.
        document = self.call('/missions?pageSize=1').xml()
        self.assertEqual([etree.QName(c).localname for c in document],
                         ['page', 'pageSize', 'totalCount', 'totalPages', 'mission'])

    def test_03_every_filter_and_their_conjunction(self):
        missions = self.data['missions']
        selectors = {
            'type': lambda m, v: m['type'] == v, 'classification': lambda m, v: m['classification'] == v,
            'status': lambda m, v: m['status'] == v, 'priority': lambda m, v: str(m['priority']) == v,
            'issuingAuthority': lambda m, v: m['issuingAuthority'] == v,
            'commandingOfficerId': lambda m, v: m.get('commandingOfficerId') == v,
            'assignedCrewId': lambda m, v: v in m['assignedCrewIds'], 'assignedAssetId': lambda m, v: v in m['assignedAssetIds'],
            'locationType': lambda m, v: m['location']['type'] == v}
        values = {
            'type': {m['type'] for m in missions}, 'classification': {m['classification'] for m in missions},
            'status': {m['status'] for m in missions}, 'priority': {str(m['priority']) for m in missions},
            'issuingAuthority': {m['issuingAuthority'] for m in missions},
            'commandingOfficerId': {m['commandingOfficerId'] for m in missions if 'commandingOfficerId' in m},
            'assignedCrewId': {c for m in missions for c in m['assignedCrewIds']},
            'assignedAssetId': {a for m in missions for a in m['assignedAssetIds']},
            'locationType': {m['location']['type'] for m in missions}}
        checked = 0
        for name, choices in values.items():
            for value in sorted(choices):
                expected = [self.expected(m) for m in self.ordered([m for m in missions if selectors[name](m, value)])]
                meta, rows = self.listing('?pageSize=50&' + name + '=' + value)
                self.assertEqual(rows, expected, name + '=' + value)
                self.assertEqual(meta[2], str(len(expected)))
                self.assertEqual(meta[3], str((len(expected) + 49) // 50))
                checked += 1
        self.assertGreater(checked, 40)
        # Singular membership filters, AND semantics and zero matches reporting zero pages.
        crew = sorted(values['assignedCrewId'])[0]
        status = 'COMPLETED'
        expected = [self.expected(m) for m in self.ordered(
            [m for m in missions if crew in m['assignedCrewIds'] and m['status'] == status])]
        self.assertEqual(self.listing('?assignedCrewId=' + crew + '&status=' + status)[1], expected)
        meta, rows = self.listing('?assignedCrewId=C-999999')
        self.assertEqual((meta, rows), (['1', '20', '0', '0'], []))
        document = self.call('/missions?assignedCrewId=C-999999').xml()
        self.assertEqual(len(document.findall(q('mission'))), 0)

    def test_04_change_log_numeric_order_and_paging(self):
        by_mission = {}
        for change in self.data['changes']:
            by_mission.setdefault(change['missionId'], []).append(change)
        self.assertEqual(sum(len(v) for v in by_mission.values()), 101)
        for mission_id, expected in by_mission.items():
            expected = sorted(expected, key=lambda c: int(c['changeId']))
            document = self.ok_xml(self.call('/missions/' + mission_id + '/changes?pageSize=50'), 'changeList')
            self.assertEqual([document.findtext(q(n)) for n in ('page', 'pageSize', 'totalCount', 'totalPages')],
                             ['1', '50', str(len(expected)), '1'])
            self.assertEqual([self.change_dict(c) for c in document.findall(q('change'))], expected, mission_id)
            collected = []
            for page in range(1, len(expected) + 1):
                part = self.ok_xml(self.call('/missions/' + mission_id + '/changes?pageSize=1&page=' + str(page)), 'changeList')
                collected += [self.change_dict(c) for c in part.findall(q('change'))]
            self.assertEqual(collected, expected)
            beyond = self.ok_xml(self.call('/missions/' + mission_id + '/changes?page=' + str(len(expected) + 1) + '&pageSize=1'), 'changeList')
            self.assertEqual(len(beyond.findall(q('change'))), 0)
            self.assertEqual(beyond.findtext(q('totalPages')), str(len(expected)))
        self.assertEqual(self.call('/missions/' + next(iter(by_mission)) + '/changes').header('ETag'), [])

    def test_05_error_mapping(self):
        known = self.data['missions'][0]['missionId']
        for query in ('?bogus=1', '?status=ACTIVE&status=ACTIVE', '?page=1&page=1', '?pageSize=5&pageSize=5', '?type=ENGINEERING',
                      '?status=', '?priority=6', '?page=0', '?page=01', '?pageSize=51', '?commandingOfficerId=P-1',
                      '?assignedAssetId=sh-17', '?type=%5B', '?%5B=1'):
            self.assert_error(self.call('/missions' + query), 400, 'INVALID_REQUEST')
        for query in ('?status=ACTIVE', '?bogus=1', '?page=1&page=2', '?pageSize=0'):
            self.assert_error(self.call('/missions/' + known + '/changes' + query), 400, 'INVALID_REQUEST')
        for bad in ('st-00000LD4O', 'ST-00000LD4', 'ST-00000LD4OO', 'x', 'ST-0000lD4OO'):
            self.assert_error(self.call('/missions/' + bad), 400, 'INVALID_MISSION_ID')
            self.assert_error(self.call('/missions/' + bad + '/changes'), 400, 'INVALID_MISSION_ID')
        self.assert_error(self.call('/missions/ST-ZZZZZZZZZ'), 404, 'MISSION_NOT_FOUND')
        self.assert_error(self.call('/missions/ST-ZZZZZZZZZ/changes'), 404, 'MISSION_NOT_FOUND')
        # The frozen contract has no error body for an unknown path: bodyless 404.
        for path in ('/', '/other', '/missions/', '/missions/' + known + '/', '/missions/' + known + '/other',
                     '/missions/' + known + '/changes/1', '/Missions'):
            self.assert_bodyless(self.call(path), 404)

    def test_06_unsupported_methods_answer_405_with_each_paths_own_allow_list(self):
        known = self.data['missions'][0]['missionId']
        allow = {'/missions': 'GET, POST', '/missions/' + known: 'GET, PUT', '/missions/' + known + '/changes': 'GET'}
        for path, header in allow.items():
            supported = header.split(', ')
            for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'):
                if method in supported:
                    continue
                response = self.call(path, method, body=b'<x/>' if method in ('POST', 'PUT', 'PATCH') else None)
                self.assertEqual(response.status, 405, method + ' ' + path)
                self.assertEqual(response.header('Allow'), [header])
                if method == 'HEAD':
                    self.assertEqual(response.body, b'')
                else:
                    self.assert_error(response, 405, 'METHOD_NOT_ALLOWED')
            # The framework never answers HEAD or OPTIONS for a supported GET, and neither is ever advertised.
            self.assertNotIn('HEAD', header)
            self.assertNotIn('OPTIONS', header)

    def test_07_accept_negotiation(self):
        def accept(*lines):
            return self.call('/missions?pageSize=1', headers=[('Accept', line) for line in lines])
        for good in ('application/xml', 'APPLICATION/XML', '*/*', 'application/*', 'text/html, application/xml;q=0.1',
                     'application/xml;charset=utf-8', 'application/xml;q=0.5, */*;q=0'):
            self.assertEqual(accept(good).status, 200, good)
        self.assertEqual(self.call('/missions?pageSize=1').status, 200)
        for excluded in ('application/json', 'text/xml', 'application/xml;q=0', '*/*, application/xml;q=0',
                         'application/*;q=0, */*', 'application/xml;version=2', 'application/xml;charset=latin1'):
            self.assert_bodyless(accept(excluded), 406)
        self.assertEqual(accept('text/html', '*/*').status, 200)
        self.assert_bodyless(accept('application/xml;q=0', 'text/html'), 406)
        for malformed in ('application/xml;q=2', 'application/xml;q=abc', 'application/xml;q=0.1234', ',', 'application', ''):
            self.assert_error(accept(malformed), 400, 'INVALID_REQUEST')
        self.assert_bodyless(self.call('/missions/ST-ZZZZZZZZZ', headers=[('Accept', 'application/json')]), 406)

    def test_08_database_failure_is_a_clean_500(self):
        for path in ('/missions', '/missions/' + self.data['missions'][0]['missionId'], '/missions/ST-ZZZZZZZZZ/changes'):
            response = self.get(self.bad_base, path)
            self.assert_error(response, 500, 'INTERNAL_ERROR')
        # Contract-level answers do not need the database.
        self.assert_error(self.get(self.bad_base, '/missions?bogus=1'), 400, 'INVALID_REQUEST')
        self.assert_bodyless(self.get(self.bad_base, '/other'), 404)


if __name__ == '__main__':
    import unittest
    unittest.main()
