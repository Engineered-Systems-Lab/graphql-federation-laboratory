"""The graph-arm totals check on an in-memory graph: no stack, no MCP server."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import totals_check  # noqa: E402


def dataset():
    missions, assets = [], []
    for index in range(237):
        missions.append({'missionId': 'ST-%09d' % index,
                         **{name: values[index % len(values)] for name, (_, values) in totals_check.LISTS['missionsPage']['filters'].items()}})
    for index in range(61):
        assets.append({'assetId': 'AST-%04d' % index,
                       **{name: values[(index * 7) % len(values)] for name, (_, values) in totals_check.LISTS['assetsPage']['filters'].items()}})
    return {'missions': missions, 'assets': assets}


class FakeGraph:
    """Answers the check's queries as an arm's access layer does (`query` returns the data object), with switches for each fault."""

    def __init__(self, fault=None):
        self.data, self.fault, self.roots = dataset(), fault, []

    def query(self, root, operation, text, variables):
        self.roots.append(root)
        field = re.search(r'\{ (\w+)\(', text).group(1)
        rows_name = field[:-4] if field.endswith('Page') else field
        filters = {k: v for k, v in variables.items() if k not in ('offset', 'limit')}
        rows = [r for r in self.data[rows_name] if all(r[k] == v for k, v in filters.items())]
        offset, limit = variables['offset'], variables.get('limit', 20)
        start = 0 if self.fault == 'ignores-offset' else offset
        window = rows[start:start + limit]
        key = 'missionId' if rows_name == 'missions' else 'assetId'
        items = [{key: r[key]} for r in window]
        if not field.endswith('Page'):
            if self.fault == 'list-differs' and offset == 0:
                items = items[::-1]
            return {field: items}
        total = len(rows)
        if self.fault == 'total-off' and not filters:
            total += 1
        has_more = offset + len(items) < total
        if self.fault == 'has-more' and not has_more:
            has_more = offset == 0 and bool(items)
        if self.fault == 'drifting-total' and offset > 0:
            total += 5
        if self.fault == 'ignores-offset':
            has_more = True
        return {field: {'items': items, 'totalCount': total, 'offset': offset, 'limit': limit, 'hasMore': has_more}}


def run(fault=None):
    graph = FakeGraph(fault)
    checker = totals_check.Checker(graph)
    rows, sums = checker.run()
    return graph, rows, sums, totals_check.summary(rows, sums)


class TheTotalsCheck(unittest.TestCase):
    def test_a_graph_whose_totals_equal_the_paged_counts_passes_every_selection_and_sum(self):
        graph, rows, sums, result = run()
        self.assertEqual(result['withProblems'], 0, [r for r in rows + sums if r['problems']])
        self.assertEqual(result['totals'], {'missionsPage': 237, 'assetsPage': 61})
        expected = 2 + sum(len(values) for spec in totals_check.LISTS.values() for _, values in spec['filters'].values())
        self.assertEqual(result['selections'], expected, 'the unfiltered selection and every value of every enum filter')
        self.assertEqual(result['sums'], sum(len(spec['filters']) for spec in totals_check.LISTS.values()))
        self.assertEqual(set(graph.roots), {'missions', 'assets'}, 'every query goes to the owning service of the access layer')
        whole = next(r for r in rows if r['field'] == 'missionsPage' and not r['filters'])
        self.assertEqual((whole['paged'], whole['pages']), (237, 3))

    def test_a_total_that_is_not_the_paged_count_is_a_problem(self):
        _, rows, sums, result = run('total-off')
        whole = next(r for r in rows if r['field'] == 'missionsPage' and not r['filters'])
        self.assertTrue(any('rows paged, totalCount' in p for p in whole['problems']), whole)
        self.assertTrue(any(s['problems'] for s in sums), 'the filtered totals no longer add up to the unfiltered one')
        self.assertGreater(result['withProblems'], 0)

    def test_a_wrong_has_more_a_drifting_total_and_items_that_differ_from_the_list_are_problems(self):
        for fault, words in (('has-more', 'hasMore'), ('drifting-total', 'gives totalCount'), ('list-differs', 'deprecated list')):
            with self.subTest(fault=fault):
                _, rows, _, result = run(fault)
                self.assertGreater(result['withProblems'], 0)
                self.assertTrue(any(words in p for r in rows for p in r['problems']), fault)

    def test_a_graph_that_ignores_the_offset_ends_the_traversals_with_a_problem_instead_of_running_on(self):
        graph, rows, sums, result = run('ignores-offset')
        self.assertLess(len(graph.roots), 1000, 'every traversal is bounded')
        whole = next(r for r in rows if r['field'] == 'missionsPage' and not r['filters'])
        self.assertTrue(any('repeats rows' in p for p in whole['problems']), whole)
        self.assertGreater(result['withProblems'], 0)

    def test_a_deprecated_list_that_repeats_its_rows_or_pages_past_the_total_is_a_problem_and_ends(self):
        checker = totals_check.Checker(FakeGraph('ignores-offset'))
        ids, problem = checker.deprecated_list('missionsPage', {}, 237)
        self.assertEqual(len(ids), 100)
        self.assertIn('repeats rows', problem)
        ids, problem = totals_check.Checker(FakeGraph()).deprecated_list('missionsPage', {}, 150)
        self.assertIn('more than the 2 pages', problem, 'the list holds more full pages than the total allows')
        self.assertEqual(totals_check.max_pages(0), 1)
        self.assertEqual(totals_check.max_pages(None), 1)

    def test_the_page_at_the_total_is_checked_as_empty(self):
        checker = totals_check.Checker(FakeGraph())
        self.assertEqual(checker.beyond_end('assetsPage', 61), [])
        self.assertTrue(checker.beyond_end('assetsPage', 60))

    def test_the_report_binds_this_script_and_the_access_layer_it_calls_and_is_written_outside_the_repository(self):
        _, rows, sums, _ = run()
        report = totals_check.build_report('gamma', rows, sums, 10, {'verified': True})
        self.assertEqual(sorted(report['inputs']), ['graph_access.py', 'totals_check.py'])
        self.assertTrue(all(len(value) == 64 for value in report['inputs'].values()))
        with self.assertRaises(SystemExit):
            totals_check.outside_repository(totals_check.REPO / 'report.json')


if __name__ == '__main__':
    unittest.main()
