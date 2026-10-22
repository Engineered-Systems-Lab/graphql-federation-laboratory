package lab.federation.adapters.missions;

import static org.assertj.core.api.Assertions.assertThat;

import graphql.ExecutionInput;
import java.io.IOException;
import java.io.InputStream;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import lab.federation.common.HttpResult;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.graphql.execution.GraphQlSource;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * The adapter against a stub of the Missions service that serves the real contract fixtures and the released dataset 1.0: the
 * mission and its fields, not-found as data, the failures and their codes, the paging translation, the all-or-nothing rule, the
 * asset reference stubs and the Federation entry points.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@SuppressWarnings("unchecked")
class MissionsAdapterTest {
    private static final StubMissions STUB = start();
    private static final List<String> BLOCKS = StubMissions.releaseBlocks();

    private static StubMissions start() {
        try {
            return new StubMissions();
        } catch (IOException error) {
            throw new IllegalStateException(error);
        }
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("missions.service-url", STUB::url);
        registry.add("missions.connect-timeout-ms", () -> "300");
        registry.add("missions.read-timeout-ms", () -> "500");
    }

    @AfterAll
    static void stop() {
        STUB.close();
    }

    @Autowired
    GraphQlSource source;

    @BeforeEach
    void reset() {
        STUB.reset();
    }

    // ---- helpers ---------------------------------------------------------------------------------------------------

    private Map<String, Object> run(String query, Map<String, Object> variables) {
        return source.graphQl().execute(ExecutionInput.newExecutionInput(query).variables(variables).build()).toSpecification();
    }

    private Map<String, Object> run(String query) {
        return run(query, Map.of());
    }

    private static Map<String, Object> data(Map<String, Object> result) {
        return (Map<String, Object>) result.get("data");
    }

    private static List<Map<String, Object>> errors(Map<String, Object> result) {
        return result.get("errors") == null ? List.of() : (List<Map<String, Object>>) result.get("errors");
    }

    private static String code(Map<String, Object> error) {
        return (String) ((Map<String, Object>) error.get("extensions")).get("code");
    }

    private static List<String> codes(Map<String, Object> result) {
        return errors(result).stream().map(MissionsAdapterTest::code).toList();
    }

    private static List<String> ids(Map<String, Object> result) {
        return ((List<Map<String, Object>>) data(result).get("missions")).stream().map(mission -> (String) mission.get("missionId")).toList();
    }

    private static List<String> idsOf(List<String> blocks) {
        return blocks.stream().map(block -> StubMissions.field(block, "missionId")).toList();
    }

    private static List<String> members(String block, String name) {
        List<String> found = new ArrayList<>();
        Matcher matcher = Pattern.compile("<" + name + ">(.*?)</" + name + ">").matcher(block);
        while (matcher.find()) {
            found.add(matcher.group(1));
        }
        return found;
    }

    private static final String ALL_FIELDS = "missionId title type classification status priority stardate durationHours objective "
            + "location { type name coordinates travelVector } issuingAuthority commandingOfficerId assignedCrewIds participantIds "
            + "assignedAssetIds estimatedCostCredits actualCostCredits outcome lastUpdated";

    /** A minimal valid mission of the contract, with the given id, for the synthetic pages. */
    private static String missionXml(String id) {
        return "<mission><missionId>" + id + "</missionId><title>Synthetic " + id + "</title><type>EXPLORATION</type><classification>UNCLASSIFIED</classification>"
                + "<status>PLANNED</status><priority>3</priority><stardate>43125.80</stardate><durationHours>1</durationHours><objective>Synthetic.</objective>"
                + "<location><type>OTHER</type><name>Somewhere</name></location><issuingAuthority>FEDERATION_COUNCIL</issuingAuthority>"
                + "<assignedCrewIds/><participantIds/><assignedAssetIds/><lastUpdated>2366-10-14T19:42:31.472Z</lastUpdated></mission>";
    }

