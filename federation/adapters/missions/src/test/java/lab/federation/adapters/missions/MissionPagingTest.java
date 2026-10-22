package lab.federation.adapters.missions;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import lab.federation.common.ErrorCode;
import lab.federation.common.Outcome;
import org.junit.jupiter.api.Test;

/** The translation of offset and limit into the service's pages, against an in-memory service that behaves as the contract says. */
class MissionPagingTest {
    /** A service holding {@code total} missions numbered 0 to total-1, paging as the contract says; it records each call. */
    private static final class FakeService implements MissionPaging.Fetch {
        final int total;
        final List<String> calls = new ArrayList<>();
        int failAtCall = -1;
        Outcome<MissionXml.Page> failure;

        FakeService(int total) {
            this.total = total;
        }

        @Override
        public Outcome<MissionXml.Page> page(long page, int pageSize) {
            calls.add(page + "x" + pageSize);
            if (calls.size() - 1 == failAtCall) {
                return failure;
            }
            assertThat(pageSize).isBetween(1, 50);
            long from = (page - 1) * pageSize;
            List<Map<String, Object>> missions = new ArrayList<>();
            for (long index = from; index < Math.min(total, from + pageSize); index++) {
                Map<String, Object> mission = new LinkedHashMap<>();
                mission.put("missionId", "ST-" + index);
                missions.add(mission);
            }
            return Outcome.resolved(new MissionXml.Page(page, pageSize, total, (total + pageSize - 1) / pageSize, missions));
        }
    }

    private static List<String> ids(MissionPaging.Result result) {
        return result.missions().stream().map(mission -> (String) mission.get("missionId")).toList();
    }

    private static List<String> range(int from, int to) {
        List<String> ids = new ArrayList<>();
        for (int index = from; index < to; index++) {
            ids.add("ST-" + index);
        }
        return ids;
    }

    @Test
    void theDefaultWindowIsOneCallOfTwentyFromPageOne() {
        FakeService service = new FakeService(31);
        MissionPaging.Result result = MissionPaging.fetch(0, 20, service);
        assertThat(ids(result)).isEqualTo(range(0, 20));
        assertThat(service.calls).containsExactly("1x20");
    }

    @Test
    void aWindowThatIsAMultipleOfTheLimitIsOneCall() {
        FakeService service = new FakeService(95);
        assertThat(ids(MissionPaging.fetch(40, 20, service))).isEqualTo(range(40, 60));
        assertThat(service.calls).containsExactly("3x20");
    }

    @Test
    void anOddOffsetNeedsTheCoveringPagesAndTheSliceIsExact() {
        FakeService service = new FakeService(95);
        MissionPaging.Result result = MissionPaging.fetch(45, 20, service);
        assertThat(ids(result)).isEqualTo(range(45, 65));
        assertThat(service.calls).as("one call of 22 covers rows 44 to 65, the fewest rows that cover the window with one call").containsExactly("3x22");
        service = new FakeService(95);
        assertThat(ids(MissionPaging.fetch(7, 20, service))).isEqualTo(range(7, 27));
        assertThat(service.calls).hasSize(1);
        service = new FakeService(95);
        assertThat(ids(MissionPaging.fetch(1, 3, service))).isEqualTo(range(1, 4));
    }

    @Test
    void aLimitAboveFiftyTakesTwoCalls() {
        FakeService service = new FakeService(95);
        assertThat(ids(MissionPaging.fetch(0, 75, service))).isEqualTo(range(0, 75));
        assertThat(service.calls).hasSize(2);
        service = new FakeService(200);
        assertThat(ids(MissionPaging.fetch(0, 100, service))).isEqualTo(range(0, 100));
        assertThat(service.calls).containsExactly("1x50", "2x50");
        service = new FakeService(200);
        assertThat(ids(MissionPaging.fetch(10, 75, service))).isEqualTo(range(10, 85));
        assertThat(service.calls).hasSize(2);
    }

    @Test
    void theLastPageIsShortAndEndsTheFetch() {
        FakeService service = new FakeService(31);
        assertThat(ids(MissionPaging.fetch(30, 20, service))).isEqualTo(range(30, 31));
        assertThat(service.calls).hasSize(1);
        service = new FakeService(31);
        assertThat(ids(MissionPaging.fetch(0, 100, service))).isEqualTo(range(0, 31));
        assertThat(service.calls).as("the first call is short, so the second is not made").containsExactly("1x50");
    }

