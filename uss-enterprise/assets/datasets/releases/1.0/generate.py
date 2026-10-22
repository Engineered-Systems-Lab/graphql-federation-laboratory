"""Assets dataset authoring. Never invoked by a service.

The release is derived from curation.json and the released Missions dataset it is checked against.
Standard library only. `review` writes the static review page and the release files into a fresh folder;
`release` publishes an immutable release folder and refuses to reuse a version.
"""
from html import escape
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parent
# This file also lives, byte for byte, inside each release folder, so the repository is found by walking up.
# A validator that copies a release elsewhere sets CONTRACT and MISSIONS_RELEASE itself before it calls release_bytes.
REPOSITORY = next((p for p in HERE.parents if (p / 'uss-enterprise/assets').is_dir()), None)
CONTRACT = REPOSITORY and REPOSITORY / 'uss-enterprise/assets/contracts/assets-v1.0.openapi.json'
MISSIONS_RELEASE = REPOSITORY and REPOSITORY / 'uss-enterprise/missions/datasets/releases/1.0'
GENERATOR_VERSION = 'assets-generator-1'
DATASET_VERSION = '1.0'
CONTRACT_REVISION = '1.0'
ASSET_ID = re.compile(r'[A-Z]{2,5}-[1-9][0-9]*')
# The kind-to-category table of the design document, spelled once here: a new kind is one row.
KIND_CATEGORY = {'STARSHIP': 'VEHICLE', 'SHUTTLE': 'VEHICLE', 'ROVER': 'VEHICLE', 'ARMORED_VEHICLE': 'VEHICLE',
                 'PHASER': 'EQUIPMENT', 'TRICORDER': 'EQUIPMENT', 'COMMUNICATOR': 'EQUIPMENT',
                 'SCIENTIFIC_INSTRUMENT': 'EQUIPMENT', 'MUSICAL_INSTRUMENT': 'EQUIPMENT'}
STATUSES = ('ACTIVE', 'MAINTENANCE', 'DECOMMISSIONED', 'DESTROYED', 'MISSING')
RELEASE_FILES = ('assets.json', 'curation.json', 'generate.py', 'manifest.json', 'provenance.json')