    private static String pageXml(int page, int pageSize, int total, int from, int count) {
        StringBuilder missions = new StringBuilder();
        for (int index = from; index < from + count; index++) {
            missions.append(missionXml(String.format("ST-%09d", index)));
        }
        return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><missionList xmlns=\"" + StubMissions.NS + "\"><page>" + page + "</page><pageSize>" + pageSize
                + "</pageSize><totalCount>" + total + "</totalCount><totalPages>" + (total + pageSize - 1) / pageSize + "</totalPages>" + missions + "</missionList>";
    }

    // ---- the mission -----------------------------------------------------------------------------------------------

    @Test
    void everyMissionOfTheReleasedDatasetReadsByItsIdWithEveryFieldAsTheServiceSentIt() {
        for (String block : BLOCKS) {
            String id = StubMissions.field(block, "missionId");
            var result = run("{ mission(missionId: \"" + id + "\") { " + ALL_FIELDS + " } }");
            assertThat(errors(result)).as(id).isEmpty();
            Map<String, Object> mission = (Map<String, Object>) data(result).get("mission");
            assertThat(mission).containsEntry("missionId", id).containsEntry("title", StubMissions.field(block, "title"))
                    .containsEntry("type", StubMissions.field(block.replaceFirst("(?s)<location>.*?</location>", ""), "type"))
                    .containsEntry("classification", StubMissions.field(block, "classification")).containsEntry("status", StubMissions.field(block, "status"))
                    .containsEntry("priority", Integer.parseInt(StubMissions.field(block, "priority"))).containsEntry("stardate", StubMissions.field(block, "stardate"))
                    .containsEntry("durationHours", Integer.parseInt(StubMissions.field(block, "durationHours")))
                    .containsEntry("objective", StubMissions.field(block, "objective")).containsEntry("issuingAuthority", StubMissions.field(block, "issuingAuthority"))
                    .containsEntry("commandingOfficerId", StubMissions.field(block, "commandingOfficerId"))
                    .containsEntry("assignedCrewIds", members(block, "crewId")).containsEntry("participantIds", members(block, "participantId"))
                    .containsEntry("assignedAssetIds", members(block, "assetId"))
                    .containsEntry("estimatedCostCredits", StubMissions.field(block, "estimatedCostCredits"))
                    .containsEntry("actualCostCredits", StubMissions.field(block, "actualCostCredits")).containsEntry("outcome", StubMissions.field(block, "outcome"))
                    .containsEntry("lastUpdated", StubMissions.field(block, "lastUpdated"));
            Map<String, Object> location = (Map<String, Object>) mission.get("location");
            assertThat(location).containsEntry("type", StubMissions.field(StubMissions.field(block, "location"), "type"))
                    .containsEntry("name", StubMissions.field(StubMissions.field(block, "location"), "name")).containsEntry("coordinates", StubMissions.field(StubMissions.field(block, "location"), "coordinates"))
                    .containsEntry("travelVector", StubMissions.field(StubMissions.field(block, "location"), "travelVector"));
        }
        assertThat(STUB.calls()).hasSize(BLOCKS.size());
    }

