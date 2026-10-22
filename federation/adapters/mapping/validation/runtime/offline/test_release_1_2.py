"""Mapping release 1.2: Missions dataset release 1.1 against the large Personnel v2 snapshot, with no Docker.

The acceptance tests come first and are written by hand from the released files, not by calling the process: the recipe of Missions
dataset release 1.1 (references.crew, references.unmappedCrew and references.participants), the pages of personnel-v2-large-004 and
the legacy crew release crew-v1-large-003. Release 1.2 must hold exactly what that reading gives: the 800 crew references, the P
participants that the roster places, no entry at all for an O-reference (refused by class, the returning Wesley Crusher O-860 above
all) and no entry for the three unmapped crew. The controlled cases (a participant that only a crew member could match, two matches, an
exception that names an O-reference or a crew member, an O-reference with a roster name) run on small inputs built here.
"""
from pathlib import Path
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_support as support  # noqa: E402
import release_check as check  # noqa: E402

ROOT = support.ROOT
RELEASES = ROOT / check.RELEASES
RECIPE = ROOT / 'uss-enterprise/missions/datasets/releases/1.1/recipe.json'
LARGE = ROOT / 'uss-enterprise/personnel-v2/datasets/personnel-v2-large-004'
V2NS = '{urn:graphql-federation-lab:personnel:v2}'

spec = importlib.util.spec_from_file_location('crew_mapping', ROOT / 'federation/personnel-mapping/crew_mapping.py')
cm = importlib.util.module_from_spec(spec)
sys.modules['crew_mapping'] = cm
spec.loader.exec_module(cm)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def roster():
    """personnelId to (name, is crew) read from the ten pages of the large snapshot, with nothing of the process."""
    people = {}
    for page in sorted(LARGE.glob('page-*.xml')):
        for node in ET.parse(page).getroot().findall(V2NS + 'personnelMember'):
            people[node.findtext(V2NS + 'personnelId')] = (node.findtext(V2NS + 'displayName'), node.find(V2NS + 'crewDetails') is not None)
    return people


