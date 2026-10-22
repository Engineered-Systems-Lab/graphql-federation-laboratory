package lab.enterprise.missions.repository;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.math.BigInteger;
import lab.enterprise.missions.api.Query;
import org.junit.jupiter.api.Test;

class PagingTest {
    private static long offset(String page, int size, long total) {
        return MissionRepository.offset(new Query.Paging(page, new BigInteger(page), size), total);
    }

    @Test void firstPageStartsAtZero() { assertEquals(0, offset("1", 20, 31)); }

    @Test void laterPagesAdvanceByPageSize() {
        assertEquals(20, offset("2", 20, 31));
        assertEquals(30, offset("4", 10, 31));
    }

    @Test void pagesBeyondTheEndAreEmptyNotErrors() {
        assertEquals(-1, offset("3", 20, 31));
        assertEquals(-1, offset("1", 20, 0));
        assertEquals(-1, offset("99999999999999999999999999", 50, 31));
    }

    @Test void exactMultipleHasNoExtraPage() {
        assertEquals(20, offset("2", 20, 40));
        assertEquals(-1, offset("3", 20, 40));
    }
}