    @Test
    void theContractFixturesServeThroughTheAdapter() {
        STUB.route("/missions/ST-0000000A1", 200, StubMissions.fixture("valid/mission-response.xml"));
        STUB.route("/missions/ST-0000000A2", 200, StubMissions.fixture("valid/mission-list.xml").replaceAll("(?s)^.*?<mission>", "<mission xmlns=\"" + StubMissions.NS + "\">")
                .replaceAll("(?s)</mission>.*$", "</mission>"));
        var full = run("{ mission(missionId: \"ST-0000000A1\") { " + ALL_FIELDS + " } }");
        Map<String, Object> mission = (Map<String, Object>) data(full).get("mission");
        assertThat(mission).containsEntry("estimatedCostCredits", "140000.00").containsEntry("actualCostCredits", "155000.00")
                .containsEntry("stardate", "43125.80").containsEntry("commandingOfficerId", "C-2")
                .containsEntry("assignedCrewIds", List.of("C-10", "C-2")).containsEntry("participantIds", List.of("O-7", "P-3"));
        assertThat((Map<String, Object>) mission.get("location")).containsEntry("coordinates", "opaque-coordinates").containsEntry("travelVector", "opaque-vector");
        var minimal = run("{ mission(missionId: \"ST-0000000A2\") { " + ALL_FIELDS + " } }");
        assertThat(errors(minimal)).isEmpty();
        assertThat((Map<String, Object>) data(minimal).get("mission")).containsEntry("commandingOfficerId", null).containsEntry("estimatedCostCredits", null)
                .containsEntry("actualCostCredits", null).containsEntry("outcome", null).containsEntry("assignedCrewIds", List.of());
    }

    @Test
    void aMissionThatDoesNotExistIsNullWithNoErrorsEntry() {
        var result = run("{ mission(missionId: \"ST-ZZZZZZZZZ\") { missionId } }");
        assertThat(data(result)).containsEntry("mission", null);
        assertThat(errors(result)).isEmpty();
        assertThat(STUB.calls()).containsExactly("/missions/ST-ZZZZZZZZZ");
    }

