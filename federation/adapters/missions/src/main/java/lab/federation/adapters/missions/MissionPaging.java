package lab.federation.adapters.missions;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import lab.federation.common.ErrorCode;
import lab.federation.common.Outcome;
import lab.federation.common.Resolution;

/**
 * Translates the graph's offset and limit into the service's page and pageSize (1 to 50 per call) and slices the answer.
 *
 * The service numbers pages from 1 with a fixed size, so the window [offset, offset + limit) is covered by whole pages. The adapter
 * chooses the page size from 1 to 50 that covers the window with the FEWEST calls, then with the fewest rows fetched, then the
 * larger size: a limit of 20 at offset 0 is one call of 20, an offset that is not a multiple of the limit often still fits one
 * call of another size, and a limit above 50 takes two calls whenever any size covers the window with two and three otherwise.
 * An offset past the end gives an empty list (the service answers a valid page beyond the end with no missions); a short page
 * ends the fetch, because the rows after it do not exist.
 *
 * All or nothing: the first failed call ends the fetch and the whole list is null; no later call is made.
 *
 * The page field (missionsPage) makes exactly the same calls and also reads the count metadata of every answer: the total is the
 * service's totalCount, never a count of fetched rows. A page is a live view with no snapshot guarantee, like the service's own pages:
 * equal counts across the calls of one page do not prove that the missions did not change between them. The deprecated list
 * (missions) does not check the counts and answers exactly as before.
 */
final class MissionPaging {
    static final int SERVICE_MAX = 50;

    private MissionPaging() {
    }

    /** The page size and the first and last page (numbered from 1) that cover the window. */
    record Plan(int pageSize, long firstPage, long lastPage) {
        long calls() {
            return lastPage - firstPage + 1;
        }

        /** The index, in the service's whole ordering, of the first row of the first page. */
        long start() {
            return (firstPage - 1) * pageSize;
        }
    }

    /** One call to the service for a page: the page, or the failure. */
    interface Fetch {
        Outcome<MissionXml.Page> page(long page, int pageSize);
    }

    /**
     * The missions of the window and, when the counts were checked, the service's total of matching missions; or, when a call failed
     * or its count metadata cannot be used, the failed outcome and no list.
     */
    record Result(List<Map<String, Object>> missions, Long totalCount, Outcome<MissionXml.Page> failure) {
        boolean failed() {
            return failure != null;
        }
    }

    static Plan plan(int offset, int limit) {
        long last = (long) offset + limit - 1;
        Plan best = null;
        for (int size = SERVICE_MAX; size >= 1; size--) {
            Plan candidate = new Plan(size, offset / size + 1L, last / size + 1L);
            if (best == null || candidate.calls() < best.calls()
                    || (candidate.calls() == best.calls() && candidate.calls() * candidate.pageSize() < best.calls() * best.pageSize())) {
                best = candidate;
            }
        }
        return best;
    }

    /** The window for the deprecated list: the count metadata is not checked. */
    static Result fetch(int offset, int limit, Fetch fetch) {
        return fetch(offset, limit, fetch, false);
    }

    /** The window for the page field: the same calls, with the count metadata of every answer checked and the total kept. */
    static Result fetchCounted(int offset, int limit, Fetch fetch) {
        return fetch(offset, limit, fetch, true);
    }

    private static Result fetch(int offset, int limit, Fetch fetch, boolean counted) {
        Plan plan = plan(offset, limit);
        List<Map<String, Object>> rows = new ArrayList<>();
        Long total = null;
        for (long page = plan.firstPage(); page <= plan.lastPage(); page++) {
            Outcome<MissionXml.Page> outcome = fetch.page(page, plan.pageSize());
            if (outcome.resolution() != Resolution.RESOLVED) {
                return new Result(null, null, outcome);
            }
            MissionXml.Page answer = outcome.value();
            if (answer.page() != page || answer.pageSize() != plan.pageSize() || answer.missions().size() > plan.pageSize()) {
                return new Result(null, null, Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "The service answered another page than the one asked"));
            }
            if (counted) {
                String fault = countFault(answer, total);
                if (fault != null) {
                    return new Result(null, null, Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, COUNT_FAULT + fault));
                }
                total = answer.totalCount();
            }
            rows.addAll(answer.missions());
            if (answer.missions().size() < plan.pageSize()) {
                break;
            }
        }
        int from = (int) (offset - plan.start());
        int begin = Math.min(from, rows.size());
        int end = Math.min(from + limit, rows.size());
        return new Result(new ArrayList<>(rows.subList(begin, end)), total, null);
    }

    static final String COUNT_FAULT = "Missions service answered count metadata the adapter cannot use: ";

    /**
     * Why the count metadata of one answer cannot be used, or null. The total must be a whole number from 0 to 2147483647 (a GraphQL
     * Int; the parser already refused a missing, non-decimal or negative one), the same in every call of the page, totalPages must be
     * ceil(totalCount / pageSize) (0 when nothing matches), and the rows of the answer must be exactly min(pageSize, max(0, totalCount -
     * start)), where start is the position of the page's first row: this covers zero matches, pages beyond the end and the last page.
     */
    static String countFault(MissionXml.Page answer, Long previousTotal) {
        long total = answer.totalCount();
        if (total > Integer.MAX_VALUE) {
            return "totalCount is above 2147483647";
        }
        if (previousTotal != null && previousTotal != total) {
            return "the calls of one page gave different totalCount values";
        }
        long size = answer.pageSize();
        if (answer.totalPages() != (total + size - 1) / size) {
            return "totalPages does not match totalCount and pageSize";
        }
        long start = (answer.page() - 1) * size;
        if (answer.missions().size() != Math.min(size, Math.max(0, total - start))) {
            return "the number of missions on the page does not match totalCount";
        }
        return null;
    }
}