    @Test
    void anOffsetAtOrPastTheEndIsAnEmptyListWithOneCall() {
        for (int offset : new int[] {31, 32, 1000, Integer.MAX_VALUE}) {
            FakeService service = new FakeService(31);
            MissionPaging.Result result = MissionPaging.fetch(offset, 20, service);
            assertThat(result.failed()).isFalse();
            assertThat(result.missions()).as("offset " + offset).isEmpty();
            assertThat(service.calls).hasSize(1);
        }
        FakeService empty = new FakeService(0);
        assertThat(MissionPaging.fetch(0, 20, empty).missions()).isEmpty();
    }

    @Test
    void everyWindowOfEveryLimitMatchesTheSliceWithTheFewestCalls() {
        for (int total : new int[] {0, 1, 31, 50, 51, 95, 150}) {
            for (int offset = 0; offset <= 160; offset++) {
                for (int limit : new int[] {1, 2, 3, 7, 10, 19, 20, 21, 33, 49, 50, 51, 64, 75, 99, 100}) {
                    FakeService service = new FakeService(total);
                    MissionPaging.Result result = MissionPaging.fetch(offset, limit, service);
                    String where = "total " + total + " offset " + offset + " limit " + limit;
                    assertThat(ids(result)).as(where).isEqualTo(range(Math.min(offset, total), Math.min(total, offset + limit)));
                    MissionPaging.Plan plan = MissionPaging.plan(offset, limit);
                    assertThat((long) service.calls.size()).as(where).isLessThanOrEqualTo(plan.calls());
                    assertThat(plan.calls()).as(where).isLessThanOrEqualTo(3);
                    if (limit <= 50) {
                        assertThat(plan.calls()).as(where).isLessThanOrEqualTo(2);
                    }
                    if (offset % limit == 0 && limit <= 50) {
                        assertThat(plan.calls()).as(where).isEqualTo(1);
                    }
                    assertThat(plan.firstPage() * plan.pageSize()).as(where).isGreaterThan(offset);
                    assertThat(plan.lastPage() * plan.pageSize()).as(where).isGreaterThanOrEqualTo((long) offset + limit);
                }
            }
        }
    }

    @Test
    void theFirstFailedCallEndsTheFetchAndTheWholeListIsNull() {
        FakeService service = new FakeService(200);
        service.failAtCall = 0;
        service.failure = Outcome.unavailable(ErrorCode.SERVICE_UNAVAILABLE, "down");
        MissionPaging.Result first = MissionPaging.fetch(0, 100, service);
        assertThat(first.failed()).isTrue();
        assertThat(first.missions()).isNull();
        assertThat(first.failure().errorCode()).isEqualTo(ErrorCode.SERVICE_UNAVAILABLE);
        assertThat(service.calls).as("no call after the failed one").hasSize(1);

        service = new FakeService(200);
        service.failAtCall = 1;
        service.failure = Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "bad");
        MissionPaging.Result second = MissionPaging.fetch(0, 100, service);
        assertThat(second.failed()).isTrue();
        assertThat(second.missions()).isNull();
        assertThat(second.failure().errorCode()).isEqualTo(ErrorCode.UPSTREAM_BAD_RESPONSE);
        assertThat(service.calls).hasSize(2);
    }

    @Test
    void aPageThatEchoesAnotherPageOrSizeOrTooManyRowsIsABadResponse() {
        MissionPaging.Fetch wrongPage = (page, size) -> Outcome.resolved(new MissionXml.Page(page + 1, size, 5, 1, List.of()));
        MissionPaging.Fetch wrongSize = (page, size) -> Outcome.resolved(new MissionXml.Page(page, size == 20 ? 19 : 20, 5, 1, List.of()));
        MissionPaging.Fetch tooMany = (page, size) -> Outcome.resolved(new MissionXml.Page(page, size, 5, 1,
                List.of(Map.of("missionId", "a"), Map.of("missionId", "b"), Map.of("missionId", "c")))) ;
        for (MissionPaging.Fetch fetch : List.of(wrongPage, wrongSize)) {
            MissionPaging.Result result = MissionPaging.fetch(0, 20, fetch);
            assertThat(result.failed()).isTrue();
            assertThat(result.failure().errorCode()).isEqualTo(ErrorCode.UPSTREAM_BAD_RESPONSE);
        }
        MissionPaging.Result result = MissionPaging.fetch(0, 2, tooMany);
        assertThat(result.failed()).isTrue();
    }

    @Test
    void theHugestOffsetStaysInArithmeticRange() {
        MissionPaging.Plan plan = MissionPaging.plan(Integer.MAX_VALUE, 100);
        assertThat(plan.pageSize()).isBetween(1, 50);
        assertThat(plan.firstPage()).isPositive();
        assertThat(plan.start()).isLessThanOrEqualTo(Integer.MAX_VALUE);
    }
}
