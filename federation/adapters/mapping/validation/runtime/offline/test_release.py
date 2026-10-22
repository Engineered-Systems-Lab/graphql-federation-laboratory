"""The mapping releases 1.0, 1.1, 1.2 and 1.3 against the repository, with no Docker.

These checks live outside the Maven tests because the build context of the image holds only federation/: the system files the
releases were checked against are under uss-enterprise/. They fail when a release file changed (a published release never changes),
when a system version or dataset release the newest mapping was not checked against appears (the probable need for a new mapping),
when assets.json differs from the expected mapping of the Assets dataset release 1.1, which is its only source, and when crew.json
differs from what the crew mapping process (federation/personnel-mapping) builds from its pinned inputs. Release 1.2 (the Missions
dataset release 1.1 against the large Personnel v2 snapshot) has its own acceptance file, test_release_1_2.py, and release 1.3 (the
participants of Missions dataset release 1.2, all resolved) has test_release_1_3.py.
"""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_support as support  # noqa: E402
import release_check as check  # noqa: E402

ROOT = support.ROOT
RELEASES = check.RELEASES
# Release 1.0 is published and immutable: the hashes of its two files, as published.
RELEASE_1_0 = {'manifest.json': '07e2299af09f72700b555712737c9e8beb08c5a979aad616684dcef108372bb6',
               'assets.json': '694ab6c8153655f6506437405cab7f07bc83d22ce3fb73d088cefc032235117c'}


def latest_release():
    return check.release_folders(ROOT)[-1]


def release(version):
    return ROOT / RELEASES / version


class RealReleases(unittest.TestCase):
    def test_the_release_folders_are_1_0_1_1_1_2_and_1_3(self):
        self.assertEqual([p.name for p in check.release_folders(ROOT)], ['1.0', '1.1', '1.2', '1.3'])
        self.assertEqual(sorted(p.name for p in release('1.0').iterdir()), ['assets.json', 'manifest.json'])
        self.assertEqual(sorted(p.name for p in release('1.1').iterdir()), ['assets.json', 'crew.json', 'manifest.json'])
        self.assertEqual(sorted(p.name for p in release('1.2').iterdir()), ['assets.json', 'crew.json', 'manifest.json', 'participants.json'])
        self.assertEqual(sorted(p.name for p in release('1.3').iterdir()), ['assets.json', 'crew.json', 'manifest.json', 'participants.json'])

    def test_release_1_0_is_untouched(self):
        for name, digest in RELEASE_1_0.items():
            self.assertEqual(check.lf_sha256(release('1.0') / name), digest, name)

    def test_release_1_1_carries_the_assets_of_release_1_0_unchanged(self):
        self.assertEqual((release('1.1') / 'assets.json').read_bytes(), (release('1.0') / 'assets.json').read_bytes())

    def test_every_file_of_every_release_matches_its_hash_in_the_manifest(self):
        for folder in check.release_folders(ROOT):
            self.assertEqual(check.check_files(folder), [], folder.name)

    def test_the_mapping_was_checked_against_the_current_system_files(self):
        self.assertEqual(check.check_against(latest_release(), ROOT), [])
        self.assertEqual(check.check_against(release('1.0'), ROOT, newest=False), [])

    def test_the_pending_list_is_empty_and_the_newest_release_names_every_system_release(self):
        self.assertEqual(check.PENDING_MAPPING, set())
        self.assertEqual(latest_release().name, '1.3')
        listed = {(e['system'], e['artifact'], e['version']) for e in check.load(latest_release() / 'manifest.json')['checkedAgainst']}
        self.assertIn(('missions', 'dataset release manifest', '1.1'), listed)
        self.assertIn(('missions', 'dataset release manifest', '1.2'), listed)
        self.assertIn(('personnel', 'dataset snapshot', 'personnel-v2-large-004'), listed)
        self.assertEqual(check.check_against(release('1.2'), ROOT, newest=False), [])

    def test_a_system_release_the_newest_mapping_was_not_checked_against_is_excused_only_by_the_list(self):
        original = check.PENDING_MAPPING
        try:
            check.PENDING_MAPPING = set()
            problems = check.check_against(release('1.2'), ROOT)  # release 1.2 was not checked against Missions 1.2
            self.assertTrue(any('missions dataset release manifest 1.2' in p and 'not checked against' in p for p in problems))
            check.PENDING_MAPPING = {('missions', 'dataset release manifest', '1.2')}
            self.assertEqual(check.check_against(release('1.2'), ROOT), [])
            self.assertTrue(any('still in PENDING_MAPPING' in p for p in check.check_against(latest_release(), ROOT)))
        finally:
            check.PENDING_MAPPING = original

    def test_release_1_0_alone_no_longer_names_the_newest_versions(self):
        self.assertTrue(any('personnel' in p and 'not checked against' in p for p in check.check_against(release('1.0'), ROOT)))

    def test_the_checked_against_list_of_1_0_names_the_three_decided_artifacts(self):
        manifest = check.load(release('1.0') / 'manifest.json')
        self.assertEqual([(e['system'], e['artifact'], e['version']) for e in manifest['checkedAgainst']],
                         [('missions', 'dataset release manifest', '1.0'), ('assets', 'contract file', '1.1'),
                          ('assets', 'dataset release manifest', '1.1')])
        assets_manifest = check.load(ROOT / check.ASSETS_DATASETS / '1.1/manifest.json')
        self.assertEqual(manifest['checkedAgainst'][0]['sha256'], assets_manifest['missionsRelease']['manifestSha256'],
                         'the Assets dataset names the same Missions release manifest')
        self.assertEqual(manifest['checkedAgainst'][1]['sha256'], assets_manifest['contractSha256'],
                         'the Assets dataset names the same contract file')

    def test_the_checked_against_list_of_1_1_adds_the_personnel_v2_snapshot(self):
        manifest = check.load(release('1.1') / 'manifest.json')
        self.assertEqual([(e['system'], e['artifact'], e['version']) for e in manifest['checkedAgainst']],
                         [('missions', 'dataset release manifest', '1.0'), ('assets', 'contract file', '1.1'),
                          ('assets', 'dataset release manifest', '1.1'),
                          ('personnel', 'dataset snapshot', 'personnel-v2-small-003')])
        self.assertEqual(manifest['checkedAgainst'][:3], check.load(release('1.0') / 'manifest.json')['checkedAgainst'])

    def test_assets_json_is_the_expected_mapping_of_the_assets_dataset_and_nothing_else(self):
        for version in ('1.0', '1.1'):
            self.assertEqual(check.check_assets_section(release(version), ROOT), [], version)
        entries = check.load(release('1.1') / 'assets.json')['entries']
        self.assertEqual(len(entries), 8)
        self.assertEqual(entries['EQ-97'], 'AST-0097')
        self.assertNotIn('EQ-108', entries)

    def test_crew_json_is_the_crew_mapping_the_process_builds_and_nothing_else(self):
        self.assertEqual(check.check_crew_section(release('1.1'), ROOT), [])
        entries = check.load(release('1.1') / 'crew.json')['entries']
        self.assertEqual(len(entries), 10)
        self.assertEqual(entries['C-71'], 'PRS-0001')
        self.assertEqual(entries['C-134'], 'PRS-1100')

    def test_the_files_use_lf_line_ends(self):
        for folder in check.release_folders(ROOT):
            for path in folder.iterdir():
                self.assertNotIn(b'\r', path.read_bytes(), folder.name + '/' + path.name)


