"""Integrity, schema, reproducibility, and independent relational checks for B."""
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
from decimal import Decimal
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import derive_b as b


SCHEMA_KEYWORDS = {'type', 'enum', 'properties', 'required',
                   'additionalProperties', 'items', 'description'}


def validate(value, schema, path='$'):
    """Validate all features used here; fail closed on an unimplemented keyword."""
    unknown = set(schema) - SCHEMA_KEYWORDS
    if unknown:
        raise ValueError('Unsupported schema keywords: ' + repr(unknown))
    predicates = {
        'null': lambda v: v is None,
        'boolean': lambda v: isinstance(v, bool),
        'string': lambda v: isinstance(v, str),
        'integer': lambda v: not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) and int(v) == v,
        'number': lambda v: not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v),
        'array': lambda v: isinstance(v, list),
        'object': lambda v: isinstance(v, dict),
    }
    types = schema.get('type', list(predicates))
    if isinstance(types, str):
        types = [types]
    if any(t not in predicates for t in types):
        raise ValueError('Unsupported schema type')
    if not any(predicates[t](value) for t in types):
        raise AssertionError(path + ': incorrect type')
    if 'enum' in schema:
        # Enum values in this corpus are strings; retain strict bool/number separation.
        if not any(value == candidate and (isinstance(value, bool) == isinstance(candidate, bool)) for candidate in schema['enum']):
            raise AssertionError(path + ': value outside enum')
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        missing = set(schema.get('required', [])) - value.keys()
        if missing:
            raise AssertionError(path + ': missing ' + repr(missing))
        extra = value.keys() - properties.keys()
        additional = schema.get('additionalProperties', True)
        if additional is False and extra:
            raise AssertionError(path + ': unexpected ' + repr(extra))
        for field, child in value.items():
            if field in properties:
                validate(child, properties[field], path + '.' + field)
            elif isinstance(additional, dict):
                validate(child, additional, path + '.' + field)
    if isinstance(value, list) and 'items' in schema:
        for index, child in enumerate(value):
            validate(child, schema['items'], path + '[' + str(index) + ']')


class DerivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.inputs, cls.contents = b.verify_package()
        cls.data = b.Data(cls.contents)
        cls.document = json.loads(b.OUTPUT.read_bytes())
        cls.keys = cls.document['keys']
        # Independent relational calculations use SQL DISTINCT rather than the
        # derivation's Python set helpers, and integer cents rather than Decimal sums.
        cls.db = sqlite3.connect(':memory:')
        cls.db.executescript('''
            CREATE TABLE mission(id TEXT PRIMARY KEY, kind TEXT, authority TEXT,
                status TEXT, classification TEXT, officer TEXT, estimate INTEGER, actual INTEGER);
            CREATE TABLE staff(mid TEXT, ref TEXT);
            CREATE TABLE use_asset(mid TEXT, ref TEXT);
            CREATE TABLE crew_map(version TEXT, ref TEXT, pid TEXT);
            CREATE TABLE asset_map(ref TEXT, aid TEXT);
            CREATE TABLE person(id TEXT PRIMARY KEY, rank TEXT, department TEXT, duty TEXT);
            CREATE TABLE asset(id TEXT PRIMARY KEY, status TEXT);
        ''')
        def cents(value):
            if value is None:
                return None
            whole, fraction = value.split('.')
            return int(whole) * 100 + int(fraction)
        for m in cls.data.missions.values():
            cls.db.execute('INSERT INTO mission VALUES(?,?,?,?,?,?,?,?)', (
                m['missionId'], m['type'], m['issuingAuthority'], m['status'],
                m['classification'], m.get('commandingOfficerId'),
                cents(m.get('estimatedCostCredits')), cents(m.get('actualCostCredits'))))
            refs = list(m['assignedCrewIds'])
            if m.get('commandingOfficerId'):
                refs.append(m['commandingOfficerId'])
            cls.db.executemany('INSERT INTO staff VALUES(?,?)', [(m['missionId'], r) for r in refs])
            cls.db.executemany('INSERT INTO use_asset VALUES(?,?)', [(m['missionId'], r) for r in m['assignedAssetIds']])
        for version, sections in cls.data.mappings.items():
            cls.db.executemany('INSERT INTO crew_map VALUES(?,?,?)', [(version, r, p) for r, p in sections.get('crew', {}).items()])
        cls.db.executemany('INSERT INTO asset_map VALUES(?,?)', cls.data.mappings['1.3']['assets'].items())
        cls.db.executemany('INSERT INTO person VALUES(?,?,?,?)', [(p['personnelId'], p['rank'], p['department'], p['dutyStatus']) for p in cls.data.people.values()])
        cls.db.executemany('INSERT INTO asset VALUES(?,?)', [(a['assetId'], a['status']) for a in cls.data.assets.values()])

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def answer(self, tid):
        return self.keys[tid]['answer']

    def test_every_packaged_input_and_package_digest(self):
        manifest = json.loads((b.ROOT / 'MANIFEST.json').read_bytes())
        expected = manifest.pop('packageSha256')
        raw = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode('utf-8')
        self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)
        self.assertEqual(expected, self.document['packageSha256'])
        self.assertEqual(manifest['labCommit'], self.document['labCommit'])
        self.assertEqual(len(manifest['files']), 69)
        for entry in manifest['files']:
            with self.subTest(path=entry['path']):
                raw = (b.ROOT / entry['path']).read_bytes()
                self.assertEqual(len(raw), entry['size'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['sha256'])
                self.assertEqual(self.document['inputs'][entry['path']], entry['sha256'])
        self.assertEqual(self.document['inputs'], self.inputs)
        # MANIFEST cannot list its own hash without a circular dependency.
        self.assertEqual(self.inputs['MANIFEST.json'], hashlib.sha256((b.ROOT / 'MANIFEST.json').read_bytes()).hexdigest())

    def test_integrity_failure_stops_derivation(self):
        fake = {'files': [], 'packageSha256': '0' * 64}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'MANIFEST.json').write_text(json.dumps(fake))
            with self.assertRaisesRegex(ValueError, 'Package SHA-256 mismatch'):
                b.verify_package(root)
            unsigned = {'files': [{'path': 'x', 'size': 1, 'sha256': hashlib.sha256(b'x').hexdigest()}]}
            fake = {**unsigned, 'packageSha256': hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
            (root / 'MANIFEST.json').write_text(json.dumps(fake))
            (root / 'x').write_bytes(b'y')
            with self.assertRaisesRegex(ValueError, 'Packaged input mismatch'):
                b.verify_package(root)

    def test_exact_task_coverage_and_sets(self):
        expected = {}
        for filename, default_set in [('pool', 'core'), ('ambiguity', 'ambiguity'), ('dev', 'dev')]:
            tasks = json.loads(self.contents['study/corpus2/' + filename + '.json'])['tasks']
            for task in tasks:
                self.assertNotIn(task['id'], expected)
                expected[task['id']] = task.get('set', default_set)
        self.assertEqual(len(expected), 90)
        self.assertEqual(set(self.keys), set(expected))
        for tid, key in self.keys.items():
            self.assertEqual(key['taskId'], tid)
            self.assertEqual(key['set'], expected[tid])
            self.assertTrue(key['basis'])
        self.assertEqual(Counter(expected.values()), {'core': 76, 'ambiguity': 6, 'dev': 8})

    def test_all_answers_variants_and_interpretations_match_schemas(self):
        for tid, key in self.keys.items():
            answers = [key['answer']] + [v['answer'] for v in key['variants']]
            answers += [v['answer'] for v in key.get('interpretations', {}).values()]
            for index, answer in enumerate(answers):
                with self.subTest(task=tid, answer=index):
                    validate(answer, self.data.tasks[tid]['schema'])
            for variant in key['variants']:
                self.assertTrue(variant['reason'])
                self.assertNotEqual(variant['answer'], key['answer'])
            self.assertEqual(len(key['variants']), len({b.encode(v['answer']) for v in key['variants']}))

    def test_validator_rejects_invalid_answers(self):
        schema = self.data.tasks['A02']['schema']
        original = self.answer('A02')
        for invalid in ({**original, 'priority': True}, {**original, 'extra': 1},
                        {**original, 'answerStatus': 'WRONG'}, {**original, 'priority': '2'},
                        {k: v for k, v in original.items() if k != 'classification'}):
            with self.assertRaises(AssertionError):
                validate(invalid, schema)
        with self.assertRaises(AssertionError):
            validate([{'assetId': 42, 'status': 'ACTIVE'}], self.data.tasks['G05']['schema']['properties']['assets'])
        with self.assertRaises(ValueError):
            validate(1, {'type': 'integer', 'unknownKeyword': True})
        with self.assertRaises(AssertionError):
            validate(float('nan'), {'type': 'number'})
        validate(None, {'type': ['string', 'null']})
        validate(1.0, {'type': 'integer'})

    def test_all_closed_interpretations_and_first_default(self):
        for tid, task in self.data.tasks.items():
            key = self.keys[tid]
            if task['set'] != 'ambiguity':
                self.assertNotIn('interpretations', key)
                continue
            accepted = task['acceptedInterpretations']
            self.assertEqual(set(key['interpretations']), {r['name'] for r in accepted})
            self.assertEqual(key['answer'], key['interpretations'][accepted[0]['name']]['answer'])
            for reading in accepted:
                interpretation = key['interpretations'][reading['name']]['answer']['interpretation']
                self.assertEqual(set(interpretation), set(reading['definition']))
                for field, rule in reading['definition'].items():
                    operation, value = next(iter(rule.items()))
                    if operation == 'set':
                        self.assertEqual(set(interpretation[field]), set(value))
                    else:
                        self.assertEqual(interpretation[field], value)

    def test_cli_comparison_and_two_runs_identical_bytes(self):
        command = [sys.executable, '-B', str(b.ROOT / 'study/corpus2/derive_b.py')]
        first = subprocess.run(command, cwd=b.ROOT, capture_output=True, check=True)
        second = subprocess.run(command, cwd=b.ROOT, capture_output=True, check=True)
        self.assertIn(b'No difference', first.stdout)
        self.assertEqual(first.stdout, second.stdout)
        original = b.OUTPUT.read_bytes()
        self.assertEqual(b.encode(b.derive()), original)
        self.assertEqual(b.encode(b.derive()), original)
        # Exercise --write twice without modifying the package's result file.
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'keys.json'
            with patch.object(b, 'OUTPUT', output), redirect_stdout(io.StringIO()):
                self.assertEqual(b.main(['--write']), 0)
                one = output.read_bytes()
                self.assertEqual(b.main(['--write']), 0)
                self.assertEqual(output.read_bytes(), one)
                self.assertEqual(one, original)
                output.write_bytes(one + b' ')
                with redirect_stderr(io.StringIO()):
                    self.assertNotEqual(b.main([]), 0)

    def test_personnel_paging_civilians_and_boundary_records(self):
        self.assertEqual(self.data.page_counts, [100] * 10)
        ns = {'p': 'urn:graphql-federation-lab:personnel:v2'}
        ids = []
        civilians = []
        security = []
        for index in range(10):
            tree = ET.fromstring(self.contents[b.PERSONNEL + 'page-%03d.xml' % index])
            for p in tree.findall('p:personnelMember', ns):
                pid = p.findtext('p:personnelId', namespaces=ns)
                ids.append(pid)
                if p.find('p:civilianDetails', ns) is not None:
                    civilians.append(pid)
                if p.findtext('p:crewDetails/p:department', namespaces=ns) == 'SECURITY':
                    security.append(pid)
        self.assertEqual(len(ids), 1000)
        self.assertEqual(len(set(ids)), 1000)
        self.assertEqual(set(ids), set(self.data.people))
        self.assertEqual(len(civilians), 219)  # Not just the 199 newly added civilians.
        self.assertEqual(self.answer('G08')['personnelIds'], sorted(civilians))
        self.assertEqual(self.answer('G03')['personnelIds'], sorted(security))
        self.assertIn('PRS-3199', self.answer('G08')['personnelIds'])

    def test_mapping_release_isolation_and_resolution_outcomes(self):
        self.assertEqual(self.data.crew_map('1.0'), {})
        self.assertEqual(len(self.data.crew_map('1.1')), 10)
        self.assertNotIn('C-1638', self.data.crew_map('1.1'))
        self.assertEqual(self.data.crew_map('1.3')['C-1638'], 'PRS-2382')
        self.assertEqual(self.answer('C06'), {'answerStatus': 'ANSWERED', 'release11PersonnelId': None, 'release13PersonnelId': 'PRS-2382'})
        self.assertEqual(self.data.asset_outcome('EQ-86'), 'RESOLVED')
        self.assertEqual(self.data.asset_outcome('EQ-97'), 'UNRESOLVED')
        self.assertEqual(self.data.asset_outcome('EQ-108'), 'UNMAPPED')
        self.assertEqual(self.answer('C12'), {'answerStatus': 'ANSWERED', 'resolved': 6, 'unresolved': 1, 'unmapped': 43})
        self.assertNotIn('AST-0097', self.data.asset_ids(self.data.missions['ST-00000LD5M']))
        self.assertIn('AST-0097', self.data.asset_ids(self.data.missions['ST-00000LD5M'], held=False))

    def test_sql_mapping_and_missing_reference_joins(self):
        rows = self.db.execute('''SELECT m.id FROM mission m
            JOIN crew_map c ON c.ref=m.officer AND c.version='1.3'
            WHERE c.pid='PRS-0001' ORDER BY m.id''').fetchall()
        self.assertEqual(self.answer('B10')['missionIds'], [r[0] for r in rows])
        rows = self.db.execute('''SELECT DISTINCT m.id FROM mission m JOIN staff s ON s.mid=m.id
            LEFT JOIN crew_map c ON c.ref=s.ref AND c.version='1.3'
            WHERE m.classification='SECRET' AND c.pid IS NULL ORDER BY m.id''').fetchall()
        self.assertEqual(self.answer('C09')['missionIds'], [r[0] for r in rows])
        rows = self.db.execute('''SELECT m.id FROM mission m WHERE m.kind='DIPLOMATIC'
            AND EXISTS(SELECT 1 FROM staff s WHERE s.mid=m.id)
            AND NOT EXISTS(SELECT 1 FROM staff s LEFT JOIN crew_map c ON c.ref=s.ref AND c.version='1.1'
                LEFT JOIN person p ON p.id=c.pid WHERE s.mid=m.id AND p.id IS NULL)
            ORDER BY m.id''').fetchall()
        self.assertEqual(self.answer('C11')['missionIds'], [r[0] for r in rows])

    def test_sql_distinct_people_and_staff_places(self):
        sql = '''SELECT COUNT(DISTINCT p.id) FROM staff s JOIN mission m ON m.id=s.mid
            JOIN crew_map c ON c.ref=s.ref AND c.version='1.3' JOIN person p ON p.id=c.pid'''
        for tid, where, field in [('E05', "m.officer='C-99'", 'distinctPeople'),
                                  ('E08', "m.classification='SECRET'", 'distinctPeople'),
                                  ('V05', '1=1', 'distinctPeople'),
                                  ('V08', "m.authority='STARFLEET_SECURITY'", 'distinctPeople')]:
            actual = self.db.execute(sql + ' WHERE ' + where).fetchone()[0]
            self.assertEqual(self.answer(tid)[field], actual)
        places = self.db.execute('''SELECT COUNT(*) FROM
            (SELECT DISTINCT s.mid,s.ref FROM staff s JOIN mission m ON m.id=s.mid
             WHERE m.authority='STARFLEET_SECURITY')''').fetchone()[0]
        self.assertEqual(places, 177)
        self.assertEqual(self.answer('V08')['staffPlaces'], places)
        raw_places = self.db.execute("SELECT COUNT(*) FROM staff s JOIN mission m ON m.id=s.mid WHERE m.authority='STARFLEET_SECURITY'").fetchone()[0]
        self.assertEqual(raw_places, 178)  # Commander/assigned overlap must count once.
        rows = self.db.execute('''SELECT COALESCE(p.rank,'CIVILIAN'), COUNT(*) FROM person p
            WHERE EXISTS(SELECT 1 FROM staff s JOIN crew_map c ON c.ref=s.ref AND c.version='1.3'
            WHERE c.pid=p.id) GROUP BY COALESCE(p.rank,'CIVILIAN') ORDER BY 1''').fetchall()
        self.assertEqual(self.answer('V05')['ranks'], [{'rank': r, 'count': n} for r, n in rows])

    def test_sql_distinct_asset_counts_and_zero_type_variant(self):
        rows = self.db.execute('''SELECT a.id, COUNT(DISTINCT u.mid) FROM use_asset u
            JOIN asset_map am ON am.ref=u.ref JOIN asset a ON a.id=am.aid
            GROUP BY a.id ORDER BY a.id''').fetchall()
        self.assertEqual(self.answer('E15')['assets'], [{'assetId': a, 'missionCount': n} for a, n in rows])
        rows = self.db.execute('''SELECT m.kind, COUNT(DISTINCT m.id) FROM mission m
            JOIN use_asset u ON u.mid=m.id JOIN asset_map am ON am.ref=u.ref
            JOIN asset a ON a.id=am.aid WHERE a.status!='ACTIVE'
            GROUP BY m.kind ORDER BY m.kind''').fetchall()
        self.assertEqual(self.answer('V06')['types'], [{'type': kind, 'missionCount': n} for kind, n in rows])
        alternate = self.keys['V06']['variants'][0]['answer']['types']
        self.assertEqual({r['type'] for r in alternate}, {m['type'] for m in self.data.missions.values()})
        self.assertEqual([r for r in alternate if r['missionCount']], self.answer('V06')['types'])

    def test_money_integer_cents_and_missing_costs(self):
        for tid, where, column, field in [
            ('E02', "officer='C-92'", 'estimate', 'totalEstimatedCost'),
            ('E11', "status='COMPLETED' AND authority='ENTERPRISE_COMMAND'", 'actual', 'totalActualCost'),
            ('V07', "kind='TRANSPORT'", 'estimate', 'totalEstimatedCost')]:
            count, cents = self.db.execute('SELECT COUNT(*), SUM(' + column + ') FROM mission WHERE ' + where).fetchone()
            answer = self.answer(tid)
            self.assertEqual(answer['missionCount'], count)
            self.assertEqual(Decimal(str(answer[field])) * 100, cents)
        rows = self.db.execute('SELECT authority, COUNT(*), SUM(estimate) FROM mission GROUP BY authority ORDER BY authority').fetchall()
        for answer, (authority, count, cents) in zip(self.answer('E12')['authorities'], rows):
            self.assertEqual(answer['issuingAuthority'], authority)
            self.assertEqual(answer['missionCount'], count)
            self.assertEqual(Decimal(str(answer['totalEstimatedCost'])) * 100, cents)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM mission WHERE estimate IS NULL').fetchone()[0], 33)
        self.assertEqual(b.total([{'cost': '0.10'}, {'cost': '0.20'}, {}], 'cost'), 0.3)
        self.assertEqual(b.total([{}, {}], 'cost'), 0.0)
        rows = self.db.execute('SELECT id FROM mission WHERE actual>estimate ORDER BY id').fetchall()
        self.assertEqual(self.answer('G10')['missionIds'], [r[0] for r in rows])

    def test_mission_xml_agrees_with_json_inputs(self):
        ns = {'m': 'urn:starfleet:missions:v1'}
        ids = []
        for page in range(1, 7):
            tree = ET.fromstring(self.contents[b.MISSIONS + 'missions-%d.xml' % page])
            self.assertEqual(int(tree.findtext('m:page', namespaces=ns)), page)
            for node in tree.findall('m:mission', ns):
                mid = node.findtext('m:missionId', namespaces=ns)
                ids.append(mid)
                record = self.data.missions[mid]
                for field in ('title', 'type', 'classification', 'status', 'issuingAuthority',
                              'commandingOfficerId', 'stardate', 'estimatedCostCredits', 'actualCostCredits'):
                    self.assertEqual(node.findtext('m:' + field, namespaces=ns), record.get(field))
                for field, child in [('assignedCrewIds', 'crewId'), ('assignedAssetIds', 'assetId'), ('participantIds', 'participantId')]:
                    values = [e.text for e in node.findall('m:' + field + '/m:' + child, ns)]
                    self.assertEqual(values, record[field])
        self.assertEqual(len(ids), 300)
        self.assertEqual(set(ids), set(self.data.missions))

    def test_outage_answers_do_not_leak_unavailable_attributes(self):
        for tid in ('D01', 'D02', 'D05', 'D06', 'D10', 'D11'):
            answer = self.answer(tid)
            self.assertFalse(answer['complete'])
            for field, value in answer.items():
                if field not in ('answerStatus', 'complete', 'unavailableServices'):
                    self.assertIn(value, (None, []))
        for tid in ('D03', 'D08', 'D13', 'D14'):
            self.assertTrue(self.answer(tid)['complete'])
            self.assertEqual(self.answer(tid)['unavailableServices'], [])
        for tid in ('D04', 'V04'):
            self.assertTrue(all(row['status'] is None for row in self.answer(tid)['assets']))
        self.assertTrue(all(row['name'] is None and row['rank'] is None for row in self.answer('D09')['people']))
        self.assertTrue(all(row['rank'] is None for row in self.answer('D12')['missions']))
        self.assertTrue(all(row['assetNames'] == [] for row in self.answer('D07')['missions']))
        self.assertIn('AST-0097', [r['assetId'] for r in self.answer('D04')['assets']])

    def test_outage_subset_variants_are_exact_and_honest(self):
        for tid, field in [('D04', 'assets'), ('D09', 'people'), ('V04', 'assets')]:
            primary = self.answer(tid)
            variants = self.keys[tid]['variants']
            self.assertEqual(len(variants), 2 ** len(primary[field]) - 1)
            for variant in variants:
                answer = variant['answer']
                self.assertEqual({k: v for k, v in answer.items() if k != field},
                                 {k: v for k, v in primary.items() if k != field})
                self.assertTrue(all(row in primary[field] for row in answer[field]))
                self.assertLess(len(answer[field]), len(primary[field]))

    def test_asset_hierarchy_and_closed_ambiguity_values(self):
        interpretations = self.keys['F03']['interpretations']
        direct = set(interpretations['directly-aboard']['answer']['assetIds'])
        recursive = set(interpretations['at-any-level']['answer']['assetIds'])
        self.assertEqual(len(direct), 11)
        self.assertLess(direct, recursive)
        self.assertNotIn('AST-0029', recursive)
        self.assertIn('AST-0009', recursive - direct)
        f01 = self.keys['F01']['interpretations']
        self.assertEqual([f01[n]['answer']['peopleCount'] for n in ['staff', 'staff-and-participants', 'assigned-crew-only']], [4, 7, 3])
        for name, value in self.keys['F06']['interpretations'].items():
            answer = value['answer']
            definition = answer['interpretation']
            candidates = []
            for m in self.data.missions.values():
                if definition['completedOnly'] and m['status'] != 'COMPLETED':
                    continue
                in_role = m.get('commandingOfficerId') == 'C-554'
                if 'ASSIGNED_CREW' in definition['roles']:
                    in_role = in_role or 'C-554' in m['assignedCrewIds']
                if in_role:
                    candidates.append((Decimal(m['stardate']), m['missionId']))
            self.assertEqual(answer['missionId'], max(candidates)[1], name)

    def test_assumptions_and_gaps_reference_real_tasks(self):
        for assumption in self.document['assumptions']:
            self.assertTrue(assumption['text'])
            self.assertTrue(assumption['taskIds'])
            self.assertLessEqual(set(assumption['taskIds']), set(self.keys))
        for gap in self.document['gaps']:
            self.assertIn(gap['taskId'], self.keys)
            self.assertTrue(gap['text'])
        covered = {tid for a in self.document['assumptions'] for tid in a['taskIds']}
        self.assertLessEqual({tid for tid, t in self.data.tasks.items() if 'stoppedService' in t}, covered)


if __name__ == '__main__':
    unittest.main()