class TheReleaseHoldsWhatTheReleasedFilesSay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs = load(RECIPE)['references']
        cls.people = roster()
        cls.by_name = {}
        for ident, (name, crew) in cls.people.items():
            cls.by_name.setdefault(name, []).append(ident)
        cls.crew = load(RELEASES / '1.2/crew.json')
        cls.participants = load(RELEASES / '1.2/participants.json')

    def test_the_roster_has_a_thousand_unique_names(self):
        self.assertEqual(len(self.people), 1000)
        self.assertEqual(len(self.by_name), 1000)

    def test_every_one_of_the_800_crew_references_maps_to_the_crew_person_of_that_exact_name(self):
        self.assertEqual(len(self.refs['crew']), 800)
        self.assertEqual(len(self.crew['entries']), 800)
        for name, ref in self.refs['crew'].items():
            with self.subTest(ref=ref):
                self.assertEqual(self.by_name[name], [self.crew['entries'][ref]])
        self.assertEqual(len(set(self.crew['entries'].values())), 800, 'no two references share a person')
        civilians = sorted(t for t in self.crew['entries'].values() if not self.people[t][1])
        self.assertEqual(len(civilians), 20, 'the 19 migrated civilians of the legacy release and Guinan')
        self.assertIn('PRS-0003', civilians)

    def test_the_ten_cast_entries_of_release_1_1_stand_unchanged(self):
        old = load(RELEASES / '1.1/crew.json')['entries']
        self.assertEqual(len(old), 10)
        for ref, target in old.items():
            self.assertEqual(self.crew['entries'][ref], target, ref)
        self.assertEqual(self.crew['entries']['C-120'], 'PRS-0714', 'Wesley Crusher the crew member')

    def test_the_three_unmapped_crew_are_not_offered_and_have_no_entry(self):
        unmapped = self.refs['unmappedCrew']
        self.assertEqual(sorted(unmapped), ['Alyssa Ogawa', 'Hubbell', 'Ro Laren'])
        for name, ref in unmapped.items():
            self.assertNotIn(ref, self.crew['entries'], name)
            self.assertNotIn(name, self.by_name, name)
        self.assertEqual(self.crew['controlledCases']['UNMAPPED'], sorted(unmapped.values(), key=lambda r: int(r[2:])))

    def test_only_the_six_exceptions_of_the_table_are_exception_cases(self):
        self.assertEqual(self.crew['controlledCases']['EXCEPTION'], ['C-71', 'C-78', 'C-92', 'C-113', 'C-127', 'C-134'])
        self.assertEqual(len(self.crew['controlledCases']['NORMAL']), 794)

    def test_a_p_participant_maps_only_when_the_roster_places_it_as_a_non_crew_person(self):
        participants = self.refs['participants']
        p_refs = [ref for ref in participants if ref.startswith('P-')]
        self.assertEqual(len(p_refs), 118)
        expected = {'P-1068': 'PRS-0003', 'P-1003': 'PRS-3001'}  # Guinan by exact name; Alexander by the participant exception
        self.assertEqual(self.participants['entries'], expected)
        for ref, target in expected.items():
            self.assertFalse(self.people[target][1], ref + ' reaches a civilian, not a crew member')
        self.assertEqual(participants['P-1068'], 'Guinan')
        self.assertEqual(self.people['PRS-0003'][0], 'Guinan')
        self.assertEqual(self.people['PRS-3001'][0], 'Alexander Rozhenko')
        # a surname shared with the roster is no match: Sarek, Perrin and Lwaxana Troi stay unmapped
        for ref in ('P-393', 'P-406', 'P-704'):
            self.assertNotIn(ref, self.participants['entries'], participants[ref])
        self.assertEqual(sorted(self.participants['controlledCases']['UNMAPPED'] + ['P-1068', 'P-1003']), sorted(p_refs))

    def test_every_o_reference_is_refused_by_class_and_the_returning_wesley_never_reaches_a_person(self):
        o_refs = sorted(ref for ref in self.refs['participants'] if ref.startswith('O-'))
        self.assertEqual(len(o_refs), 28)
        self.assertEqual(sorted(self.participants['controlledCases']['REFUSED_BY_CLASS']), o_refs)
        for ref in o_refs:
            self.assertNotIn(ref, self.participants['entries'])
            self.assertNotIn(ref, self.crew['entries'])
        self.assertIn('Wesley Crusher', self.refs['participants']['O-860'])
        self.assertNotIn('O-860', self.participants['entries'])
        for section in (self.crew, self.participants):
            self.assertNotIn('PRS-0714', [t for r, t in section['entries'].items() if r != 'C-120'], 'only the crew reference C-120 reaches Wesley')

    def test_assets_json_is_release_1_1_unchanged_and_the_manifest_lists_three_files(self):
        self.assertEqual((RELEASES / '1.2/assets.json').read_bytes(), (RELEASES / '1.1/assets.json').read_bytes())
        manifest = load(RELEASES / '1.2/manifest.json')
        self.assertEqual(manifest['release'], '1.2')
        self.assertEqual(sorted(manifest['files']), ['assets.json', 'crew.json', 'participants.json'])
        self.assertEqual(check.check_files(RELEASES / '1.2'), [])
        self.assertEqual(check.check_assets_section(RELEASES / '1.2', ROOT), [])

    def test_the_checked_against_list_repeats_release_1_1_and_adds_missions_1_1_and_the_large_snapshot(self):
        manifest = load(RELEASES / '1.2/manifest.json')
        self.assertEqual(manifest['checkedAgainst'][:4], load(RELEASES / '1.1/manifest.json')['checkedAgainst'])
        self.assertEqual([(e['system'], e['artifact'], e['version']) for e in manifest['checkedAgainst'][4:]],
                         [('missions', 'dataset release manifest', '1.1'), ('personnel', 'dataset snapshot', 'personnel-v2-large-004')])
        self.assertEqual(manifest['checkedAgainst'][4]['sha256'], check.lf_sha256(ROOT / check.MISSIONS_DATASETS / '1.1/manifest.json'))
        self.assertEqual(manifest['checkedAgainst'][5]['sha256'], check.lf_sha256(LARGE / 'manifest.json'))
        self.assertEqual(check.check_against(RELEASES / '1.2', ROOT, newest=False), [])  # release 1.3 names Missions 1.2; this one stays true

    def test_the_release_is_what_the_process_builds_and_older_releases_stay_true(self):
        self.assertEqual(check.check_large_release(RELEASES / '1.2', ROOT), [])
        self.assertEqual(cm.check_large(ROOT), [])
        for version in ('1.0', '1.1'):
            self.assertEqual(check.check_against(RELEASES / version, ROOT, newest=False), [], version)

    def test_the_release_folder_is_lf_only(self):
        for path in (RELEASES / '1.2').iterdir():
            self.assertNotIn(b'\r', path.read_bytes(), path.name)