class TheChecksCatchChanges(unittest.TestCase):
    """The checks themselves, on a small repository built in a temporary folder."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='mapping-release-check-'))
        self.addCleanup(shutil.rmtree, self.temp, True)
        for relative in (check.ASSETS_CONTRACTS + '/assets-v1.1.openapi.json', check.ASSETS_DATASETS + '/1.1/manifest.json',
                         check.ASSETS_DATASETS + '/1.1/assets.json', check.PROVENANCE, check.MISSIONS_DATASETS + '/1.0/manifest.json',
                         check.PERSONNEL_DATASETS + '/personnel-v2-small-003.xml'):
            self.copy(relative)
        for version in ('1.0', '1.1'):
            for file in (ROOT / RELEASES / version).iterdir():
                self.copy(RELEASES + '/' + version + '/' + file.name)
        self.release = self.temp / RELEASES / '1.0'
        self.newest = self.temp / RELEASES / '1.1'

    def copy(self, relative):
        target = self.temp / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)

    def copy_process(self):
        """The crew mapping process with every input it pins (the old release of the people is copied whole)."""
        pins = check.load(ROOT / 'federation/personnel-mapping/pins.json')
        for entry in pins.values():
            if isinstance(entry, dict) and 'path' in entry:
                self.copy(entry['path'])
        self.copy(check.CREW_MAPPING)
        self.copy('federation/personnel-mapping/pins.json')
        source = ROOT / pins['v1Release']['path']
        shutil.copytree(source.parent, (self.temp / pins['v1Release']['path']).parent, dirs_exist_ok=True)

    def test_the_copy_passes(self):
        self.copy_process()
        for folder, newest in ((self.release, False), (self.newest, True)):
            self.assertEqual(check.check_files(folder) + check.check_against(folder, self.temp, newest=newest)
                             + check.check_assets_section(folder, self.temp), [], folder.name)
        self.assertEqual(check.check_crew_section(self.newest, self.temp), [])

    def test_a_changed_release_file_fails(self):
        path = self.release / 'assets.json'
        path.write_bytes(path.read_bytes().replace(b'AST-0004', b'AST-0005'))
        self.assertTrue(any('never changes' in p for p in check.check_files(self.release)))

    def test_an_unlisted_file_fails(self):
        (self.release / 'crew.json').write_text('{}\n', encoding='utf-8')
        self.assertTrue(any('differ' in p for p in check.check_files(self.release)))

    def test_a_changed_assets_contract_fails_with_the_need_for_a_new_mapping(self):
        path = self.temp / check.ASSETS_CONTRACTS / 'assets-v1.1.openapi.json'
        path.write_bytes(path.read_bytes() + b' ')
        problems = check.check_against(self.newest, self.temp)
        self.assertTrue(any('new mapping' in p and 'contract file' in p for p in problems), problems)

    def test_a_changed_dataset_missions_or_personnel_file_fails(self):
        for relative in (check.ASSETS_DATASETS + '/1.1/manifest.json', check.MISSIONS_DATASETS + '/1.0/manifest.json',
                         check.PERSONNEL_DATASETS + '/personnel-v2-small-003.xml'):
            with self.subTest(relative=relative):
                path = self.temp / relative
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                self.assertTrue(any('new mapping' in p for p in check.check_against(self.newest, self.temp)))
                path.write_bytes(original)
        self.assertEqual(check.check_against(self.newest, self.temp), [])

    def test_a_newer_system_version_the_mapping_was_not_checked_against_fails(self):
        cases = {'assets contract': (check.ASSETS_CONTRACTS + '/assets-v1.2.openapi.json', 'assets contract file 1.2'),
                 'assets dataset': (check.ASSETS_DATASETS + '/1.2/manifest.json', 'assets dataset release manifest 1.2'),
                 'missions dataset': (check.MISSIONS_DATASETS + '/1.3/manifest.json', 'missions dataset release manifest 1.3'),
                 'personnel snapshot': (check.PERSONNEL_DATASETS + '/personnel-v2-small-004.xml',
                                        'personnel dataset snapshot personnel-v2-small-004')}
        for name, (relative, text) in cases.items():
            with self.subTest(name=name):
                path = self.temp / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}\n', encoding='utf-8')
                problems = check.check_against(self.newest, self.temp)
                self.assertTrue(any(text in p and 'not checked against' in p for p in problems), problems)
                path.unlink()

    def test_a_newer_system_version_does_not_fail_an_older_release_that_stays_true_to_what_it_lists(self):
        path = self.temp / check.PERSONNEL_DATASETS / 'personnel-v2-small-004.xml'
        path.write_text('{}\n', encoding='utf-8')
        self.assertEqual(check.check_against(self.release, self.temp, newest=False), [])

    def test_a_manifest_with_no_checked_against_list_fails(self):
        manifest = check.load(self.release / 'manifest.json')
        manifest['checkedAgainst'] = []
        (self.release / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(any('no checkedAgainst' in p for p in check.check_against(self.release, self.temp)))

    def test_an_invented_or_missing_entry_fails(self):
        path = self.release / 'assets.json'
        section = json.loads(path.read_text(encoding='utf-8'))
        section['entries']['EQ-108'] = 'AST-0008'
        path.write_text(json.dumps(section), encoding='utf-8')
        problems = check.check_assets_section(self.release, self.temp)
        self.assertTrue(any('differ from the expected mapping' in p for p in problems), problems)
        del section['entries']['EQ-108'], section['entries']['EQ-64']
        path.write_text(json.dumps(section), encoding='utf-8')
        self.assertTrue(any('differ from the expected mapping' in p for p in check.check_assets_section(self.release, self.temp)))

    def test_a_changed_or_invented_crew_entry_fails(self):
        self.copy_process()
        path = self.newest / 'crew.json'
        section = json.loads(path.read_text(encoding='utf-8'))
        section['entries']['C-85'] = 'PRS-0003'
        path.write_text(json.dumps(section, indent=2) + '\n', encoding='utf-8')
        self.assertTrue(any('crew.json differs' in p for p in check.check_crew_section(self.newest, self.temp)))
        section['entries']['C-85'] = 'PRS-0002'
        section['entries']['C-999'] = 'PRS-0003'
        path.write_text(json.dumps(section, indent=2) + '\n', encoding='utf-8')
        self.assertTrue(any('crew.json differs' in p for p in check.check_crew_section(self.newest, self.temp)))

    def test_a_changed_pinned_input_of_the_process_fails(self):
        self.copy_process()
        for relative in ('federation/personnel-mapping/mapping-exceptions.json',
                         check.PERSONNEL_DATASETS + '/personnel-v2-small-002.xml', 'uss-enterprise/missions/datasets/recipe.json'):
            with self.subTest(relative=relative):
                path = self.temp / relative
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                self.assertTrue(any('differs from its pin' in p for p in check.check_crew_section(self.newest, self.temp)))
                path.write_bytes(original)
        self.assertEqual(check.check_crew_section(self.newest, self.temp), [])

    def test_a_release_that_does_not_name_the_personnel_snapshot_fails(self):
        self.copy_process()
        manifest = check.load(self.newest / 'manifest.json')
        manifest['checkedAgainst'] = [e for e in manifest['checkedAgainst'] if e['system'] != 'personnel']
        (self.newest / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(any('does not name the Personnel v2 snapshot' in p for p in check.check_crew_section(self.newest, self.temp)))


if __name__ == '__main__':
    unittest.main()
