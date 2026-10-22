"""Offline generator regression tests, independent of runtime registration."""
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / 'uss-enterprise/crew-personnel/generator/generate_003.py'
spec = importlib.util.spec_from_file_location('dataset003', SOURCE)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

# The generator and package reproduction pin CPython 3.12.14 (the manifest toolchain; see the legacy exception in
# governance/CONSTRAINTS.md). Under any other interpreter the tests that build or run the package skip with this reason,
# so a failing run means a defect, not the interpreter. Run them separately under the pinned interpreter.
PINNED = (platform.python_implementation(), platform.python_version()) == (g.TOOLCHAIN['implementation'], g.TOOLCHAIN['version'])
needs_pinned = unittest.skipUnless(PINNED, 'needs %s %s, the dataset 003 toolchain pin' % (g.TOOLCHAIN['implementation'], g.TOOLCHAIN['version']))


class Dataset003Tests(unittest.TestCase):
    def setUp(self):
        self.records, self.ledger = g.records_and_ledger()
        self.by_id = {r['crewId']: r for r in self.records}

    def test_exact_matrix_and_status_totals(self):
        matrix = [[1,1,2,6,4,2,4,0], [0,0,1,18,30,20,75,6], [0,0,3,35,45,25,112,0],
                  [0,0,3,30,35,8,58,6], [0,1,3,16,15,8,43,4], [0,0,0,12,20,12,76,0],
                  [0,0,1,12,11,5,27,4]]
        counts = Counter((r['department'], r['rank']) for r in self.records)
        self.assertEqual([[counts[d, r] for r in g.RANKS] for d in g.DEPARTMENTS], matrix)
        self.assertEqual([sum(row) for row in matrix], [20,150,220,140,90,120,60])
        self.assertEqual([sum(row[k] for row in matrix) for k in range(8)], [1,2,13,129,160,80,395,20])
        self.assertEqual(Counter(r['dutyStatus'] for r in self.records), {'ACTIVE':719, 'ON_LEAVE':40, 'INACTIVE':41})

    def test_retained_002_and_named_semantics(self):
        root = ET.parse(ROOT / 'uss-enterprise/crew-personnel/fixtures/canonical/crew-v1-small-002.xml').getroot()
        for member in root.findall(f'{{{g.NS}}}crewMember'):
            expected = {c.tag.split('}')[1]: c.text for c in member}
            if expected['crewId'] == 'CRW-1050':
                expected.update(department='SCIENCE', positionTitle='Science Department Lead')
            self.assertEqual(self.by_id[expected['crewId']], expected)
        self.assertEqual(self.by_id['CRW-1100']['displayName'], "Miles O'Brien")
        self.assertEqual(self.by_id['CRW-1100']['rank'], 'CHIEF_PETTY_OFFICER')
        self.assertEqual(self.by_id['CRW-1101']['displayName'], 'Sonya Gomez')
        self.assertEqual(self.by_id['CRW-1101']['supervisorCrewId'], 'CRW-1049')
        self.assertEqual(self.by_id['CRW-1055']['positionTitle'], 'Acting Ensign')
        self.assertEqual(self.by_id['CRW-1055']['supervisorCrewId'], 'CRW-1050')
        self.assertNotIn('supervisorCrewId', self.by_id['CRW-1056'])

    def test_names_ids_ledger_independent_hash_order(self):
        keys = sorted((hashlib.sha256(('enterprise-d-2366-003-v1|name|' + str(k)).encode()).hexdigest(), k)
                      for k in range(1024))
        generated = self.records[14:]
        self.assertEqual([r['crewId'] for r in generated], [f'CRW-{n}' for n in range(2000,2786)])
        self.assertEqual(len({r['displayName'] for r in self.records}), 800)
        for j, (_, k) in enumerate(keys[:786]):
            name = g.GIVEN[k // 32] + ' ' + g.FAMILY[k % 32]
            self.assertEqual(generated[j]['displayName'], name)
            self.assertEqual(self.ledger[14+j], dict(crewId=f'CRW-{2000+j}', displayName=name, slot=j, nameCandidate=k))
        self.assertTrue(all(r['slot'] is None and r['nameCandidate'] is None for r in self.ledger[:14]))

    def test_hierarchy_status_and_positions(self):
        sections = [2002,2019,2167,2383,2522,2608,2728]
        leads = [1048,1100,1049,1050,1053,1058,2727]
        for department, section, lead in zip(g.DEPARTMENTS, sections, leads):
            section_id, lead_id = f'CRW-{section}', f'CRW-{lead}'
            self.assertEqual(self.by_id[section_id]['positionTitle'], 'Section Supervisor')
            self.assertEqual(self.by_id[section_id]['supervisorCrewId'], lead_id)
            local = [r for r in self.records[14:] if r['department'] == department and r['crewId'] not in (section_id, lead_id)]
            for t, r in enumerate(local):
                self.assertEqual(r['supervisorCrewId'], lead_id if t % 10 == 0 else section_id)
                self.assertEqual(r['positionTitle'], g.TITLES[r['rank']])
        flight = self.by_id['CRW-2727']
        self.assertEqual((flight['positionTitle'], flight['supervisorCrewId']), ('Flight Operations Lead','CRW-1048'))
        for j, r in enumerate(self.records[14:]):
            expected = 'ACTIVE' if int(r['crewId'][4:]) in sections + [2727] else 'INACTIVE' if j % 20 == 0 else 'ON_LEAVE' if j % 10 == 0 else 'ACTIVE'
            self.assertEqual(r['dutyStatus'], expected)
        self.assertEqual([r['crewId'] for r in self.records if 'supervisorCrewId' not in r], ['CRW-1047','CRW-1056'])
        for r in self.records:
            seen = set()
            while r is not None:
                self.assertNotIn(r['crewId'], seen)
                seen.add(r['crewId'])
                r = self.by_id[r['supervisorCrewId']] if 'supervisorCrewId' in r else None

    def test_xml_serialization_and_page_coverage(self):
        ids = []
        for p in range(8):
            raw = g.xml_bytes(self.records,p)
            self.assertNotIn(b'\r', raw)
            self.assertTrue(raw.endswith(b'\n') and not raw.endswith(b'\n\n'))
            self.assertTrue(raw.startswith(b"<?xml version='1.0' encoding='utf-8'?>\n"))
            root = ET.fromstring(raw)
            self.assertEqual([e.tag.split('}')[1] for e in root], ['datasetVersion']+['crewMember']*100+['totalCount','offset','limit','hasMore'])
            self.assertEqual([e.text for e in list(root)[-4:]], ['800',str(p*100),'100','true' if p<7 else 'false'])
            for member in root.findall(f'{{{g.NS}}}crewMember'):
                ids.append(member[0].text)
                self.assertEqual([e.tag.split('}')[1] for e in member], list(g.FIELDS) if len(member)==7 else list(g.FIELDS[:-1]))
        self.assertEqual(ids, [r['crewId'] for r in self.records])
        altered = copy.deepcopy(self.records)
        altered[0]['displayName'] = "R&D <Systems> O'Brien"
        self.assertIn(b"R&amp;D &lt;Systems&gt; O'Brien", g.xml_bytes(altered,0))

    @needs_pinned
    def test_manifest_and_hash_binding(self):
        package = g.package_bytes()
        manifest = json.loads(package['manifest.json'])
        self.assertEqual(set(manifest), {'formatVersion','datasetVersion','count','generator','recipe','pages'})
        self.assertEqual(manifest['formatVersion'],1)
        self.assertEqual(manifest['count'],800)
        self.assertEqual(manifest['recipe']['identityLedger'],self.ledger)
        self.assertEqual(manifest['generator']['toolchain'], {'implementation':'CPython','version':'3.12.14','dependencies':'stdlib-only'})
        self.assertEqual(manifest['generator']['source']['sha256'],hashlib.sha256(SOURCE.read_bytes().replace(b'\r\n', b'\n')).hexdigest())
        for p, entry in enumerate(manifest['pages']):
            raw = package[f'page-{p:03d}.xml']
            self.assertEqual(entry, dict(filename=f'page-{p:03d}.xml',offset=p*100,count=100,byteLength=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        self.assertEqual(package['manifest.json'],(json.dumps(manifest,sort_keys=True,ensure_ascii=True,indent=2,separators=(',',': '))+'\n').encode('ascii'))

    @needs_pinned
    def test_two_processes_lf_crlf_paths_locale_and_hashseed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for label, ending, hashseed in [('a',b'\n','1'),('b',b'\r\n','987')]:
                directory = base / label
                directory.mkdir()
                source = directory / 'generate_003.py'
                source.write_bytes(SOURCE.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',ending))
                env = dict(os.environ, PYTHONHASHSEED=hashseed, TZ='UTC' if label=='a' else 'America/New_York', LC_ALL='C')
                result = subprocess.run([sys.executable,'-B',str(source),'generate',str(directory/'package')], cwd=directory, env=env, capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
            first = {p.name:p.read_bytes() for p in (base/'a/package').iterdir()}
            second = {p.name:p.read_bytes() for p in (base/'b/package').iterdir()}
            self.assertEqual(first,second)

    @needs_pinned
    def test_negative_packages(self):
        original = g.package_bytes()
        def rewrite_manifest(files, mutate):
            manifest = json.loads(files['manifest.json'])
            mutate(manifest)
            files['manifest.json'] = g.json_bytes(manifest)
        for case in ('missing','extra','tamper','reordered','page_swap','manifest_hash','manifest_key','manifest_crlf','page_crlf','dangling','cycle','self','duplicate_id','duplicate_name','version'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                files = dict(original)
                if case=='missing': del files['page-003.xml']
                elif case=='extra': files['extra.xml']=b'extra'
                elif case=='tamper': files['page-000.xml']=files['page-000.xml'].replace(b'Jean-Luc', b'Jean-Luk')
                elif case=='reordered': rewrite_manifest(files,lambda m:m['pages'].reverse())
                elif case=='page_swap': files['page-000.xml'],files['page-001.xml']=files['page-001.xml'],files['page-000.xml']
                elif case=='manifest_hash': rewrite_manifest(files,lambda m:m['pages'][0].update(sha256='0'*64))
                elif case=='manifest_key': rewrite_manifest(files,lambda m:m.update(extra=True))
                elif case=='manifest_crlf': files['manifest.json']=files['manifest.json'].replace(b'\n',b'\r\n')
                elif case=='page_crlf': files['page-000.xml']=files['page-000.xml'].replace(b'\n',b'\r\n')
                elif case=='version': files['page-001.xml']=files['page-001.xml'].replace(b'crew-v1-large-003', b'crew-v1-large-004')
                else:
                    records=copy.deepcopy(self.records)
                    if case=='dangling': records[14]['supervisorCrewId']='CRW-9999'
                    elif case=='self': records[14]['supervisorCrewId']=records[14]['crewId']
                    elif case=='cycle':
                        records[14]['supervisorCrewId']=records[15]['crewId']
                        records[15]['supervisorCrewId']=records[14]['crewId']
                    elif case=='duplicate_id': records[15]['crewId']=records[14]['crewId']
                    elif case=='duplicate_name': records[15]['displayName']=records[14]['displayName']
                    files['page-000.xml']=g.xml_bytes(records,0)
                    # Even a freshly rehashed page cannot hide invalid aggregate semantics.
                    rewrite_manifest(files,lambda m:m['pages'][0].update(sha256=g.sha(files['page-000.xml']),byteLength=len(files['page-000.xml'])))
                for name, data in files.items(): (Path(temp)/name).write_bytes(data)
                with self.assertRaises(ValueError): g.validate_package(temp)

    @needs_pinned
    def test_fail_closed_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'package'
            digest=g.generate(path)
            self.assertEqual(digest,g.validate_package(path))
            before={p.name:p.read_bytes() for p in path.iterdir()}
            with self.assertRaises(FileExistsError): g.generate(path)
            self.assertEqual(before,{p.name:p.read_bytes() for p in path.iterdir()})
        with self.assertRaises(ValueError): g.canonical_source(b'line\rbroken\n')
        with self.assertRaises(ValueError): g.canonical_source(b'\xef\xbb\xbftext\n')

    def test_negative_residual_and_insufficient_names(self):
        saved=copy.deepcopy(g.MATRIX)
        try:
            g.MATRIX[0][0]=0
            with self.assertRaisesRegex(ValueError,'negative residual'): g.records_and_ledger()
        finally: g.MATRIX[:]=saved
        given,family=g.GIVEN[:],g.FAMILY[:]
        try:
            g.GIVEN[:]=['Same']*32
            g.FAMILY[:]=['Name']*32
            with self.assertRaisesRegex(ValueError,'insufficient'): g.name_candidates()
        finally: g.GIVEN[:],g.FAMILY[:]=given,family


if __name__=='__main__':
    unittest.main()
