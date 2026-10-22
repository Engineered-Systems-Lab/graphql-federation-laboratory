package lab.enterprise.crew;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.*;
import java.util.concurrent.atomic.AtomicLong;
import lab.enterprise.crew.contract.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class DatasetServiceTest {
    @Test void aggregatePaginationFiltersAndIdentity() throws Exception {
        var dataset = Dataset.load("crew-v1-large-003");
        var service = new CrewService(dataset, CrewService.Profile.normal);
        var records = dataset.records();
        var allIds = records.stream().map(CrewMember::getCrewId).toList();
        var defaults = service.listCrewMembers(new ListCrewMembersRequestType());
        assertEquals(800, defaults.getTotalCount()); assertEquals(20, defaults.getCrewMember().size());
        for (int limit : new int[]{1, 20, 100}) {
            var ids = new java.util.ArrayList<String>();
            for (int offset = 0; offset < 800; offset += limit) {
                var query = new ListCrewMembersRequestType(); query.setOffset(offset); query.setLimit(limit);
                var page = service.listCrewMembers(query);
                assertEquals(800, page.getTotalCount()); assertEquals(offset + limit < 800, page.isHasMore());
                ids.addAll(page.getCrewMember().stream().map(CrewMember::getCrewId).toList());
            }
            assertEquals(allIds, ids);
        }
        for (int offset : new int[]{95, 199, 695, 799, 800, 801, Integer.MAX_VALUE}) {
            var query = new ListCrewMembersRequestType(); query.setOffset(offset); query.setLimit(20);
            var page = service.listCrewMembers(query);
            assertEquals(allIds.stream().skip(offset).limit(20).toList(), page.getCrewMember().stream().map(CrewMember::getCrewId).toList());
        }
        var departments = new java.util.ArrayList<Department>(java.util.List.of(Department.values())); departments.add(null);
        var statuses = new java.util.ArrayList<DutyStatus>(java.util.List.of(DutyStatus.values())); statuses.add(null);
        for (var department : departments) for (var status : statuses) {
            var expected = records.stream().filter(m -> department == null || m.getDepartment() == department)
                .filter(m -> status == null || m.getDutyStatus() == status).map(CrewMember::getCrewId).toList();
            var query = new ListCrewMembersRequestType(); query.setDepartment(department); query.setDutyStatus(status);
            query.setOffset(5); query.setLimit(100);
            var actual = service.listCrewMembers(query);
            assertEquals(expected.size(), actual.getTotalCount());
            assertEquals(expected.stream().skip(5).limit(100).toList(), actual.getCrewMember().stream().map(CrewMember::getCrewId).toList());
        }
        assertEquals(719, records.stream().filter(m -> m.getDutyStatus() == DutyStatus.ACTIVE).count());
        assertEquals(40, records.stream().filter(m -> m.getDutyStatus() == DutyStatus.ON_LEAVE).count());
        assertEquals(41, records.stream().filter(m -> m.getDutyStatus() == DutyStatus.INACTIVE).count());
        for (var member : records) {
            var get = new GetCrewMemberRequestType(); get.setCrewId(member.getCrewId());
            var returned = service.getCrewMember(get).getCrewMember();
            assertEquals(member.getDisplayName(), returned.getDisplayName());
            assertEquals(member.getSupervisorCrewId(), returned.getSupervisorCrewId());
            returned.setDisplayName("mutated");
            assertEquals(member.getDisplayName(), service.getCrewMember(get).getCrewMember().getDisplayName());
        }
        var byId = records.stream().collect(java.util.stream.Collectors.toMap(CrewMember::getCrewId, m -> m));
        assertEquals(Department.SCIENCE, byId.get("CRW-1050").getDepartment());
        assertEquals("Science Department Lead", byId.get("CRW-1050").getPositionTitle());
        assertEquals("CRW-1050", byId.get("CRW-1055").getSupervisorCrewId());
        assertNull(byId.get("CRW-1056").getSupervisorCrewId());
        assertEquals("Miles O'Brien", byId.get("CRW-1100").getDisplayName());
        assertEquals("Sonya Gomez", byId.get("CRW-1101").getDisplayName());
        for (String version : new String[]{"crew-v1-small-001", "crew-v1-small-002"})
            assertEquals(Department.OPERATIONS, Dataset.load(version).records().get(3).getDepartment());
        for (int limit : new int[]{0, 101}) {
            var query = new ListCrewMembersRequestType(); query.setLimit(limit);
            assertEquals(FaultCode.INVALID_REQUEST, assertThrows(CrewServiceFaultMessage.class,
                () -> service.listCrewMembers(query)).getFaultInfo().getCode());
        }
    }
    @ParameterizedTest @ValueSource(strings = {"duplicate-id", "dangling", "self-reference", "cycle", "count-mismatch"})
    void rejectsUnreadyDatasets(String name) {
        assertThrows(Exception.class, () -> Dataset.parse(Files.readAllBytes(Path.of("fixtures/negative/datasets/" + name + ".xml"))));
    }
    @ParameterizedTest @ValueSource(strings = {"crew-v1-small-001", "crew-v1-small-002"})
    void checkoutLineEndingsPassRealLoader(String version) throws Exception {
        byte[] original = Files.readAllBytes(Path.of("fixtures/canonical/" + version + ".xml"));
        String lf = new String(original, java.nio.charset.StandardCharsets.UTF_8).replace("\r\n", "\n");
        String crlf = lf.replace("\n", "\r\n");
        // Reproduce 002's known 113 CRLF + one bare LF even on an all-LF checkout.
        String mixed = crlf.replaceFirst("\r\n", "\n");
        assertTrue(mixed.contains("\r\n"));
        assertEquals(1, mixed.replace("\r\n", "").chars().filter(c -> c == '\n').count());
        if (version.equals("crew-v1-small-002")) assertEquals(113, mixed.split("\r\n", -1).length - 1);
        for (byte[] representation : new byte[][] {original, lf.getBytes(java.nio.charset.StandardCharsets.UTF_8),
                crlf.getBytes(java.nio.charset.StandardCharsets.UTF_8), mixed.getBytes(java.nio.charset.StandardCharsets.UTF_8)}) {
            byte[] before = representation.clone();
            var dataset = Dataset.load(version, representation);
            assertEquals(version, dataset.version);
            assertEquals(version.endsWith("001") ? 6 : 12, dataset.records().size());
            assertEquals("Jean-Luc Picard", dataset.records().get(0).getDisplayName());
            assertArrayEquals(before, representation, "Hashing must not mutate parser input");
        }
    }
    @ParameterizedTest @ValueSource(strings = {"crew-v1-small-001", "crew-v1-small-002"})
    void realLoaderRejectsContentChanges(String version) throws Exception {
        String lf = Files.readString(Path.of("fixtures/canonical/" + version + ".xml")).replace("\r\n", "\n");
        for (String changed : new String[] {lf.replace("Jean-Luc Picard", "Jean-Luc Picaro"),
                lf.replace("Jean-Luc Picard", " Jean-Luc Picard"), lf.replaceFirst("\n", "\r"), lf + "\r"}) {
            var failure = assertThrows(IllegalStateException.class,
                () -> Dataset.load(version, changed.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            assertEquals("Immutable dataset hash mismatch", failure.getMessage());
        }
    }
    @Test void registeredSnapshotsAreSeparateAndDefensivelyCopied() throws Exception {
        var first = Dataset.load("crew-v1-small-001"); var latest = Dataset.load(Dataset.DEFAULT_VERSION);
        assertEquals(6, first.records().size()); assertEquals(12, latest.records().size());
        latest.records().get(0).setDisplayName("changed");
        assertEquals("Jean-Luc Picard", latest.records().get(0).getDisplayName());
        assertThrows(IllegalArgumentException.class, () -> Dataset.load("../validation/crew-v1-edge-001"));
    }
    @Test void edgeDatasetPreservesIdentityTextAndReporting() throws Exception {
        var data = Dataset.parse(Files.readAllBytes(Path.of("fixtures/validation/crew-v1-edge-001.xml")));
        assertEquals("CRW-0007", data.records().get(0).getCrewId());
        assertTrue(data.records().stream().anyMatch(m -> m.getPositionTitle().equals("R&D <Systems>")));
        assertEquals("  Research Assistant  ", data.records().get(1).getPositionTitle());
        assertEquals(2, data.records().stream().filter(m -> m.getDisplayName().equals("Alex Smith")).count());
    }
    @Test void exactInjectedDelayAndInvalidRequestPrecedence() throws Exception {
        var requested = new AtomicLong();
        var service = new CrewService(Dataset.load(Dataset.DEFAULT_VERSION), CrewService.Profile.slow, requested::addAndGet);
        var request = new GetCrewMemberRequestType(); request.setCrewId("CRW-0000");
        assertEquals(FaultCode.INVALID_REQUEST, assertThrows(CrewServiceFaultMessage.class, () -> service.getCrewMember(request)).getFaultInfo().getCode());
        assertEquals(0, requested.get());
        request.setCrewId("CRW-9999");
        assertEquals(FaultCode.CREW_NOT_FOUND, assertThrows(CrewServiceFaultMessage.class, () -> service.getCrewMember(request)).getFaultInfo().getCode());
        assertEquals(2000, requested.get());
        service.listCrewMembers(new ListCrewMembersRequestType()); assertEquals(4000, requested.get());
    }
    @Test void unexpectedErrorBecomesSanitizedInternalError() throws Exception {
        var service = new CrewService(Dataset.load(Dataset.DEFAULT_VERSION), CrewService.Profile.slow,
            ignored -> { throw new IllegalStateException("secret internal diagnostics"); });
        var fault = assertThrows(CrewServiceFaultMessage.class, () -> service.listCrewMembers(new ListCrewMembersRequestType()));
        assertEquals(FaultCode.INTERNAL_ERROR, fault.getFaultInfo().getCode());
        assertNull(fault.getFaultInfo().getField()); assertFalse(fault.getMessage().contains("secret"));
    }
    @Test void javaSchemaCountsSupplementaryXmlCharacters() throws Exception {
        String xml = Files.readString(Path.of("fixtures/canonical/crew-v1-small-001.xml"));
        String boundary = xml.replace("Jean-Luc Picard", "\uD83D\uDE80".repeat(100));
        assertDoesNotThrow(() -> Dataset.parse(boundary.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        String tooLong = xml.replace("Jean-Luc Picard", "\uD83D\uDE80".repeat(101));
        assertThrows(Exception.class, () -> Dataset.parse(tooLong.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
    }
}
