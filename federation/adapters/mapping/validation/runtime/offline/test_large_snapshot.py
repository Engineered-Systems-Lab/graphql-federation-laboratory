"""The batch of the crew mapping process that builds the large Personnel v2 snapshot, with no Docker.

The acceptance tests come first and re-derive the rules by hand from the released files (the v1 release crew-v1-large-003 and the
Personnel v2 snapshot personnel-v2-small-003), not by calling the process: every one of the 800 people of the v1 release must stand in
personnel-v2-large-004 as the process rules say, and the package must be reproducible (the same inputs give the same bytes). The
controlled cases (two matches, a taken identifier) run on small inputs built here.
"""
from pathlib import Path
import importlib.util
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_support as support  # noqa: E402

ROOT = support.ROOT
MODULE = ROOT / 'federation/personnel-mapping/crew_mapping.py'
V1 = ROOT / 'uss-enterprise/crew-personnel/datasets/released/crew-v1-large-003'
SMALL_003 = ROOT / 'uss-enterprise/personnel-v2/datasets/personnel-v2-small-003.xml'
LARGE = ROOT / 'uss-enterprise/personnel-v2/datasets/personnel-v2-large-004'

spec = importlib.util.spec_from_file_location('crew_mapping', MODULE)
cm = importlib.util.module_from_spec(spec)
sys.modules['crew_mapping'] = cm
spec.loader.exec_module(cm)

V1NS = '{urn:graphql-federation-lab:crew-personnel:v1}'
V2NS = '{urn:graphql-federation-lab:personnel:v2}'
MEMBER_LINE = re.compile(r'  <personnelMember><personnelId>(PRS-[0-9]{4})</personnelId>.*</personnelMember>')


def v1_people():
    people = {}
    for page in sorted(V1.glob('page-*.xml')):
        for node in ET.parse(page).getroot().findall(V1NS + 'crewMember'):
            fields = {child.tag.replace(V1NS, ''): child.text for child in node}
            people[fields['crewId']] = fields
    return people


def v2_lines(path):
    """personnelId to the exact line of the file, for a file of one member per line."""
    return {m.group(1): m.group(0) for m in (MEMBER_LINE.match(line) for line in path.read_text(encoding='utf-8').split('\n')) if m}


def v2_people(lines):
    """personnelId to a dict of the fields of the member line (rank, department, clearance and supervisor None for a civilian)."""
    people = {}
    for ident, line in lines.items():
        node = ET.fromstring(line.replace('<personnelMember>', '<personnelMember xmlns="urn:graphql-federation-lab:personnel:v2">', 1))
        crew = node.find(V2NS + 'crewDetails')
        get = lambda name: None if crew is None else crew.findtext(V2NS + name)  # noqa: E731
        people[ident] = dict(name=node.findtext(V2NS + 'displayName'), title=node.findtext(V2NS + 'positionTitle'),
                             duty=node.findtext(V2NS + 'dutyStatus'), civilian=node.find(V2NS + 'civilianDetails') is not None,
                             rank=get('rank'), department=get('department'), clearance=get('securityClearance'),
                             supervisor=get('supervisorPersonnelId'))
    return people


def large_lines():
    lines = {}
    for page in sorted(LARGE.glob('page-*.xml')):
        lines.update(v2_lines(page))
    return lines


def clearance_by_rank(rank, department):
    value = {'CAPTAIN': 'TOP_SECRET', 'COMMANDER': 'SECRET', 'LIEUTENANT_COMMANDER': 'SECRET'}.get(rank, 'NONE')
    return 'SECRET' if department == 'SECURITY' and value == 'NONE' else value


class TheLargeSnapshotFollowsTheProcessRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1 = v1_people()
        cls.small_lines = v2_lines(SMALL_003)
        cls.small = v2_people(cls.small_lines)
        cls.lines = large_lines()
        cls.large = v2_people(cls.lines)

    def expected_id(self, v1_id):
        """Step 2: an exact name in the source snapshot keeps the v2 id; step 3: otherwise the number of the v1 id is kept."""
        name = self.v1[v1_id]['displayName']
        hits = [ident for ident, person in self.small.items() if person['name'] == name]
        self.assertLessEqual(len(hits), 1, name)
        return hits[0] if hits else 'PRS-' + v1_id[4:]

    def test_the_package_has_a_thousand_people_in_ten_pages_and_the_inputs_are_the_pinned_ones(self):
        self.assertEqual(800, len(self.v1))
        self.assertEqual(1000, len(self.large))
        self.assertEqual(14, len(self.small))
        self.assertEqual(['manifest.json'] + ['page-%03d.xml' % i for i in range(10)], sorted(p.name for p in LARGE.iterdir()))
        self.assertEqual([], cm.check_pins(ROOT, cm.LARGE_PINS))

    def test_the_fourteen_people_of_the_source_snapshot_are_kept_byte_for_byte(self):
        for ident, line in self.small_lines.items():
            self.assertEqual(line, self.lines[ident], ident)

    def test_every_person_of_the_v1_release_stands_as_the_process_says(self):
        kept = migrated = 0
        for v1_id, person in sorted(self.v1.items()):
            ident = self.expected_id(v1_id)
            self.assertIn(ident, self.large, v1_id)
            if ident in self.small:
                kept += 1
                self.assertEqual(self.small_lines[ident], self.lines[ident])  # the v2 record stands
                continue
            migrated += 1
            self.assertEqual('PRS-' + v1_id[4:], ident)
            record = self.large[ident]
            self.assertEqual((person['displayName'], person['positionTitle'], person['dutyStatus']),
                             (record['name'], record['title'], record['duty']), v1_id)
            if person['rank'] == 'CIVILIAN':
                self.assertTrue(record['civilian'], v1_id)  # a civilian record holds no rank, department, clearance or supervisor
                continue
            self.assertFalse(record['civilian'], v1_id)
            self.assertEqual((person['rank'], person['department']), (record['rank'], record['department']), v1_id)
            self.assertEqual(clearance_by_rank(person['rank'], person['department']), record['clearance'], v1_id)
            supervisor = person.get('supervisorCrewId')
            self.assertEqual(None if supervisor is None else self.expected_id(supervisor), record['supervisor'], v1_id)
        self.assertEqual((13, 787), (kept, migrated))

    def test_the_civilians_are_the_range_after_the_migrated_numbers(self):
        v1_numbers = {int(v1_id[4:]) for v1_id in self.v1}
        added = sorted(ident for ident in self.large if ident not in self.small and ('CRW-' + ident[4:]) not in self.v1)
        self.assertEqual(['PRS-%04d' % n for n in range(3001, 3200)], added)
        self.assertGreater(3001, max(v1_numbers))
        for ident in added:
            self.assertTrue(self.large[ident]['civilian'], ident)
        v1_names = {person['displayName'] for person in self.v1.values()}
        names = [person['name'] for person in self.large.values()]
        self.assertEqual(len(names), len(set(names)))  # one name, one person: the exact-name rule never has two matches
        self.assertFalse(v1_names & {self.large[ident]['name'] for ident in added})

    def test_the_paging_fields_of_every_page_are_exact(self):
        for index in range(10):
            text = (LARGE / ('page-%03d.xml' % index)).read_text(encoding='utf-8')
            self.assertIn('<totalCount>1000</totalCount><offset>%d</offset><limit>100</limit><hasMore>%s</hasMore>'
                          % (index * 100, 'true' if index < 9 else 'false'), text)
            self.assertEqual(100, sum(1 for line in text.split('\n') if MEMBER_LINE.match(line)))

    def test_the_batch_reproduces_the_package_byte_for_byte_and_twice(self):
        self.assertEqual([], cm.compare_large(ROOT))
        first, second = cm.large_files(ROOT), cm.large_files(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(sorted(first), sorted(p.name for p in LARGE.iterdir()))
        for name, data in first.items():
            self.assertEqual((LARGE / name).read_bytes(), data, name)
        self.assertNotIn(b'\r', b''.join(first.values()))


class TheBatchRefusesWhatTheProcessRefuses(unittest.TestCase):
    @staticmethod
    def person(name, rank='ENSIGN', department='OPERATIONS', supervisor=None):
        return dict(displayName=name, positionTitle='Officer', dutyStatus='ACTIVE', rank=rank, department=department, supervisor=supervisor)

    @staticmethod
    def v2(**people):
        return {ident.replace('_', '-'): dict(displayName=name, positionTitle='Officer', dutyStatus='ACTIVE', rank=None, department=None,
                                              securityClearance=None, supervisor=None) for ident, name in people.items()}

    def test_a_name_in_personnel_v2_keeps_the_v2_identifier_and_a_new_name_keeps_the_v1_number(self):
        results = cm.map_people({'CRW-1500': self.person('Ada Lovelace'), 'CRW-1501': self.person('New Person')}, self.v2(PRS_0009='Ada Lovelace'))
        self.assertEqual([('NAME', 'PRS-0009'), ('MIGRATE', 'PRS-1501')], [(r.outcome, r.target or r.migrated_id) for r in results])

    def test_two_people_with_one_name_in_the_v1_release_are_a_failure(self):
        with self.assertRaises(cm.MappingFailure) as caught:
            cm.map_people({'CRW-1500': self.person('Twin'), 'CRW-1501': self.person('Twin')}, self.v2(PRS_0009='Someone'))
        self.assertEqual(['CRW-1500', 'CRW-1501'], caught.exception.matches)

    def test_two_people_with_one_name_in_personnel_v2_are_a_failure(self):
        with self.assertRaises(cm.MappingFailure) as caught:
            cm.map_people({'CRW-1500': self.person('Twin')}, self.v2(PRS_0009='Twin', PRS_0010='Twin'))
        self.assertEqual(['PRS-0009', 'PRS-0010'], caught.exception.matches)

    def test_a_migrated_number_that_personnel_v2_holds_is_a_failure(self):
        with self.assertRaises(cm.MappingFailure):
            cm.map_people({'CRW-1500': self.person('Newcomer')}, self.v2(PRS_1500='Someone Else'))

    def test_a_run_refuses_to_start_when_an_input_differs_from_its_pin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'federation/personnel-mapping').mkdir(parents=True)
            (root / cm.LARGE_PINS).write_bytes((ROOT / cm.LARGE_PINS).read_bytes())
            with self.assertRaises(cm.MappingFailure) as caught:
                cm.load_large_inputs(root)
            self.assertIn('refuses to start', str(caught.exception))

    def test_a_published_package_is_never_overwritten(self):
        self.assertEqual(1, cm.main(['large', '--write']))


class TheCivilians(unittest.TestCase):
    def test_the_same_people_come_out_every_time(self):
        module = cm.civilians_module()
        people = module.generate()
        self.assertEqual(people, module.generate())
        self.assertEqual(199, len(people))
        self.assertEqual(['PRS-%04d' % n for n in range(3001, 3200)], [p['personnelId'] for p in people])
        self.assertEqual(4, sum(1 for p in people if p['origin'] == 'canon-inspired'))
        self.assertTrue(all(p['dutyStatus'] in ('ACTIVE', 'ON_LEAVE', 'INACTIVE') for p in people))
        self.assertEqual(199, len({p['displayName'] for p in people}))
        for person in people:
            self.assertTrue(1 <= len(person['displayName']) <= 100 and 1 <= len(person['positionTitle']) <= 100)


if __name__ == '__main__':
    unittest.main()