class TheProcessKeepsTheClasses(unittest.TestCase):
    """Controlled cases on inputs small enough to read."""

    def v2(self, *members):
        people = {}
        for ident, name, crew in members:
            people[ident] = {'displayName': name, 'positionTitle': 'T', 'dutyStatus': 'ACTIVE', 'rank': 'ENSIGN' if crew else None,
                             'department': 'OPERATIONS' if crew else None, 'securityClearance': 'NONE' if crew else None, 'supervisor': None}
        return people

    ROSTER = (('PRS-0001', 'Guinan', False), ('PRS-0002', 'Wesley Crusher', True), ('PRS-0003', 'Keiko', False))

    def test_an_o_reference_is_refused_whatever_its_name_even_one_that_is_on_the_roster(self):
        results = cm.map_participants({'O-1': 'Guinan', 'O-2': 'Wesley Crusher', 'O-3': 'nobody'}, {}, self.v2(*self.ROSTER))
        self.assertEqual([(r.ref, r.outcome, r.target) for r in results], [('O-1', 'REFUSED', None), ('O-2', 'REFUSED', None), ('O-3', 'REFUSED', None)])

    def test_the_crew_process_never_accepts_an_o_reference(self):
        with self.assertRaises(cm.MappingFailure) as caught:
            cm.map_references({'O-860': 'Wesley Crusher'}, {}, self.v2(*self.ROSTER))
        self.assertIn('refused by class', str(caught.exception))
        with self.assertRaises(cm.MappingFailure):
            cm.map_references({'C-1': 'Guinan', 'O-860': 'Wesley Crusher'}, {}, self.v2(*self.ROSTER), live=True)
        with self.assertRaises(cm.MappingFailure):
            cm.map_references({'P-1': 'Guinan'}, {}, self.v2(*self.ROSTER))

    def test_no_table_can_name_an_o_reference(self):
        with self.assertRaises(cm.MappingFailure) as caught:
            cm.map_participants({'O-1': 'Guinan'}, {'O-1': 'PRS-0001'}, self.v2(*self.ROSTER))
        self.assertIn('refused by class', str(caught.exception))
        with self.assertRaises(cm.MappingFailure):
            cm.map_references({'C-1': 'Guinan'}, {'O-1': 'PRS-0001'}, self.v2(*self.ROSTER))

    def test_a_p_participant_is_placed_by_the_exact_name_of_a_non_crew_person(self):
        results = cm.map_participants({'P-1': 'Guinan', 'P-2': 'guinan', 'P-3': 'Guin', 'P-4': 'Keiko O\'Brien'}, {}, self.v2(*self.ROSTER))
        self.assertEqual([(r.ref, r.outcome, r.target) for r in results],
                         [('P-1', 'NAME', 'PRS-0001'), ('P-2', 'UNMAPPED', None), ('P-3', 'UNMAPPED', None), ('P-4', 'UNMAPPED', None)])

    def test_a_participant_exception_wins_over_a_name_and_must_reach_a_non_crew_person_of_the_snapshot(self):
        result = cm.map_participants({'P-1': 'Guinan'}, {'P-1': 'PRS-0003'}, self.v2(*self.ROSTER))[0]
        self.assertEqual((result.outcome, result.target), ('EXCEPTION', 'PRS-0003'))
        for table, why in (({'P-1': 'PRS-0002'}, 'crew member'), ({'P-1': 'PRS-0099'}, 'not in the snapshot'),
                           ({'P-1': 'CRW-1047'}, 'grammar'), ({'P-9': 'PRS-0003'}, 'unknown reference'), ({'C-1': 'PRS-0003'}, 'wrong class')):
            with self.subTest(why=why), self.assertRaises(cm.MappingFailure):
                cm.map_participants({'P-1': 'Guinan'}, table, self.v2(*self.ROSTER))

    def test_a_participant_that_only_a_crew_member_matches_is_a_failure_not_a_pick(self):
        with self.assertRaises(cm.MappingFailure) as caught:
            cm.map_participants({'P-1': 'Wesley Crusher'}, {}, self.v2(*self.ROSTER))
        self.assertEqual(caught.exception.matches, ['PRS-0002'])

    def test_more_than_one_match_is_a_failure_that_reports_every_match(self):
        with self.assertRaises(cm.MappingFailure) as caught:
            cm.map_participants({'P-1': 'Keiko'}, {}, self.v2(*self.ROSTER, ('PRS-0004', 'Keiko', True)))
        self.assertEqual(caught.exception.matches, ['PRS-0003', 'PRS-0004'])

    def test_a_crew_reference_is_not_a_participant(self):
        with self.assertRaises(cm.MappingFailure):
            cm.map_participants({'C-1': 'Guinan'}, {}, self.v2(*self.ROSTER))
        with self.assertRaises(cm.MappingFailure):
            cm.map_participants({'X-1': 'Guinan'}, {}, self.v2(*self.ROSTER))

    def test_the_references_come_ordered_by_class_and_number(self):
        results = cm.map_participants({'O-5': 'a', 'P-30': 'b', 'P-4': 'c', 'O-12': 'd'}, {}, self.v2(*self.ROSTER))
        self.assertEqual([r.ref for r in results], ['O-5', 'O-12', 'P-4', 'P-30'])


