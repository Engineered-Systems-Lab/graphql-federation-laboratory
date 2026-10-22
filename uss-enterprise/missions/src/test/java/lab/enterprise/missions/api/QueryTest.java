package lab.enterprise.missions.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.math.BigInteger;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import lab.enterprise.missions.ApiException;
import lab.enterprise.missions.xml.Classification;
import lab.enterprise.missions.xml.IssuingAuthority;
import lab.enterprise.missions.xml.LocationType;
import lab.enterprise.missions.xml.MissionType;
import lab.enterprise.missions.xml.Status;
import org.junit.jupiter.api.Test;

class QueryTest {
    private static Map<String, List<String>> q(String... pairs) {
        Map<String, List<String>> map = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) map.computeIfAbsent(pairs[i], k -> new java.util.ArrayList<>()).add(pairs[i + 1]);
        return map;
    }

    private static void invalid(Map<String, List<String>> parameters) {
        ApiException e = assertThrows(ApiException.class, () -> Query.missions(parameters));
        assertEquals(400, e.status);
        assertEquals("INVALID_REQUEST", e.code);
    }

    @Test void defaults() {
        var query = Query.missions(q());
        assertTrue(query.filters().isEmpty());
        assertEquals("1", query.paging().pageText());
        assertEquals(20, query.paging().pageSize());
    }

    @Test void everyFilterIsAccepted() {
        var query = Query.missions(q("type", "MAINTENANCE", "classification", "TOP_SECRET", "status", "ACTIVE", "priority", "5",
                "issuingAuthority", "FEDERATION_COUNCIL", "commandingOfficerId", "C-85", "assignedCrewId", "C-1",
                "assignedAssetId", "SH-17", "locationType", "DEEP_SPACE", "page", "3", "pageSize", "50"));
        assertEquals(9, query.filters().size());
        assertEquals(BigInteger.valueOf(3), query.paging().page());
        assertEquals(50, query.paging().pageSize());
    }

    @Test void hugePageIsValidAndKeepsItsText() {
        var query = Query.missions(q("page", "99999999999999999999999999"));
        assertEquals("99999999999999999999999999", query.paging().pageText());
    }

    @Test void rejectsInvalidRecognizedValues() {
        invalid(q("type", "ENGINEERING"));
        invalid(q("type", "exploration"));
        invalid(q("status", ""));
        invalid(q("priority", "0"));
        invalid(q("priority", "6"));
        invalid(q("commandingOfficerId", "P-1"));
        invalid(q("assignedCrewId", "C-01"));
        invalid(q("assignedAssetId", "sh-17"));
        invalid(q("assignedAssetId", "S-1"));
        invalid(q("page", "0"));
        invalid(q("page", "01"));
        invalid(q("page", "-1"));
        invalid(q("pageSize", "0"));
        invalid(q("pageSize", "51"));
        invalid(q("pageSize", "05"));
    }

    @Test void rejectsUnknownAndRepeatedParameters() {
        invalid(q("participantId", "P-1"));
        invalid(q("sort", "stardate"));
        invalid(q("status", "ACTIVE", "status", "ACTIVE"));
        invalid(q("page", "1", "page", "2"));
        invalid(q("pageSize", "5", "pageSize", "5"));
        invalid(q("bad\u0001name", "x"));
    }

    @Test void changesAcceptOnlyPaging() {
        assertEquals("2", Query.changes(q("page", "2")).pageText());
        assertThrows(ApiException.class, () -> Query.changes(q("status", "ACTIVE")));
        assertThrows(ApiException.class, () -> Query.changes(q("page", "1", "page", "1")));
    }

    @Test void missionIdGrammar() {
        assertTrue(Query.validMissionId("ST-00000LD4O"));
        assertTrue(Query.validMissionId("ST-ZZZZZZZZZ"));
        assertFalse(Query.validMissionId("st-00000LD4O"));
        assertFalse(Query.validMissionId("ST-00000LD4"));
        assertFalse(Query.validMissionId("ST-00000LD4OO"));
        assertFalse(Query.validMissionId("ST-0000lD4OO"));
        assertFalse(Query.validMissionId(" ST-00000LD4O"));
    }

    @Test void vocabularyEqualsTheFrozenContract() {
        assertEquals(values(MissionType.values()), new TreeSet<>(Query.MISSION_TYPES));
        assertEquals(values(Classification.values()), new TreeSet<>(Query.CLASSIFICATIONS));
        assertEquals(values(Status.values()), new TreeSet<>(Query.STATUSES));
        assertEquals(values(LocationType.values()), new TreeSet<>(Query.LOCATION_TYPES));
        assertEquals(values(IssuingAuthority.values()), new TreeSet<>(Query.AUTHORITIES));
    }

    private static Set<String> values(Enum<?>[] constants) {
        Set<String> out = new TreeSet<>();
        Arrays.stream(constants).forEach(c -> {
            try { out.add((String) c.getClass().getMethod("value").invoke(c)); } catch (ReflectiveOperationException e) { throw new AssertionError(e); }
        });
        return out;
    }
}