    @Test
    void aMalformedIdIsBadUserInput() {
        var result = run("{ mission(missionId: \"sh-17\") { missionId } }");
        assertThat(data(result)).containsEntry("mission", null);
        assertThat(codes(result)).containsExactly("BAD_USER_INPUT");
        assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("mission"));
    }

    @Test
    void anIdThatCannotBeOnePathSegmentIsBadUserInputAndIsNeverSent() {
        for (String id : List.of("ST-0/1", "../missions", "..", ".", "a\\b", "")) {
            var result = run("query($id: ID!) { mission(missionId: $id) { missionId } }", Map.of("id", id));
            assertThat(data(result)).as(id).containsEntry("mission", null);
            assertThat(codes(result)).as(id).containsExactly("BAD_USER_INPUT");
        }
        assertThat(STUB.calls()).isEmpty();
        var entity = run(MISSIONS, Map.of("r", List.of(Map.of("__typename", "Mission", "missionId", "x/y"))));
        assertThat(codes(entity)).containsExactly("BAD_USER_INPUT");
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void anUnknownPathAnswersABodylessNotFoundAndIsNotAMissingMission() {
        STUB.route("/missions/ST-000000001", 404, "");
        var result = run("{ mission(missionId: \"ST-000000001\") { missionId } }");
        assertThat(data(result)).containsEntry("mission", null);
        assertThat(codes(result)).containsExactly("UPSTREAM_BAD_RESPONSE");
        STUB.reset();
        STUB.route("/missions/ST-000000001", 404, "{\"code\":\"MISSION_NOT_FOUND\"}");
        assertThat(codes(run("{ mission(missionId: \"ST-000000001\") { missionId } }"))).as("a JSON body is not the contract's error").containsExactly("UPSTREAM_BAD_RESPONSE");
        STUB.reset();
        STUB.route("/missions/ST-000000001", 404, StubMissions.error("INVALID_REQUEST"));
        assertThat(codes(run("{ mission(missionId: \"ST-000000001\") { missionId } }"))).containsExactly("UPSTREAM_BAD_RESPONSE");
    }

    @Test
    void aServerErrorATimeoutAndNoServiceAreServiceUnavailableWithOneEntry() {
        STUB.route("/missions/ST-000000001", 500, StubMissions.error("INTERNAL_ERROR"));
        STUB.route("/missions/ST-000000002", 200, StubMissions.fixture("valid/mission-response.xml"), 2000);
        for (String id : List.of("ST-000000001", "ST-000000002")) {
            var result = run("{ mission(missionId: \"" + id + "\") { missionId title status } }");
            assertThat(data(result)).containsEntry("mission", null);
            assertThat(codes(result)).containsExactly("SERVICE_UNAVAILABLE");
            assertThat(errors(result).get(0).get("message")).isEqualTo("Missions service unavailable");
        }
    }

    @Test
    void aBodyThatIsNotTheContractIsAnUpstreamBadResponse() {
        String fixture = StubMissions.fixture("valid/mission-response.xml");
        Map<String, String> bad = new HashMap<>();
        bad.put("ST-000000001", "not xml at all");
        bad.put("ST-000000002", fixture.replace("<status>COMPLETED</status>", "<status>RETIRED</status>"));
        bad.put("ST-000000003", fixture);   // a mission, but not the one asked for
        bad.put("ST-000000004", "<!DOCTYPE mission [<!ENTITY x SYSTEM \"file:///etc/passwd\">]>" + fixture.substring(fixture.indexOf("<mission")).replace("Example sector", "&x;"));
        bad.put("ST-000000005", "");
        bad.forEach((id, body) -> STUB.route("/missions/" + id, 200, body));
        for (String id : bad.keySet()) {
            var result = run("{ mission(missionId: \"" + id + "\") { missionId } }");
            assertThat(data(result)).as(id).containsEntry("mission", null);
            assertThat(codes(result)).as(id).containsExactly("UPSTREAM_BAD_RESPONSE");
        }
    }

    // ---- the list --------------------------------------------------------------------------------------------------

    @Test
    void aDefaultPageIsOneCallOfTwentyAndTheServicesOrder() {
        var result = run("{ missions { missionId } }");
        assertThat(errors(result)).isEmpty();
        assertThat(ids(result)).isEqualTo(idsOf(BLOCKS.subList(0, 20)));
        assertThat(STUB.calls()).containsExactly("/missions?page=1&pageSize=20");
    }

    @Test
    void theLastPageIsShortAndAnOffsetPastTheEndIsAnEmptyList() {
        assertThat(ids(run("{ missions(offset: 290, limit: 20) { missionId } }"))).isEqualTo(idsOf(BLOCKS.subList(290, 300)));
        STUB.reset();
        var past = run("{ missions(offset: 300, limit: 20) { missionId } }");
        assertThat(data(past)).containsEntry("missions", List.of());
        assertThat(errors(past)).isEmpty();
        assertThat(STUB.calls()).hasSize(1);
        assertThat(data(run("{ missions(offset: 2000000000, limit: 5) { missionId } }"))).containsEntry("missions", List.of());
    }

    @Test
    void anOddOffsetIsSlicedFromTheCoveringPage() {
        var result = run("{ missions(offset: 5, limit: 10) { missionId } }");
        assertThat(ids(result)).isEqualTo(idsOf(BLOCKS.subList(5, 15)));
        assertThat(STUB.calls()).hasSize(1);
        STUB.reset();
        assertThat(ids(run("{ missions(offset: 17, limit: 9) { missionId } }"))).isEqualTo(idsOf(BLOCKS.subList(17, 26)));
        STUB.reset();
        assertThat(ids(run("{ missions(offset: 28, limit: 100) { missionId } }"))).isEqualTo(idsOf(BLOCKS.subList(28, 128)));
    }

    @Test
    void aLimitAboveFiftyTakesTwoCallsAndTheListIsTheSlice() {
        STUB.route("/missions?page=1&pageSize=50", 200, pageXml(1, 50, 75, 0, 50));
        STUB.route("/missions?page=2&pageSize=50", 200, pageXml(2, 50, 75, 50, 25));
        var result = run("{ missions(limit: 100) { missionId } }");
        assertThat(errors(result)).isEmpty();
        assertThat(ids(result)).hasSize(75).startsWith("ST-000000000", "ST-000000001").endsWith("ST-000000074");
        assertThat(STUB.calls()).containsExactly("/missions?page=1&pageSize=50", "/missions?page=2&pageSize=50");
    }

    @Test
    void theFiltersReachTheServiceInOrderAndSelectTheDatasetMissions() {
        var result = run("{ missions(status: COMPLETED, assignedAssetId: \"EQ-64\", limit: 50) { missionId status assignedAssetIds } }");
        assertThat(STUB.calls()).containsExactly("/missions?status=COMPLETED&assignedAssetId=EQ-64&page=1&pageSize=50");
        List<String> expected = idsOf(BLOCKS.stream().filter(block -> "COMPLETED".equals(StubMissions.field(block, "status")) && members(block, "assetId").contains("EQ-64")).toList());
        assertThat(expected).isNotEmpty();
        assertThat(ids(result)).isEqualTo(expected);
        STUB.reset();
        var every = run("{ missions(type: SCIENTIFIC, classification: UNCLASSIFIED, priority: 3, issuingAuthority: STARFLEET_SCIENCE, commandingOfficerId: \"C-85\","
                + " assignedCrewId: \"C-92\", locationType: DEEP_SPACE, limit: 50) { missionId } }");
        assertThat(errors(every)).isEmpty();
        assertThat(STUB.calls()).containsExactly("/missions?type=SCIENTIFIC&classification=UNCLASSIFIED&priority=3&issuingAuthority=STARFLEET_SCIENCE"
                + "&commandingOfficerId=C-85&assignedCrewId=C-92&locationType=DEEP_SPACE&page=1&pageSize=50");
        assertThat(ids(every)).contains("ST-00000LD4O");
    }

    @Test
    void aFilterValueTheServiceRefusesIsBadUserInputWithTheListNull() {
        for (String arguments : List.of("priority: 9", "commandingOfficerId: \"x\"", "assignedAssetId: \"eq-64\"")) {
            var result = run("{ missions(" + arguments + ") { missionId } }");
            assertThat(data(result)).as(arguments).containsEntry("missions", null);
            assertThat(codes(result)).as(arguments).containsExactly("BAD_USER_INPUT");
        }
    }

    @Test
    void anEnumValueOutsideTheContractNeverReachesTheService() {
        var result = run("{ missions(status: RETIRED) { missionId } }");
        assertThat(errors(result)).isNotEmpty();
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void aLimitAbove100OrBelow1OrANegativeOffsetIsBadUserInputWithNoCall() {
        for (String arguments : List.of("limit: 101", "limit: 0", "offset: -1")) {
            var result = run("{ missions(" + arguments + ") { missionId } }");
            assertThat(data(result)).containsEntry("missions", null);
            assertThat(codes(result)).containsExactly("BAD_USER_INPUT");
        }
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void ifTheSecondCallOfAPageFailsTheWholeListIsNullWithOneEntry() {
        STUB.route("/missions?page=1&pageSize=50", 200, pageXml(1, 50, 75, 0, 50));
        STUB.route("/missions?page=2&pageSize=50", 500, StubMissions.error("INTERNAL_ERROR"));
        var result = run("{ missions(limit: 100) { missionId } }");
        assertThat(data(result)).containsEntry("missions", null);
        assertThat(codes(result)).containsExactly("SERVICE_UNAVAILABLE");
        assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("missions"));
    }

    @Test
    void ifTheFirstCallFailsTheSecondIsNotMadeAndABadBodyIsOneUpstreamBadResponse() {
        STUB.route("/missions?page=1&pageSize=50", 500, "");
        var down = run("{ missions(limit: 100) { missionId } }");
        assertThat(data(down)).containsEntry("missions", null);
        assertThat(codes(down)).containsExactly("SERVICE_UNAVAILABLE");
        assertThat(STUB.calls()).containsExactly("/missions?page=1&pageSize=50");
        STUB.reset();
        STUB.route("/missions?page=1&pageSize=50", 200, "<missionList xmlns=\"" + StubMissions.NS + "\"><page>1</page></missionList>");
        var bad = run("{ missions(limit: 100) { missionId } }");
        assertThat(codes(bad)).containsExactly("UPSTREAM_BAD_RESPONSE");
        STUB.reset();
        STUB.route("/missions?page=1&pageSize=20", 200, pageXml(2, 20, 5, 0, 5));
        assertThat(codes(run("{ missions { missionId } }"))).as("another page than the one asked").containsExactly("UPSTREAM_BAD_RESPONSE");
    }

    @Test
    void theContractFixturesOfAListAndAnEmptyListServeThroughTheAdapter() {
        STUB.route("/missions?page=1&pageSize=20", 200, StubMissions.fixture("valid/mission-list.xml"));
        assertThat(ids(run("{ missions { missionId } }"))).containsExactly("ST-0000000A2");
        STUB.reset();
        STUB.route("/missions?page=1&pageSize=20", 200, StubMissions.fixture("valid/mission-list-empty.xml"));
        var empty = run("{ missions { missionId } }");
        assertThat(data(empty)).containsEntry("missions", List.of());
        assertThat(errors(empty)).isEmpty();
    }

    // ---- the asset references --------------------------------------------------------------------------------------

    @Test
    void eachAssignedAssetIsOneStubWithTheReferenceAsStoredAndTheReleaseTheClientNamed() {
        var result = run("{ mission(missionId: \"ST-00000LD4S\") { assignedAssetIds assets(release: \"1.0\") { localRef release } } }");
        assertThat(errors(result)).isEmpty();
        Map<String, Object> mission = (Map<String, Object>) data(result).get("mission");
        assertThat(mission.get("assignedAssetIds")).isEqualTo(List.of("EQ-75", "SH-42", "VS-31"));
        assertThat(mission.get("assets")).isEqualTo(List.of(Map.of("localRef", "EQ-75", "release", "1.0"), Map.of("localRef", "SH-42", "release", "1.0"),
                Map.of("localRef", "VS-31", "release", "1.0")));
        assertThat(STUB.calls()).as("the reference field makes no call: only the one call for the mission").containsExactly("/missions/ST-00000LD4S");
        STUB.reset();
        var other = run("{ mission(missionId: \"ST-00000LD4S\") { assets(release: \"9.9\") { localRef release } } }");
        assertThat(((List<Map<String, Object>>) ((Map<String, Object>) data(other).get("mission")).get("assets"))).extracting(entry -> entry.get("release"))
                .containsExactly("9.9", "9.9", "9.9");
    }

    @Test
    void eachAssignedCrewMemberIsOnePersonnelReferenceStubAndTheCommandingOfficerAndTheParticipantsAreNot() {
        var result = run("{ mission(missionId: \"ST-00000LD4O\") { commandingOfficerId assignedCrewIds participantIds crew(release: \"1.0\") { localRef release } } }");
        assertThat(errors(result)).isEmpty();
        Map<String, Object> mission = (Map<String, Object>) data(result).get("mission");
        assertThat(mission.get("commandingOfficerId")).isEqualTo("C-85");
        assertThat(mission.get("assignedCrewIds")).isEqualTo(List.of("C-120", "C-92"));
        assertThat(mission.get("crew")).isEqualTo(List.of(Map.of("localRef", "C-120", "release", "1.0"), Map.of("localRef", "C-92", "release", "1.0")));
        assertThat(STUB.calls()).as("the reference field makes no call: only the one call for the mission").containsExactly("/missions/ST-00000LD4O");
        var missing = run("{ mission(missionId: \"ST-00000LD4O\") { crew { localRef } } }");
        assertThat(errors(missing)).as("a request that names no release is refused by GraphQL itself").isNotEmpty();
    }

    @Test
    void theCommandingOfficerIsOnePersonnelReferenceStubOrNullWhenTheMissionHasNone() {
        var result = run("{ mission(missionId: \"ST-00000LD4O\") { commandingOfficerId commandingOfficer(release: \"1.1\") { localRef release } } }");
        assertThat(errors(result)).isEmpty();
        Map<String, Object> mission = (Map<String, Object>) data(result).get("mission");
        assertThat(mission.get("commandingOfficerId")).isEqualTo("C-85");
        assertThat(mission.get("commandingOfficer")).isEqualTo(Map.of("localRef", "C-85", "release", "1.1"));
        assertThat(STUB.calls()).as("the reference field makes no call: only the one call for the mission").containsExactly("/missions/ST-00000LD4O");
        STUB.route("/missions/ST-0000000A2", 200, StubMissions.fixture("valid/mission-list.xml").replaceAll("(?s)^.*?<mission>", "<mission xmlns=\"" + StubMissions.NS + "\">")
                .replaceAll("(?s)</mission>.*$", "</mission>"));
        var none = run("{ mission(missionId: \"ST-0000000A2\") { commandingOfficerId commandingOfficer(release: \"1.1\") { localRef } } }");
        assertThat(errors(none)).as("no commanding officer is null data, not an error").isEmpty();
        assertThat((Map<String, Object>) data(none).get("mission")).containsEntry("commandingOfficerId", null).containsEntry("commandingOfficer", null);
        var missing = run("{ mission(missionId: \"ST-00000LD4O\") { commandingOfficer { localRef } } }");
        assertThat(errors(missing)).as("a request that names no release is refused by GraphQL itself").isNotEmpty();
    }

    @Test
    void aMissionWithNoAssetsHasNoStubsAndTheReleaseIsRequired() {
        STUB.route("/missions/ST-0000000A2", 200, StubMissions.fixture("valid/mission-list.xml").replaceAll("(?s)^.*?<mission>", "<mission xmlns=\"" + StubMissions.NS + "\">")
                .replaceAll("(?s)</mission>.*$", "</mission>"));
        var none = run("{ mission(missionId: \"ST-0000000A2\") { assets(release: \"1.0\") { localRef } } }");
        assertThat(((Map<String, Object>) data(none).get("mission")).get("assets")).isEqualTo(List.of());
        var missing = run("{ mission(missionId: \"ST-0000000A2\") { assets { localRef } } }");
        assertThat(errors(missing)).as("a request that names no release is refused by GraphQL itself").isNotEmpty();
    }

    @Test
    void theStubsAlsoComeFromAListWithoutAnyExtraCall() {
        var result = run("{ missions(limit: 3) { missionId assets(release: \"1.0\") { localRef release } } }");
        assertThat(errors(result)).isEmpty();
        assertThat(STUB.calls()).hasSize(1);
        List<Map<String, Object>> missions = (List<Map<String, Object>>) data(result).get("missions");
        assertThat(missions.get(0).get("assets")).isEqualTo(members(BLOCKS.get(0), "assetId").stream().map(ref -> Map.of("localRef", ref, "release", "1.0")).toList());
    }

    // ---- the Federation entry points -------------------------------------------------------------------------------

    @Test
    void theServiceAnswersItsSdlWithFederation2() {
        var sdl = (String) ((Map<String, Object>) data(run("{ _service { sdl } }")).get("_service")).get("sdl");
        assertThat(sdl).contains("https://specs.apollo.dev/federation/v2.0");
        assertThat(sdl).contains("type Mission").contains("type AssetReference").contains("type MissionLocation").contains("enum MissionStatus");
        assertThat(sdl).containsPattern("@key\\(fields\\s*:\\s*\"localRef release\",\\s*resolvable\\s*:\\s*false\\)");
        assertThat(sdl).containsPattern("type Mission @key\\(fields\\s*:\\s*\"missionId\"");
        assertThat(sdl).contains("assets(release: String!): [AssetReference!]!").contains("crew(release: String!): [PersonnelReference!]!")
                .contains("commandingOfficer(release: String!): PersonnelReference");
        assertThat(sdl).contains("estimatedCostCredits: String").doesNotContain("Float");
    }

    @Test
    void theSchemaUsesOnlyKeyAndTheResolvableFalseOfTheStub() throws IOException {
        String schema;
        try (InputStream stream = getClass().getResourceAsStream("/graphql/schema.graphqls")) {
            schema = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
        String code = schema.lines().filter(line -> !line.stripLeading().startsWith("#")).collect(Collectors.joining("\n"));
        Matcher matcher = Pattern.compile("@(\\w+)").matcher(code);
        java.util.Set<String> used = new TreeSet<>();
        while (matcher.find()) {
            used.add(matcher.group(1));
        }
        assertThat(used).containsExactlyInAnyOrder("link", "key");
        assertThat(code).contains("@key(fields: \"missionId\")").contains("@key(fields: \"localRef release\", resolvable: false)");
        assertThat(code).contains("import: [\"@key\"]");
    }

    private static final String MISSIONS = "query($r: [_Any!]!) { _entities(representations: $r) { ... on Mission { missionId title status } } }";

    @Test
    void theMissionEntityResolvesByItsKeyAndAnUnknownKeyIsNullWithNoEntry() {
        var result = run(MISSIONS, Map.of("r", List.of(Map.of("__typename", "Mission", "missionId", "ST-00000LD4O"), Map.of("__typename", "Mission", "missionId", "ST-ZZZZZZZZZ"))));
        List<Map<String, Object>> entities = (List<Map<String, Object>>) data(result).get("_entities");
        assertThat(entities.get(0)).containsEntry("missionId", "ST-00000LD4O").containsEntry("title", "Stellar observation support").containsEntry("status", "POSTPONED");
        assertThat(entities.get(1)).isNull();
        assertThat(errors(result)).isEmpty();
    }

    @Test
    void aFailedCallOfAnEntityIsOneEntryPerCallAndAMalformedKeyIsBadUserInput() {
        STUB.route("/missions/ST-000000001", 500, "");
        STUB.route("/missions/ST-000000002", 200, "junk");
        var result = run(MISSIONS, Map.of("r", List.of(Map.of("__typename", "Mission", "missionId", "ST-000000001"), Map.of("__typename", "Mission", "missionId", "ST-000000002"),
                Map.of("__typename", "Mission", "missionId", "x1"))));
        assertThat(codes(result)).containsExactly("SERVICE_UNAVAILABLE", "UPSTREAM_BAD_RESPONSE", "BAD_USER_INPUT");
        assertThat((List<Object>) data(result).get("_entities")).containsExactly(null, null, null);
    }

    @Test
    void aRepresentationThatLacksTheKeyOrNamesAnotherTypeIsAnAdapterFault() {
        List<Map<String, Object>> representations = List.of(Map.<String, Object>of("__typename", "Mission"),
                Map.<String, Object>of("__typename", "AssetReference", "localRef", "SH-17", "release", "1.0"));
        for (Map<String, Object> representation : representations) {
            var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on Mission { missionId } } }", Map.of("r", List.of(representation)));
            assertThat(codes(result)).as(representation.toString()).containsExactly("INTERNAL_SERVER_ERROR");
        }
    }

    @Test
    void theClientNeverThrows() throws IOException {
        int closed;
        try (ServerSocket socket = new ServerSocket(0, 1, java.net.InetAddress.getLoopbackAddress())) {
            closed = socket.getLocalPort();
        }
        MissionsClient client = new MissionsClient("http://127.0.0.1:" + closed + "/", 300, 500);
        assertThat(client.mission("ST-000000001").failed()).isTrue();
        HttpResult list = client.list(new java.util.LinkedHashMap<>(), 1, 20);
        assertThat(list.failed()).isTrue();
    }
}