def canonical(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('utf-8')


def source_bytes(path):
    return Path(path).read_bytes().replace(b'\r\n', b'\n')


def digest(content):
    return hashlib.sha256(content).hexdigest()


def load(path):
    return json.loads(source_bytes(path).decode('utf-8'))


def id_key(asset_id):
    prefix, number = asset_id.split('-')
    return prefix, int(number)


def missions_references(release_dir=None):
    """Return {assetId: [mission, ...]} from the released Missions dataset, and the total reference count."""
    missions = load(Path(release_dir or MISSIONS_RELEASE) / 'release.json')['missions']
    found = {}
    total = 0
    for mission in missions:
        for asset_id in mission['assignedAssetIds']:
            found.setdefault(asset_id, []).append({'missionId': mission['missionId'], 'title': mission['title'],
                                                   'status': mission['status'], 'stardate': mission['stardate']})
            total += 1
    return found, total


def build_assets(curation):
    assets = []
    for entry in curation['assets']:
        kind = entry['kind']
        if kind not in KIND_CATEGORY:
            raise ValueError('Unknown kind ' + kind)
        assets.append({'assetId': entry['assetId'], 'kind': kind, 'category': KIND_CATEGORY[kind], 'name': entry['name'],
                       'description': entry['description'], 'status': entry['status'],
                       'parentAssetId': entry['parentAssetId']})
    assets.sort(key=lambda a: id_key(a['assetId']))
    return {'datasetVersion': DATASET_VERSION, 'contractRevision': CONTRACT_REVISION, 'assets': assets}


def build_provenance(curation, references, total):
    held = {a['assetId'] for a in curation['assets']}
    nine = sorted(references, key=id_key)
    expected = []
    for asset_id in nine:
        want = curation['expectedReferences'][asset_id]
        expected.append({'assetId': asset_id, 'case': want['case'], 'resolution': want['resolution'],
                         'assetsAnswers': '404 ASSET_NOT_FOUND' if want['resolution'] == 'UNRESOLVED' else '200 with the record',
                         'consumerShows': ('UNRESOLVED with asset null, as data' if want['resolution'] == 'UNRESOLVED'
                                           else 'RESOLVED with the asset'),
                         'status': want['status'], 'referenceCount': len(references[asset_id]),
                         'missionIds': sorted(m['missionId'] for m in references[asset_id]),
                         'heldByAssets': asset_id in held, **({'note': want['note']} if 'note' in want else {})})
    return {
        'cases': curation['cases'],
        'consumerRule': curation['consumerRule'],
        'expectedReferences': expected,
        'idConvention': curation['idConvention'],
        'limitations': [
            'Synthetic lab content: no claim of canon.',
            'Kinds, statuses and parents of the nine Missions-referenced assets are decided by this dataset; Missions holds ids only.',
            'No timing judgment: DESTROYED and MISSING assets resolve with their status.',
            'No location, no Personnel mapping and no cross-service rule beyond the references shown.'],
        'missionsRelease': {'datasetVersion': '1.0', 'distinctAssets': len(nine), 'references': total},
        'parentChains': curation['parentChains'],
        'sources': curation['sources'],
    }


def build_release(directory):
    """Build every release file's bytes from a folder that holds curation.json (and the generator beside it)."""
    curation = load(Path(directory) / 'curation.json')
    references, total = missions_references()
    assets = build_assets(curation)
    provenance = build_provenance(curation, references, total)
    return canonical(assets), canonical(provenance)


def build_manifest(assets_bytes, provenance_bytes, curation_bytes, generator_bytes, assets):
    contract = source_bytes(CONTRACT)
    return {
        'contractRevision': CONTRACT_REVISION,
        'contractSha256': digest(contract),
        'counts': {'assets': len(assets['assets']),
                   'kinds': len({a['kind'] for a in assets['assets']})},
        'datasetVersion': DATASET_VERSION,
        'files': {'assets.json': digest(assets_bytes), 'curation.json': digest(curation_bytes),
                  'generate.py': digest(generator_bytes), 'provenance.json': digest(provenance_bytes)},
        'generatorVersion': GENERATOR_VERSION,
        'missionsRelease': {'datasetVersion': '1.0',
                            'manifestSha256': digest(source_bytes(MISSIONS_RELEASE / 'manifest.json')),
                            'releaseSha256': digest(source_bytes(MISSIONS_RELEASE / 'release.json'))},
    }


def release_bytes():
    curation_bytes = source_bytes(HERE / 'curation.json')
    generator_bytes = source_bytes(Path(__file__))
    assets_bytes, provenance_bytes = build_release(HERE)
    assets = json.loads(assets_bytes)
    manifest = build_manifest(assets_bytes, provenance_bytes, curation_bytes, generator_bytes, assets)
    return {'assets.json': assets_bytes, 'curation.json': curation_bytes, 'generate.py': generator_bytes,
            'manifest.json': canonical(manifest), 'provenance.json': provenance_bytes}


CSS = """
:root{--bg:#f6f7f9;--fg:#1b1f24;--muted:#5b6570;--card:#fff;--line:#d5dae0;--ok:#0b7a43;--bad:#b3261e;--warn:#8a5a00;--accent:#1f4f99}
@media (prefers-color-scheme:dark){:root{--bg:#14171b;--fg:#e8ebee;--muted:#9aa5b1;--card:#1d2127;--line:#363d46;--ok:#4cc38a;--bad:#ff8a80;--warn:#e0b050;--accent:#7fb0ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}h1{font-size:1.5rem;margin:.2em 0}h2{font-size:1.15rem;margin:1.6em 0 .5em;border-bottom:1px solid var(--line);padding-bottom:.2em}
p{margin:.4em 0}.muted{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}.card b{display:block;font-size:1.5rem}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:.88rem}th,td{padding:6px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--bg);position:sticky;top:0}.tag{display:inline-block;padding:1px 7px;border-radius:10px;border:1px solid var(--line);font-size:.78rem;white-space:nowrap}
.RESOLVED{color:var(--ok)}.UNRESOLVED{color:var(--bad)}.DESTROYED,.MISSING{color:var(--warn)}code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.92em}
"""


def table(headers, rows):
    head = ''.join(f'<th>{escape(h)}</th>' for h in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def code(value):
    return f'<code>{escape(value)}</code>'


def tag(value):
    return f'<span class="tag {escape(value)}">{escape(value)}</span>'


def render_review(assets, provenance, references):
    items = assets['assets']
    by_id = {a['assetId']: a for a in items}
    children = {}
    for a in items:
        if a['parentAssetId']:
            children.setdefault(a['parentAssetId'], []).append(a['assetId'])
    referenced = set(references)
    expected = provenance['expectedReferences']
    resolved = sum(1 for e in expected if e['resolution'] == 'RESOLVED')
    kinds = {}
    for a in items:
        kinds[a['kind']] = kinds.get(a['kind'], 0) + 1
    statuses = {}
    for a in items:
        statuses[a['status']] = statuses.get(a['status'], 0) + 1
    parts = [f'<h1>Assets dataset {escape(DATASET_VERSION)}: review page</h1>',
             '<p class="muted">Static page for the Captain to read before the dataset is released. It is a review artifact of the '
             'dataset tooling, not a service frontend. Nothing here is published yet.</p>']
    cards = [('Assets', len(items)), ('Kinds', len(kinds)), ('Missions-referenced ids', len(expected)),
             ('Resolve', resolved), ('Dangling', len(expected) - resolved),
             ('Missions references', provenance['missionsRelease']['references'])]
    parts.append('<div class="cards">' + ''.join(f'<div class="card"><b>{n}</b>{escape(t)}</div>' for t, n in cards) + '</div>')
    parts.append('<h2>Summary</h2><p>Kinds: ' + ', '.join(f'{code(k)} {n}' for k, n in sorted(kinds.items())) + '</p>'
                 '<p>Statuses: ' + ', '.join(f'{code(k)} {n}' for k, n in sorted(statuses.items())) + '</p>'
                 f'<p>Unreferenced by any mission: {len(items) - resolved} assets (every asset except the {resolved} resolving Missions-referenced ones).</p>')
    parts.append('<h2>The nine Missions-referenced ids</h2><p class="muted">Released Missions dataset 1.0: 9 distinct assets in '
                 f'{provenance["missionsRelease"]["references"]} references. Two layers answer: what the Assets service answers, and what the '
                 'consumer shows; the federation shape is { id, resolution, asset }. '
                 + escape(provenance['consumerRule']) + '</p>')
    rows = []
    for e in expected:
        a = by_id.get(e['assetId'])
        rows.append([code(e['assetId']), tag(e['case']), escape(e['assetsAnswers']), escape(e['consumerShows']),
                     escape(f'{a["name"]} ({a["kind"]}, {a["status"]})') if a else '<span class="muted">not held: 404 ASSET_NOT_FOUND</span>',
                     str(e['referenceCount']), '<br>'.join(code(m) for m in e['missionIds']),
                     escape(e.get('note', ''))])
    parts.append(table(['Id', 'Case', 'Assets answers', 'Consumer shows', 'Asset in the dataset', 'Missions references', 'Missions', 'Note'], rows))
    parts.append('<h2>Controlled cases and expected outcomes</h2>')
    parts.append('<p>' + escape(provenance['consumerRule']) + '</p>')
    parts.append(table(['Case', 'Assets', 'Assets answers', 'Consumer shows', 'Expected outcome'], [
        [tag(c['case']), ', '.join(code(i) for i in case_assets(c['case'], items, referenced, provenance)) or '-',
         escape(c['assetsAnswers']), escape(c['consumerShows']), escape(c['expected'])]
        for c in provenance['cases']]))
    parts.append('<h2>Parent chains</h2>')
    parts.append(table(['Chain, child to top'], [[' &rarr; '.join(f'{code(i)} {escape(by_id[i]["name"])}' for i in chain)]
                                                  for chain in provenance['parentChains']]))
    parts.append('<h2>All assets</h2>')
    rows = []
    for a in items:
        parent = a['parentAssetId']
        rows.append([code(a['assetId']), tag(a['kind']), tag(a['category']), escape(a['name']), escape(a['description']),
                     tag(a['status']), code(parent) if parent else '-', ', '.join(code(c) for c in children.get(a['assetId'], [])) or '-',
                     str(len(references.get(a['assetId'], []))) if a['assetId'] in referenced else '0'])
    parts.append(table(['Id', 'Kind', 'Category', 'Name', 'Description', 'Status', 'Parent', 'Carries', 'Mission refs'], rows))
    parts.append('<h2>Id convention and sources</h2><p class="muted">The prefix is a dataset convention, not a contract rule.</p>'
                 + table(['Prefix', 'Used for'], [[code(k), escape(v)] for k, v in sorted(provenance['idConvention'].items())])
                 + '<p class="muted">' + escape(provenance['sources']['inspiration']) + ' ' + escape(provenance['sources']['synthetic']) + '</p>')
    body = '\n'.join(parts)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Assets dataset review</title><style>{CSS}</style></head><body><main>{body}</main></body></html>\n')


def case_assets(case, items, referenced, provenance):
    if case == 'DANGLING':
        return [e['assetId'] for e in provenance['expectedReferences'] if e['case'] == 'DANGLING']
    if case == 'PARENT_CHAIN':
        return [i for chain in provenance['parentChains'] for i in chain]
    if case == 'UNREFERENCED':
        return [a['assetId'] for a in items if a['assetId'] not in referenced]
    return [e['assetId'] for e in provenance['expectedReferences'] if e['case'] == case]


def write_new_folder(folder, files):
    folder = Path(folder)
    if folder.exists():
        raise ValueError('Refusing to reuse an existing folder: ' + str(folder))
    folder.mkdir(parents=True)
    for name, content in files.items():
        (folder / name).write_bytes(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    review = sub.add_parser('review', help='write the review page and the candidate release files into a fresh folder')
    review.add_argument('--output', required=True)
    publish = sub.add_parser('release', help='publish the immutable release folder after the Captain reviewed it')
    publish.add_argument('--captain-reviewed', action='store_true')
    args = parser.parse_args(argv)
    files = release_bytes()
    if args.command == 'review':
        references, _ = missions_references()
        page = render_review(json.loads(files['assets.json']), json.loads(files['provenance.json']), references)
        write_new_folder(args.output, {**files, 'review.html': page.encode('utf-8')})
        print('Wrote ' + str(Path(args.output).resolve()))
        return 0
    if not args.captain_reviewed:
        print('FAIL: release needs --captain-reviewed, stating that the Captain read the review page', file=sys.stderr)
        return 1
    target = HERE / 'releases' / DATASET_VERSION
    write_new_folder(target, files)
    print('Published ' + str(target))
    return 0


if __name__ == '__main__':
    sys.exit(main())
