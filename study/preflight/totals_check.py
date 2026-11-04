"""The graph-arm totals check of study 2 (the Job study2_graph_totals, G2): in one graph arm, every total of the page fields equals the paged
count, filtered and unfiltered, and the page fields return the deprecated lists' items.

    python -B study/preflight/totals_check.py --arm <gamma|delta|epsilon> --backend real --config <machine-local study config>
        --output <report.json outside the repository>

It runs against a live stack, through the arm's own MCP tool `graphql_query` and nothing else, after the same verification of the running
stack that step 7 makes (study/corpus2/reference/run_reference.py `verify_backend`: the observed containers and images against the
declaration of study/launch/make_config.py, and on the real backend the dataset fingerprint of the Missions database); a stack that is not
the declared one refuses the run (exit 4). The reference solutions are not changed or used: the check imports the arms' access layers
(reference/graph_access.py) only for their one call to the tool, so the hashes that bind the step 7 reports stay as they are.

For each page field (`missionsPage`, `assetsPage`) it asks the unfiltered selection and every value of every enum filter of that list
(Missions: type, classification, status, priority 1 to 5, issuingAuthority, locationType; Assets: kind, category, status), each page with
the graph's largest limit (100), offset 0, 100, ... until hasMore is false, and requires:
  - every page answers with no errors entry, echoes its offset and limit, and gives the same totalCount;
  - hasMore is true exactly when rows remain after the page, and every page before the last is full;
  - the paged count equals totalCount;
  - the items, joined in page order, are the deprecated list's (`missions`, `assets`) for the same filters, paged the same way;
  - a page that starts at the total is empty, with the same total and hasMore false;
and, for every filter, that its values' totals add up to the unfiltered total (every record has exactly one value of each such field).

The report names the arm, the verified provenance, every selection with its total, its pages and its problems, and the hashes of this
script and of the access layer it calls. The exit status is 0 only when no selection has a problem. Starting a stack or an MCP server is an
operator action, and so is this run against one: it needs the lead developer's go.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REFERENCE = REPO / 'study' / 'corpus2' / 'reference'
for folder in (REFERENCE, REFERENCE.parent):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

ARMS = ('gamma', 'delta', 'epsilon')
PAGE = 100
LISTS = {
    'missionsPage': {'list': 'missions', 'owner': 'missions', 'id': 'missionId', 'filters': {
        'type': ('MissionType', ['DIPLOMATIC', 'EXPLORATION', 'SCIENTIFIC', 'FIRST_CONTACT', 'MEDICAL', 'RESCUE', 'HUMANITARIAN', 'SECURITY',
                                 'TACTICAL', 'TRANSPORT', 'MAINTENANCE']),
        'classification': ('Classification', ['UNCLASSIFIED', 'SECRET', 'TOP_SECRET']),
        'status': ('MissionStatus', ['PLANNED', 'AUTHORIZED', 'ACTIVE', 'POSTPONED', 'COMPLETED', 'FAILED', 'CANCELLED']),
        'priority': ('Int', [1, 2, 3, 4, 5]),
        'issuingAuthority': ('IssuingAuthority', ['STARFLEET_COMMAND', 'ENTERPRISE_COMMAND', 'STARFLEET_MEDICAL', 'STARFLEET_SCIENCE',
                                                  'STARFLEET_SECURITY', 'FEDERATION_COUNCIL']),
        'locationType': ('LocationType', ['PLANET', 'STARBASE', 'VESSEL', 'SECTOR', 'DEEP_SPACE', 'ENTERPRISE', 'OTHER'])}},
    'assetsPage': {'list': 'assets', 'owner': 'assets', 'id': 'assetId', 'filters': {
        'kind': ('AssetKind', ['STARSHIP', 'SHUTTLE', 'ROVER', 'ARMORED_VEHICLE', 'PHASER', 'TRICORDER', 'COMMUNICATOR',
                               'SCIENTIFIC_INSTRUMENT', 'MUSICAL_INSTRUMENT']),
        'category': ('AssetCategory', ['VEHICLE', 'EQUIPMENT']),
        'status': ('AssetStatus', ['ACTIVE', 'MAINTENANCE', 'DECOMMISSIONED', 'DESTROYED', 'MISSING'])}},
}


def max_pages(total):
    """The most pages of PAGE rows a traversal may ask: the pages that hold `total` rows and the empty or short one after them."""
    return (total if isinstance(total, int) and total >= 0 else 0) // PAGE + 1


def digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


class Checker:
    """The checks over one arm's access layer (an object with `query(root, operation, text, variables)`, the arms' GraphAccess)."""

    def __init__(self, access):
        self.access = access
        self.calls = 0

    def ask(self, owner, operation, text, variables):
        self.calls += 1
        return self.access.query(owner, operation, text, variables)

    @staticmethod
    def declaration(filters, types):
        decl = ''.join(', $%s: %s' % (name, types[name]) for name in filters)
        args = ''.join('%s: $%s, ' % (name, name) for name in filters)
        return decl, args

    def page_field(self, field, filters):
        """Every page of the page field for `filters`: (items, total, pages, problems)."""
        spec = LISTS[field]
        types = {name: spec['filters'][name][0] for name in filters}
        decl, args = self.declaration(filters, types)
        text = ('query TotalsPage($offset: Int, $limit: Int%s) { %s(%soffset: $offset, limit: $limit) { items { %s } totalCount offset limit '
                'hasMore } }' % (decl, field, args, spec['id']))
        items, total, pages, problems, offset = [], None, 0, [], 0
        while True:
            page = self.ask(spec['owner'], 'TotalsPage', text, dict(filters, offset=offset, limit=PAGE)).get(field)
            pages += 1
            if page is None:
                return items, total, pages, problems + ['the page at offset %d is null' % offset]
            if total is None:
                total = page['totalCount']
            if page['totalCount'] != total:
                problems.append('the page at offset %d gives totalCount %s, the first page %s' % (offset, page['totalCount'], total))
            if (page['offset'], page['limit']) != (offset, PAGE):
                problems.append('the page at offset %d echoes offset %s and limit %s' % (offset, page['offset'], page['limit']))
            fresh = [item[spec['id']] for item in page['items']]
            if set(fresh) & set(items):
                return items, total, pages, problems + ['the page at offset %d repeats rows of an earlier page' % offset]
            items += fresh
            if page['hasMore'] != (len(items) < total):
                problems.append('the page at offset %d says hasMore %s with %d of %d rows paged' % (offset, page['hasMore'], len(items), total))
            if not page['hasMore'] or not page['items']:
                break
            if pages >= max_pages(total):
                problems.append('more than the %d pages a total of %s allows' % (max_pages(total), total))
                break
            if len(page['items']) != PAGE:
                problems.append('the page at offset %d is not full but not the last' % offset)
            offset += PAGE
        if len(items) != total:
            problems.append('%d rows paged, totalCount %s' % (len(items), total))
        if len(set(items)) != len(items):
            problems.append('a row appears twice in the pages')
        return items, total, pages, problems

    def deprecated_list(self, field, filters, total):
        """The deprecated list's ids for `filters`, paged offset 0, 100, ... until a page is short, and its problem or None. The traversal
        is bounded by the pages the page field's total allows, and a page that repeats rows ends it, so a graph that ignores the offset
        cannot make the check run on."""
        spec = LISTS[field]
        types = {name: spec['filters'][name][0] for name in filters}
        decl, args = self.declaration(filters, types)
        text = 'query TotalsList($offset: Int, $limit: Int%s) { %s(%soffset: $offset, limit: $limit) { %s } }' % (decl, spec['list'], args, spec['id'])
        ids, offset, pages = [], 0, 0
        while True:
            batch = self.ask(spec['owner'], 'TotalsList', text, dict(filters, offset=offset, limit=PAGE)).get(spec['list'])
            pages += 1
            if batch is None:
                return None, 'the deprecated list is null'
            fresh = [item[spec['id']] for item in batch]
            if set(fresh) & set(ids):
                return ids, 'the deprecated list repeats rows at offset %d' % offset
            ids += fresh
            if len(batch) < PAGE:
                return ids, None
            if pages >= max_pages(total):
                return ids, 'the deprecated list has more than the %d pages a total of %s allows' % (max_pages(total), total)
            offset += PAGE

    def beyond_end(self, field, total):
        spec = LISTS[field]
        text = 'query TotalsEnd($offset: Int) { %s(offset: $offset, limit: 20) { items { %s } totalCount offset limit hasMore } }' % (field, spec['id'])
        page = self.ask(spec['owner'], 'TotalsEnd', text, {'offset': total}).get(field)
        expected = {'items': [], 'totalCount': total, 'offset': total, 'limit': 20, 'hasMore': False}
        return [] if page == expected else ['the page at the total (offset %d) is %s, not %s' % (total, json.dumps(page), json.dumps(expected))]

    def selection(self, field, filters):
        items, total, pages, problems = self.page_field(field, filters)
        listed, problem = self.deprecated_list(field, filters, total)
        if problem:
            problems.append(problem)
        elif listed != items:
            problems.append('the items differ from the deprecated list (%d against %d rows)' % (len(items), len(listed)))
        return {'field': field, 'filters': filters, 'totalCount': total, 'paged': len(items), 'pages': pages, 'problems': problems}

    def run(self):
        rows, sums = [], []
        for field, spec in LISTS.items():
            whole = self.selection(field, {})
            rows.append(whole)
            if whole['totalCount'] is not None:
                whole['problems'] += self.beyond_end(field, whole['totalCount'])
            for name, (_, values) in spec['filters'].items():
                parts = [self.selection(field, {name: value}) for value in values]
                rows += parts
                added = sum(part['totalCount'] or 0 for part in parts)
                sums.append({'field': field, 'filter': name, 'sum': added, 'unfiltered': whole['totalCount'],
                             'problems': [] if added == whole['totalCount'] else ['the totals of %s add up to %d, not %s' % (name, added, whole['totalCount'])]})
        return rows, sums


def summary(rows, sums):
    failed = [row for row in rows + sums if row['problems']]
    return {'selections': len(rows), 'sums': len(sums), 'withProblems': len(failed),
            'totals': {row['field']: row['totalCount'] for row in rows if not row['filters']}}


def build_report(arm, rows, sums, calls, origin):
    return {'check': 'study2-graph-totals', 'arm': arm, 'origin': origin, 'toolCalls': calls,
            'inputs': {'totals_check.py': digest(__file__), 'graph_access.py': digest(REFERENCE / 'graph_access.py')},
            'summary': summary(rows, sums), 'selections': rows, 'sums': sums}


def outside_repository(path):
    path = Path(path).resolve()
    if path == REPO or REPO in path.parents:
        raise SystemExit('the report must be written outside the repository: %s' % path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--arm', required=True, choices=ARMS)
    parser.add_argument('--backend', required=True, choices=['simulated', 'real'])
    parser.add_argument('--config', help='the machine-local study config (for its dataset_fingerprint command); needed with --backend real')
    parser.add_argument('--output', help='write the JSON report here (outside the repository)')
    args = parser.parse_args(argv)
    output = outside_repository(args.output) if args.output else None
    import run_reference
    module = run_reference.arm_module(args.arm)
    config = json.loads(Path(args.config).read_text(encoding='utf-8')) if args.config else None
    origin, problems = run_reference.verify_backend(module.ARM, args.backend, config=config)
    if problems:
        print('the running stack is not the declared %s backend of %s:\n- %s' % (args.backend, module.NAME, '\n- '.join(problems)))
        return 4
    sys.path.insert(0, str(REPO / 'study' / 'harness'))
    from mcp_client import McpSession
    with McpSession(origin['mcpUrl'], 'study2-totals-check-%s' % module.ARM) as session:
        names = {t['name'] for t in session.tools()}
        if names != set(module.TOOLS):
            raise SystemExit('the server at %s offers %s, not the tools of %s' % (origin['mcpUrl'], sorted(names), module.NAME))
        checker = Checker(module.ACCESS(session.call))
        rows, sums = checker.run()
    report = build_report(module.ARM, rows, sums, checker.calls, origin)
    if output:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for row in rows + sums:
        for problem in row['problems']:
            print('%s %s: %s' % (row['field'], json.dumps(row.get('filters', row.get('filter'))), problem))
    print('%s (%s, %s): %s' % (module.NAME, module.ARM, args.backend, json.dumps(report['summary'])))
    return 0 if not report['summary']['withProblems'] else 1


if __name__ == '__main__':
    sys.exit(main())