class TheChecksCatchChanges(unittest.TestCase):
    """The release 1.2 checks on a copy of the files they stand on, in a temporary folder."""

    FILES = ('federation/personnel-mapping/crew_mapping.py', 'federation/personnel-mapping/release-large-pins.json',
             'federation/mapping-releases/1.1/manifest.json', 'federation/mapping-releases/1.1/assets.json',
             'uss-enterprise/missions/datasets/releases/1.1/manifest.json')

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='mapping-release-1-2-'))
        self.addCleanup(shutil.rmtree, self.temp, True)
        pins = load(ROOT / cm.RELEASE_PINS)
        names = list(self.FILES) + [entry['path'] for entry in pins.values() if isinstance(entry, dict) and 'path' in entry]
        for name in names:
            self.copy(name)
        for folder in (ROOT / pins['v1Release']['path']).parent, LARGE, RELEASES / '1.2':
            shutil.copytree(folder, self.temp / folder.relative_to(ROOT), dirs_exist_ok=True)
        self.release = self.temp / 'federation/mapping-releases/1.2'

    def copy(self, relative):
        target = self.temp / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)

    def test_the_copy_passes(self):
        self.assertEqual(check.check_large_release(self.release, self.temp), [])
        self.assertEqual(cm.check_large(self.temp), [])

    def test_a_changed_or_invented_entry_fails(self):
        for name, ref, target in (('crew.json', 'C-120', 'PRS-0713'), ('participants.json', 'O-860', 'PRS-0714'),
                                  ('participants.json', 'P-1068', 'PRS-0001')):
            with self.subTest(name=name, ref=ref):
                path = self.release / name
                original = path.read_bytes()
                section = json.loads(original.decode('utf-8'))
                section['entries'][ref] = target
                path.write_bytes((json.dumps(section, indent=2) + '\n').encode('utf-8'))
                self.assertTrue(any(name + ' differs' in p for p in check.check_large_release(self.release, self.temp)))
                path.write_bytes(original)
        self.assertEqual(check.check_large_release(self.release, self.temp), [])

    def test_a_missing_or_extra_file_fails(self):
        (self.release / 'participants.json').rename(self.release / 'participants.bak')
        problems = check.check_large_release(self.release, self.temp)
        self.assertTrue(any('participants.json is missing' in p for p in problems), problems)
        self.assertTrue(any('participants.bak is extra' in p for p in problems), problems)

    def test_a_changed_pinned_input_stops_the_run(self):
        pins = load(self.temp / cm.RELEASE_PINS)
        for key, entry in pins.items():
            if not (isinstance(entry, dict) and 'path' in entry):
                continue
            with self.subTest(input=key):
                path = self.temp / entry['path']
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                self.assertTrue(any('differs from its pin' in p for p in check.check_large_release(self.release, self.temp)))
                with self.assertRaises(cm.MappingFailure):
                    cm.load_release_inputs(self.temp)
                path.write_bytes(original)
        self.assertEqual(check.check_large_release(self.release, self.temp), [])

    def test_a_changed_page_of_the_large_snapshot_is_refused_by_the_hash_in_its_manifest(self):
        page = self.temp / 'uss-enterprise/personnel-v2/datasets/personnel-v2-large-004/page-004.xml'
        page.write_bytes(page.read_bytes() + b' ')
        self.assertTrue(any('v2Target: page-004.xml differs' in p for p in check.check_large_release(self.release, self.temp)))

    def test_a_manifest_that_does_not_name_the_new_dataset_releases_fails(self):
        path = self.release / 'manifest.json'
        manifest = load(path)
        manifest['checkedAgainst'] = [e for e in manifest['checkedAgainst'] if e['version'] not in ('1.1', 'personnel-v2-large-004') or e['system'] == 'assets']
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        self.assertTrue(any('manifest.json differs' in p for p in check.check_large_release(self.release, self.temp)))
        self.assertTrue(any('not checked against' in p for p in check.check_against(self.release, self.temp)))

    def test_a_participant_exception_that_names_an_o_reference_stops_the_build(self):
        path = self.temp / 'federation/personnel-mapping/participant-exceptions.json'
        table = load(path)
        table['entries']['O-860'] = 'PRS-0714'
        path.write_text(json.dumps(table, indent=2) + '\n', encoding='utf-8')
        pins = load(self.temp / cm.RELEASE_PINS)
        pins['participantExceptions']['sha256'] = cm.digest(path, 'lf')
        (self.temp / cm.RELEASE_PINS).write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
        problems = check.check_large_release(self.release, self.temp)
        self.assertTrue(any('refused by class' in p for p in problems), problems)


if __name__ == '__main__':
    unittest.main()
