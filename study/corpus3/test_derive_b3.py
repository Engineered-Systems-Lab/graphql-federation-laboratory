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

import derive_b3 as b


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
        cls.document = json.loads(b.OUTPUT.read_bytes())
        cls.keys = cls.document['keys']
        cls.data = b.Data(cls.contents)
        cls.db = sqlite3.connect(':memory:')
        cls.db.row_factory = sqlite3.Row
        cls.db.executescript('''
            CREATE TABLE mission(id TEXT PRIMARY KEY, type TEXT, status TEXT, officer TEXT, cents INTEGER);
            CREATE TABLE crew(mid TEXT, ref TEXT, role TEXT);
            CREATE TABLE equipment(mid TEXT, ref TEXT);
            CREATE TABLE cmap(version TEXT, ref TEXT, pid TEXT);
            CREATE TABLE amap(version TEXT, ref TEXT, aid TEXT);
            CREATE TABLE person(id TEXT PRIMARY KEY, title TEXT, department TEXT, rank TEXT, duty TEXT, supervisor TEXT);
            CREATE TABLE asset(id TEXT PRIMARY KEY, name TEXT, kind TEXT, status TEXT, parent TEXT);
        ''')
        # Parse raw releases separately from Data. SQL joins supply the independent
        # relational oracle; monetary inputs are converted to integer cents.
        missions = json.loads(cls.contents[b.MISSIONS + 'release.json'])['missions']
        for m in missions:
            cost = m.get('estimatedCostCredits')
            cents = None if cost is None else int(cost.replace('.', ''))
            cls.db.execute('INSERT INTO mission VALUES(?,?,?,?,?)',
                           (m['missionId'], m['type'], m['status'], m.get('commandingOfficerId'), cents))
            cls.db.executemany('INSERT INTO crew VALUES(?,?,?)',
                               [(m['missionId'], ref, 'ASSIGNED_CREW') for ref in m['assignedCrewIds']])
            if m.get('commandingOfficerId'):
                cls.db.execute('INSERT INTO crew VALUES(?,?,?)', (m['missionId'], m.get('commandingOfficerId'), 'COMMANDING_OFFICER'))
            cls.db.executemany('INSERT INTO equipment VALUES(?,?)', [(m['missionId'], ref) for ref in m['assignedAssetIds']])
        for version in ('1.0', '1.1', '1.2', '1.3'):
            for filename, table in [('crew', 'cmap'), ('assets', 'amap')]:
                path = 'federation/mapping-releases/' + version + '/' + filename + '.json'
                if path in cls.contents:
                    entries = json.loads(cls.contents[path])['entries']
                    cls.db.executemany('INSERT INTO ' + table + ' VALUES(?,?,?)',
                                       [(version, ref, target) for ref, target in entries.items()])
        cls.page_ids = []
        ns = {'p': 'urn:graphql-federation-lab:personnel:v2'}
        for path in sorted(cls.contents):
            if path.startswith(b.PERSONNEL + 'page-'):
                page_ids = []
                for member in ET.fromstring(cls.contents[path]).findall('p:personnelMember', ns):
                    def value(field):
                        return member.findtext('.//p:' + field, namespaces=ns)
                    civilian = member.find('p:civilianDetails', ns) is not None
                    pid = value('personnelId')
                    page_ids.append(pid)
                    cls.db.execute('INSERT INTO person VALUES(?,?,?,?,?,?)',
                                   (pid, value('positionTitle'), 'CIVILIAN' if civilian else value('department'),
                                    'CIVILIAN' if civilian else value('rank'), value('dutyStatus'), value('supervisorPersonnelId')))
                cls.page_ids.append(page_ids)
        for a in json.loads(cls.contents[b.ASSETS + 'assets.json'])['assets']:
            cls.db.execute('INSERT INTO asset VALUES(?,?,?,?,?)',
                           tuple(a[f] for f in ('assetId', 'name', 'kind', 'status', 'parentAssetId')))
        cls.db.executescript('''
            CREATE VIEW people_on AS SELECT DISTINCT c.mid, p.*, c.role FROM crew c
                JOIN cmap x ON x.ref=c.ref AND x.version='1.3' JOIN person p ON p.id=x.pid;
            CREATE VIEW assets_on AS SELECT DISTINCT e.mid, a.* FROM equipment e
                JOIN amap x ON x.ref=e.ref AND x.version='1.3' JOIN asset a ON a.id=x.aid;
        ''')

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def rows(self, sql, args=()):
        return [dict(r) for r in self.db.execute(sql, args)]

    def ids(self, sql, args=()):
        return [r[0] for r in self.db.execute(sql, args)]

    def answer(self, tid):
        return self.keys[tid]['answer']

    def test_integrity_and_input_inventory(self):
        manifest = json.loads((b.ROOT / 'MANIFEST.json').read_bytes())
        digest = manifest.pop('packageSha256')
        self.assertEqual(digest, hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
        for entry in manifest['files']:
            raw = (b.ROOT / entry['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['sha256'])
            self.assertEqual(len(raw), entry['size'])
        self.assertEqual(self.document['inputs'], self.inputs)
        self.assertEqual(self.document['packageSha256'], digest)
        self.assertEqual(self.document['labCommit'], manifest['labCommit'])

    def test_coverage_and_schemas(self):
        tasks = json.loads(self.contents['study/corpus3/tasks.json'])['tasks']
        schemas = json.loads(self.contents['study/corpus3/schemas.json'])['schemas']
        self.assertEqual(len(tasks), 31)
        self.assertEqual(len(self.keys), 31)
        self.assertEqual(set(self.keys), {t['id'] for t in tasks})
        for t in tasks:
            key = self.keys[t['id']]
            self.assertEqual(key['taskId'], t['id'])
            self.assertEqual(key['set'], t['set'])
            validate(key['answer'], schemas[t['id']])
            for variant in key['variants']:
                validate(variant['answer'], schemas[t['id']])
                self.assertTrue(variant['reason'])
            self.assertTrue(key['basis'])

    def test_recompute_and_deterministic_bytes(self):
        run = subprocess.run([sys.executable, '-B', str(b.ROOT / 'study/corpus3/derive_b3.py')], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('No difference', run.stdout)
        first, second = b.encode(b.derive()), b.encode(b.derive())
        self.assertEqual(first, second)
        self.assertEqual(first, b.OUTPUT.read_bytes())
        self.assertTrue(first.endswith(b'\n'))
        # Separate interpreter invocations with unrelated hash seeds exercise set order.
        import os
        command = [sys.executable, '-B', '-c', 'import derive_b3 as b; import sys; sys.stdout.buffer.write(b.encode(b.derive()))']
        for seed in ('2', '91'):
            raw = subprocess.check_output(command, cwd=b.OUTPUT.parent, env={**os.environ, 'PYTHONHASHSEED': seed})
            self.assertEqual(raw, first)

    def test_comparison_failure(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / 'keys.json'
            output.write_text('{}\n')
            with patch.object(b, 'OUTPUT', output), redirect_stderr(io.StringIO()):
                self.assertEqual(b.main([]), 1)
            with patch.object(b, 'OUTPUT', output), redirect_stdout(io.StringIO()):
                self.assertEqual(b.main(['--write']), 0)
            self.assertEqual(output.read_bytes(), b.OUTPUT.read_bytes())

    def test_all_personnel_pages(self):
        self.assertEqual([len(page) for page in self.page_ids], [100] * 10)
        self.assertEqual(self.data.page_counts, [100] * 10)
        self.assertEqual(set(self.data.people), {pid for page in self.page_ids for pid in page})
        self.assertEqual(len(self.data.people), 1000)
        self.assertEqual(self.ids('SELECT id FROM person ORDER BY id'), sorted(self.data.people))

    def test_reverse_person_queries(self):
        self.assertEqual(self.answer('B16')['missions'], self.rows('''SELECT mid AS missionId,
            CASE WHEN MAX(role='COMMANDING_OFFICER') THEN 'COMMANDING_OFFICER' ELSE 'ASSIGNED_CREW' END AS role
            FROM people_on WHERE title='Flight Operations Lead' GROUP BY mid ORDER BY mid'''))
        self.assertEqual(self.answer('B17')['missions'], self.rows('''SELECT DISTINCT mid AS missionId, m.type
            FROM people_on p JOIN mission m ON m.id=p.mid
            WHERE title='Transporter Chief' AND role='ASSIGNED_CREW' ORDER BY mid'''))
        self.assertEqual(self.ids("SELECT mid FROM people_on WHERE title='Transporter Chief' AND role='COMMANDING_OFFICER'"), [])
        self.assertEqual(self.answer('B19')['missions'], self.rows('''SELECT DISTINCT mid AS missionId, m.status
            FROM people_on p JOIN mission m ON m.id=p.mid WHERE title='Chief of Security' ORDER BY mid'''))
        for tid, where in [('B18', "title='Chief Medical Officer' AND role='COMMANDING_OFFICER'"),
                           ('B21', "title='Section Supervisor'"),
                           ('B22', "department='COMMAND' AND role='COMMANDING_OFFICER'"),
                           ('B23', "supervisor=(SELECT id FROM person WHERE title='Chief Medical Officer') AND title!='Chief Medical Officer'")]:
            self.assertEqual(self.answer(tid)['missionIds'], self.ids('SELECT DISTINCT mid FROM people_on WHERE ' + where + ' ORDER BY mid'))
        members = []
        for pid in self.ids("SELECT DISTINCT id FROM people_on WHERE duty='ON_LEAVE' ORDER BY id"):
            members.append({'personnelId': pid, 'missionIds': self.ids('SELECT DISTINCT mid FROM people_on WHERE id=? ORDER BY mid', (pid,))})
        self.assertEqual(self.answer('B20')['members'], members)

    def test_mapping_release_boundaries(self):
        for tid, title in [('C13', 'Acting Ensign'), ('C14', 'Engineering Officer')]:
            self.assertEqual(self.answer(tid)['missionIds'], self.ids('''SELECT DISTINCT c.mid FROM crew c
                JOIN cmap x ON x.ref=c.ref AND x.version='1.1' JOIN person p ON p.id=x.pid
                WHERE p.title=? ORDER BY c.mid''', (title,)))
        self.assertEqual(self.answer('C14')['missionIds'], [])
        self.assertTrue(self.ids("SELECT mid FROM people_on WHERE title='Engineering Officer'"))
        self.assertEqual(self.answer('C16')['missionIds'], self.ids('''SELECT DISTINCT mid FROM equipment e
            JOIN amap x ON x.ref=e.ref AND x.version='1.0' WHERE aid='AST-0024' ORDER BY mid'''))

    def test_reverse_asset_queries(self):
        for tid, where in [('B24', "name='Away-team communications kit'"), ('B25', "kind='SHUTTLE'"),
                           ('B26', "parent='AST-0029'"), ('B27', "status='MISSING'"),
                           ('B29', "parent=(SELECT id FROM asset WHERE name='Shuttlecraft Magellan')"),
                           ('C15', "kind='ROVER'")]:
            self.assertEqual(self.answer(tid)['missionIds'], self.ids('SELECT DISTINCT mid FROM assets_on WHERE ' + where + ' ORDER BY mid'))
        self.assertEqual(self.answer('B28')['missionIds'], self.ids("SELECT mid FROM assets_on WHERE id IN ('AST-0005','AST-0007') GROUP BY mid HAVING COUNT(DISTINCT id)=2 ORDER BY mid"))
        self.assertEqual(self.answer('C15')['missionIds'], [])
        self.assertTrue(self.ids("SELECT id FROM asset WHERE kind='ROVER'"))
        self.assertNotEqual(set(self.answer('B26')['missionIds']), set(self.answer('B29')['missionIds']))

    def test_asset_aggregates_and_money(self):
        self.assertEqual(self.answer('E17')['shuttles'], self.rows('''SELECT a.id AS assetId, COUNT(DISTINCT o.mid) AS missionCount
            FROM asset a LEFT JOIN assets_on o ON o.id=a.id WHERE a.kind='SHUTTLE' GROUP BY a.id ORDER BY a.id'''))
        for tid, field, output in [('E18', 'kind', 'kinds'), ('E19', 'status', 'statuses')]:
            self.assertEqual(self.answer(tid)[output], self.rows('SELECT ' + field + ', COUNT(DISTINCT mid) AS missionCount FROM assets_on GROUP BY ' + field + ' ORDER BY ' + field))
        count, cents = self.db.execute("SELECT COUNT(*), SUM(cents) FROM mission WHERE id IN (SELECT mid FROM assets_on WHERE id='AST-0004')").fetchone()
        self.assertEqual(self.answer('E20')['missionCount'], count)
        self.assertEqual(Decimal(str(self.answer('E20')['totalEstimatedCost'])), Decimal(cents) / 100)
        self.assertEqual(b.total([{'cost': '0.10'}, {'cost': '0.20'}, {'cost': None}], 'cost'), 0.3)
        self.assertEqual(b.total([], 'cost'), 0.0)

    def test_person_aggregates(self):
        self.assertEqual(self.answer('E21')['members'], self.rows("SELECT id AS personnelId, COUNT(DISTINCT mid) AS missionCount FROM people_on WHERE department='COMMAND' AND role='COMMANDING_OFFICER' GROUP BY id ORDER BY id"))
        self.assertEqual(self.answer('E22')['statuses'], self.rows("SELECT m.status, COUNT(DISTINCT m.id) AS count FROM mission m JOIN people_on p ON p.mid=m.id WHERE p.id='PRS-2018' GROUP BY m.status ORDER BY m.status"))
        departments = self.rows('''SELECT department, COUNT(*) AS count FROM person WHERE id NOT IN
            (SELECT id FROM people_on) GROUP BY department ORDER BY department''')
        self.assertEqual(self.answer('E23')['departments'], departments)
        self.assertEqual(self.answer('E23')['memberCount'], sum(r['count'] for r in departments))
        self.assertEqual(self.answer('E24')['members'], self.rows('''SELECT p.id AS personnelId, COUNT(DISTINCT o.mid) AS missionCount
            FROM person p LEFT JOIN people_on o ON o.id=p.id WHERE p.title='Section Supervisor' GROUP BY p.id ORDER BY p.id'''))
        self.assertEqual(self.answer('E25')['departments'], self.rows('SELECT department, COUNT(DISTINCT mid) AS missionCount FROM people_on GROUP BY department ORDER BY department'))

    def test_three_system_joins(self):
        rows = []
        for m in self.db.execute("SELECT id FROM mission WHERE type='RESCUE' ORDER BY id"):
            pid = self.db.execute('''SELECT NULLIF(p.department,'CIVILIAN') FROM mission m
                LEFT JOIN cmap x ON x.ref=m.officer AND x.version='1.3' LEFT JOIN person p ON p.id=x.pid WHERE m.id=?''', (m['id'],)).fetchone()[0]
            rows.append({'missionId': m['id'], 'commandingOfficerDepartment': pid,
                         'assetIds': self.ids('SELECT id FROM assets_on WHERE mid=? ORDER BY id', (m['id'],))})
        self.assertEqual(self.answer('B31')['missions'], rows)
        anchor = next(r for r in rows if r['missionId'] == 'ST-00000LD4T')
        self.assertEqual(self.answer('B30')['commandingOfficerDepartment'], anchor['commandingOfficerDepartment'])
        self.assertEqual(self.answer('B30')['assets'], self.rows("SELECT id AS assetId, kind FROM assets_on WHERE mid='ST-00000LD4T' ORDER BY id"))
        for tid, kind in [('E26', 'EXPLORATION'), ('E27', 'FIRST_CONTACT')]:
            self.assertEqual(self.answer(tid)['assetIds'], self.ids('SELECT DISTINCT a.id FROM assets_on a JOIN mission m ON m.id=a.mid WHERE m.type=? ORDER BY a.id', (kind,)))
            if tid == 'E26':
                count = self.db.execute('SELECT COUNT(DISTINCT p.id) FROM people_on p JOIN mission m ON m.id=p.mid WHERE m.type=?', (kind,)).fetchone()[0]
                self.assertEqual(self.answer(tid)['distinctPeople'], count)
            else:
                self.assertEqual(self.answer(tid)['ranks'], self.rows('SELECT rank, COUNT(DISTINCT p.id) AS count FROM people_on p JOIN mission m ON m.id=p.mid WHERE m.type=? GROUP BY rank ORDER BY rank', (kind,)))


if __name__ == '__main__':
    unittest.main()
