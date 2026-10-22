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

    /** The missions of the window, or, when a call failed, that call's failed outcome and no list. */
    record Result(List<Map<String, Object>> missions, Outcome<MissionXml.Page> failure) {
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

    static Result fetch(int offset, int limit, Fetch fetch) {
        Plan plan = plan(offset, limit);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (long page = plan.firstPage(); page <= plan.lastPage(); page++) {
            Outcome<MissionXml.Page> outcome = fetch.page(page, plan.pageSize());
            if (outcome.resolution() != Resolution.RESOLVED) {
                return new Result(null, outcome);
            }
            MissionXml.Page answer = outcome.value();
            if (answer.page() != page || answer.pageSize() != plan.pageSize() || answer.missions().size() > plan.pageSize()) {
                return new Result(null, Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "The service answered another page than the one asked"));
            }
            rows.addAll(answer.missions());
            if (answer.missions().size() < plan.pageSize()) {
                break;
            }
        }
        int from = (int) (offset - plan.start());
        int begin = Math.min(from, rows.size());
        int end = Math.min(from + limit, rows.size());
        return new Result(new ArrayList<>(rows.subList(begin, end)), null);
    }
}
