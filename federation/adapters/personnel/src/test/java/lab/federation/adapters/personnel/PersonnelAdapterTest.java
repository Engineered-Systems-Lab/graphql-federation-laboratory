package lab.federation.adapters.personnel;

import static org.assertj.core.api.Assertions.assertThat;

import graphql.ExecutionInput;
import java.io.IOException;
import java.io.InputStream;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
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
 * The adapter against a stub of the Personnel v2 service that serves the two registered snapshots and validates every request
 * against the real XSD: the member and its choice of details, not-found as data, the failures and their codes, the paging cases,
 * the all-or-nothing rule, the four outcomes of a crew reference, the snapshot that the adapter reads once by pages and serves
 * from memory (one probe per batch, a reload on a new datasetVersion, outages answered as before), one errors entry per failed lookup
 * and the Federation entry points.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@SuppressWarnings("unchecked")
class PersonnelAdapterTest {
    private static final StubPersonnel STUB = start();

    private static StubPersonnel start() {
        try {
            return new StubPersonnel();
        } catch (IOException error) {
            throw new IllegalStateException(error);
        }
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("personnel.service-url", STUB::url);
        registry.add("personnel.connect-timeout-ms", () -> "300");
        registry.add("personnel.read-timeout-ms", () -> "500");
    }

    @AfterAll
    static void stop() {
        STUB.close();
    }

    @Autowired
    GraphQlSource source;

    @Autowired
    PersonnelSnapshots snapshots;

    /** What an entity lookup sends first, and what it sends to read a snapshot of up to 100 members. */
    private static final String PROBE = "list?offset=0&limit=1";
    private static final String READ = "list?offset=0&limit=100";

    @BeforeEach
    void reset() {
        STUB.reset();
        snapshots.clear();
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
        return errors(result).stream().map(PersonnelAdapterTest::code).toList();
    }

    private static final String DETAILS = "details { __typename ... on CrewDetails { rank department securityClearance supervisorPersonnelId } "
            + "... on CivilianDetails { placeholder } }";
    private static final String MEMBER = "personnelId displayName positionTitle dutyStatus " + DETAILS;
    private static final String ONE = "query($id: ID!) { personnel(personnelId: $id) { " + MEMBER + " } }";
    private static final String LIST = "query($department: Department, $dutyStatus: DutyStatus, $offset: Int, $limit: Int) { personnelMembers(department: $department, "
            + "dutyStatus: $dutyStatus, offset: $offset, limit: $limit) { datasetVersion totalCount offset limit hasMore items { personnelId displayName } } }";

    private static Map<String, Object> variables(Object... pairs) {
        Map<String, Object> variables = new HashMap<>();
        for (int index = 0; index < pairs.length; index += 2) {
            variables.put((String) pairs[index], pairs[index + 1]);
        }
        return variables;
    }

    private Map<String, Object> page(Object... pairs) {
        return run(LIST, variables(pairs));
    }

    private static Map<String, Object> pageOf(Map<String, Object> result) {
        return (Map<String, Object>) data(result).get("personnelMembers");
    }

    private static List<String> ids(Map<String, Object> result) {
        return ((List<Map<String, Object>>) pageOf(result).get("items")).stream().map(item -> (String) item.get("personnelId")).toList();
    }

    private static List<String> idsOf(String snapshot) {
        return StubPersonnel.blocks(StubPersonnel.snapshot(snapshot)).stream().map(block -> StubPersonnel.field(block, "personnelId")).toList();
    }

    // ---- the member ------------------------------------------------------------------------------------------------

    @Test
    void everyMemberOfBothSnapshotsReadsByItsIdWithEveryFieldAndItsChoiceOfDetails() {
        for (String name : List.of(StubPersonnel.SMALL_001, StubPersonnel.SMALL_002)) {
            STUB.reset();
            STUB.use(name);
            for (String block : StubPersonnel.blocks(StubPersonnel.snapshot(name))) {
                String id = StubPersonnel.field(block, "personnelId");
                var result = run(ONE, Map.of("id", id));
                assertThat(errors(result)).as(name + " " + id).isEmpty();
                Map<String, Object> member = (Map<String, Object>) data(result).get("personnel");
                assertThat(member).containsEntry("personnelId", id).containsEntry("displayName", StubPersonnel.field(block, "displayName"))
                        .containsEntry("positionTitle", StubPersonnel.field(block, "positionTitle"))
                        .containsEntry("dutyStatus", StubPersonnel.field(block, "dutyStatus"));
                Map<String, Object> details = (Map<String, Object>) member.get("details");
                if (block.contains("<civilianDetails/>")) {
                    assertThat(details).containsEntry("__typename", "CivilianDetails").containsEntry("placeholder", null);
                } else {
                    assertThat(details).containsEntry("__typename", "CrewDetails").containsEntry("rank", StubPersonnel.field(block, "rank"))
                            .containsEntry("department", StubPersonnel.field(block, "department"))
                            .containsEntry("securityClearance", StubPersonnel.field(block, "securityClearance"))
                            .containsEntry("supervisorPersonnelId", StubPersonnel.field(block, "supervisorPersonnelId"));
                }
            }
            assertThat(STUB.calls()).hasSize(7).allMatch(call -> call.startsWith("get/PRS-"));
            assertThat(STUB.invalid()).isEmpty();
        }
    }

    @Test
    void theWesleyCaseOnePersonnelIdIsACivilianInOneSnapshotAndACrewEnsignInTheOther() {
        STUB.use(StubPersonnel.SMALL_001);
        Map<String, Object> civilian = (Map<String, Object>) data(run(ONE, Map.of("id", "PRS-0714"))).get("personnel");
        assertThat(civilian).containsEntry("positionTitle", "Student");
        assertThat((Map<String, Object>) civilian.get("details")).containsEntry("__typename", "CivilianDetails");
        STUB.use(StubPersonnel.SMALL_002);
        Map<String, Object> crew = (Map<String, Object>) data(run(ONE, Map.of("id", "PRS-0714"))).get("personnel");
        assertThat(crew).containsEntry("personnelId", "PRS-0714").containsEntry("positionTitle", "Acting Ensign");
        assertThat((Map<String, Object>) crew.get("details")).containsEntry("__typename", "CrewDetails").containsEntry("rank", "ENSIGN")
                .containsEntry("department", "OPERATIONS").containsEntry("supervisorPersonnelId", "PRS-0002");
    }

    @Test
    void aMemberThatDoesNotExistIsNullWithNoErrorsEntry() {
        var result = run(ONE, Map.of("id", "PRS-9999"));
        assertThat(data(result)).containsEntry("personnel", null);
        assertThat(errors(result)).isEmpty();
        assertThat(STUB.calls()).containsExactly("get/PRS-9999");
    }

    @Test
    void anIdTheServiceRefusesIsBadUserInput() {
        for (String id : List.of("PRS-0000", "x", "", " PRS-0001", "PRS-00011", "prs-0001", "PRS-0001 ", "<tag>", "a&b", "\"'")) {
            var result = run(ONE, Map.of("id", id));
            assertThat(data(result)).as(id).containsEntry("personnel", null);
            assertThat(codes(result)).as(id).containsExactly("BAD_USER_INPUT");
            assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("personnel"));
        }
        assertThat(STUB.invalid()).as("the markup characters were escaped, so each request was well-formed XML the service could refuse").hasSize(10);
        assertThat(STUB.invalid().stream().filter(body -> body.contains("&lt;tag&gt;")).count()).isEqualTo(1);
        assertThat(STUB.invalid().stream().filter(body -> body.contains("a&amp;b")).count()).isEqualTo(1);
    }

    @Test
    void anIdThatCannotBeSentAsXmlTextIsBadUserInputAndIsNeverSent() {
        for (String id : List.of("PRS-0001\n", "PRS-\u0000001", "PRS-é001", "PRS-0001 ", "\t")) {
            var result = run(ONE, Map.of("id", id));
            assertThat(data(result)).as(id).containsEntry("personnel", null);
            assertThat(codes(result)).as(id).containsExactly("BAD_USER_INPUT");
        }
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void aFailureOfTheServiceIsUnavailableWithOneEntryAndEveryOtherFailureHasItsCode() {
        record Case(String name, int status, String body, String code) {
        }
        for (Case failure : List.of(
                new Case("a plain 500", 500, "Internal Server Error", "SERVICE_UNAVAILABLE"),
                new Case("a 503", 503, "", "SERVICE_UNAVAILABLE"),
                new Case("the fault ServiceUnavailable", 500, StubPersonnel.fault("ServiceUnavailable", null), "SERVICE_UNAVAILABLE"),
                new Case("the fault InternalError", 500, StubPersonnel.fault("InternalError", null), "SERVICE_UNAVAILABLE"),
                new Case("a protocol fault with no detail", 500, StubPersonnel.envelope("<soap:Fault><faultcode>soap:Server</faultcode><faultstring>x</faultstring></soap:Fault>"), "SERVICE_UNAVAILABLE"),
                new Case("a malformed envelope", 200, "<soap:Envelope", "UPSTREAM_BAD_RESPONSE"),
                new Case("a body that is not the contract", 200, StubPersonnel.envelope("<Other xmlns=\"" + StubPersonnel.NS + "\"/>"), "UPSTREAM_BAD_RESPONSE"),
                new Case("a fault under HTTP 200", 200, StubPersonnel.fault("PersonnelNotFound", "personnelId"), "UPSTREAM_BAD_RESPONSE"),
                new Case("a bodyless 404", 404, "", "UPSTREAM_BAD_RESPONSE"),
                new Case("a 400", 400, "bad", "UPSTREAM_BAD_RESPONSE"))) {
            STUB.reset();
            STUB.route("get/PRS-0002", failure.status(), failure.body());
            var result = run(ONE, Map.of("id", "PRS-0002"));
            assertThat(data(result)).as(failure.name()).containsEntry("personnel", null);
            assertThat(codes(result)).as(failure.name()).containsExactly(failure.code());
            assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("personnel"));
        }
    }

    @Test
    void aTimeoutIsUnavailableAndTheMessageNamesNoInternals() {
        STUB.route("get/PRS-0002", 200, StubPersonnel.envelope("<Other/>"), 2000);
        var result = run(ONE, Map.of("id", "PRS-0002"));
        assertThat(codes(result)).containsExactly("SERVICE_UNAVAILABLE");
        assertThat(errors(result).get(0).get("message")).isEqualTo("Personnel service unavailable");
    }

    @Test
    void aMemberThatIsNotTheOneAskedForIsNotUsed() {
        STUB.route("get/PRS-0002", 200, StubPersonnel.envelope("<GetPersonnelMemberResponse xmlns=\"" + StubPersonnel.NS + "\"><datasetVersion>personnel-v2-small-002</datasetVersion>"
                + StubPersonnel.blocks(StubPersonnel.snapshot(StubPersonnel.SMALL_002)).get(0) + "</GetPersonnelMemberResponse>"));
        var result = run(ONE, Map.of("id", "PRS-0002"));
        assertThat(data(result)).containsEntry("personnel", null);
        assertThat(codes(result)).containsExactly("UPSTREAM_BAD_RESPONSE");
    }

    // ---- the list and the paging -----------------------------------------------------------------------------------

    @Test
    void aDefaultPageIsOneCallWithOffset0AndLimit20AndCarriesTheDatasetVersion() {
        var result = run("{ personnelMembers { datasetVersion totalCount offset limit hasMore items { personnelId displayName positionTitle dutyStatus " + DETAILS + " } } }");
        assertThat(errors(result)).isEmpty();
        Map<String, Object> page = pageOf(result);
        assertThat(page).containsEntry("datasetVersion", StubPersonnel.SMALL_002).containsEntry("totalCount", 7).containsEntry("offset", 0)
                .containsEntry("limit", 20).containsEntry("hasMore", false);
        assertThat(((List<Map<String, Object>>) page.get("items")).stream().map(item -> item.get("personnelId")).toList()).isEqualTo(idsOf(StubPersonnel.SMALL_002));
        assertThat(STUB.calls()).containsExactly("list?offset=0&limit=20");
        assertThat(STUB.invalid()).isEmpty();
    }

    @Test
    void theLimitOf100IsOneCallAndALimitAbove100OrBelow1OrANegativeOffsetIsBadUserInputWithNoCall() {
        assertThat(errors(page("offset", 0, "limit", 100))).isEmpty();
        assertThat(STUB.calls()).containsExactly("list?offset=0&limit=100");
        STUB.reset();
        for (var arguments : List.of(variables("offset", 0, "limit", 101), variables("offset", 0, "limit", 0), variables("offset", 0, "limit", -1),
                variables("offset", -1, "limit", 20))) {
            var result = run(LIST, arguments);
            assertThat(data(result)).as(arguments.toString()).containsEntry("personnelMembers", null);
            assertThat(codes(result)).as(arguments.toString()).containsExactly("BAD_USER_INPUT");
        }
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void aNullOffsetOrLimitMeansTheDefault() {
        var result = page("offset", null, "limit", null);
        assertThat(errors(result)).isEmpty();
        assertThat(pageOf(result)).containsEntry("offset", 0).containsEntry("limit", 20);
        assertThat(STUB.calls()).containsExactly("list?offset=0&limit=20");
    }

    @Test
    void anOffsetAndALimitSelectTheWindowAndAnOffsetPastTheEndIsAnEmptyPage() {
        var window = page("offset", 2, "limit", 2);
        assertThat(ids(window)).containsExactly("PRS-0003", "PRS-0004");
        assertThat(pageOf(window)).containsEntry("hasMore", true).containsEntry("totalCount", 7).containsEntry("offset", 2).containsEntry("limit", 2);
        var past = page("offset", 7, "limit", 20);
        assertThat(errors(past)).isEmpty();
        assertThat(ids(past)).isEmpty();
        assertThat(pageOf(past)).containsEntry("hasMore", false).containsEntry("totalCount", 7);
        assertThat(ids(page("offset", 2147483647, "limit", 1))).isEmpty();
        assertThat(STUB.calls()).containsExactly("list?offset=2&limit=2", "list?offset=7&limit=20", "list?offset=2147483647&limit=1");
    }

    @Test
    void theFiltersReachTheServiceAndCombineWithAndAndTheyDependOnTheSnapshot() {
        assertThat(ids(page("department", "OPERATIONS", "dutyStatus", "ACTIVE", "offset", 0, "limit", 20))).containsExactly("PRS-0002", "PRS-0714");
        assertThat(STUB.calls()).containsExactly("list?department=OPERATIONS&dutyStatus=ACTIVE&offset=0&limit=20");
        STUB.use(StubPersonnel.SMALL_001);
        var first = page("department", "OPERATIONS", "dutyStatus", "ACTIVE", "offset", 0, "limit", 20);
        assertThat(ids(first)).as("Wesley is a civilian in the first snapshot, and a department matches crew only").containsExactly("PRS-0002");
        assertThat(pageOf(first)).containsEntry("datasetVersion", StubPersonnel.SMALL_001);
        assertThat(ids(page("dutyStatus", "ON_LEAVE", "offset", 0, "limit", 20))).containsExactly("PRS-0004");
        assertThat(ids(page("department", "MEDICAL", "offset", 0, "limit", 20))).isEmpty();
        assertThat(ids(page("department", "COMMAND", "offset", 0, "limit", 20))).containsExactly("PRS-0001");
        assertThat(STUB.invalid()).isEmpty();
    }

    @Test
    void theDatasetVersionIsOnEveryResultSoAClientCanSeeItChangeBetweenPages() {
        var before = page("offset", 0, "limit", 3);
        STUB.use(StubPersonnel.SMALL_001);
        var after = page("offset", 3, "limit", 3);
        assertThat(pageOf(before).get("datasetVersion")).isEqualTo(StubPersonnel.SMALL_002);
        assertThat(pageOf(after).get("datasetVersion")).isEqualTo(StubPersonnel.SMALL_001);
        assertThat(pageOf(before).get("datasetVersion")).isNotEqualTo(pageOf(after).get("datasetVersion"));
    }

    @Test
    void aFailedCallMakesTheWholeResultNullWithOneEntry() {
        STUB.route("list?offset=0&limit=20", 500, "Internal Server Error");
        var result = page("offset", 0, "limit", 20);
        assertThat(data(result)).containsEntry("personnelMembers", null);
        assertThat(codes(result)).containsExactly("SERVICE_UNAVAILABLE");
        assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("personnelMembers"));
        STUB.reset();
        STUB.route("list?offset=0&limit=20", 200, StubPersonnel.envelope("<ListPersonnelMembersResponse xmlns=\"" + StubPersonnel.NS + "\"/>"));
        var malformed = page("offset", 0, "limit", 20);
        assertThat(data(malformed)).containsEntry("personnelMembers", null);
        assertThat(codes(malformed)).containsExactly("UPSTREAM_BAD_RESPONSE");
        STUB.reset();
        STUB.route("list?offset=0&limit=20", 500, StubPersonnel.fault("PersonnelNotFound", "personnelId"));
        assertThat(codes(page("offset", 0, "limit", 20))).as("a list has no not-found").containsExactly("UPSTREAM_BAD_RESPONSE");
        STUB.reset();
        STUB.route("list?offset=0&limit=20", 200, StubPersonnel.envelope("<Other/>"), 2000);
        assertThat(codes(page("offset", 0, "limit", 20))).containsExactly("SERVICE_UNAVAILABLE");
    }

    @Test
    void aPageThatIsNotTheOneAskedForIsNotUsed() {
        String other = StubPersonnel.envelope("<ListPersonnelMembersResponse xmlns=\"" + StubPersonnel.NS + "\"><datasetVersion>personnel-v2-small-002</datasetVersion>"
                + "<totalCount>7</totalCount><offset>5</offset><limit>20</limit><hasMore>false</hasMore></ListPersonnelMembersResponse>");
        STUB.route("list?offset=0&limit=20", 200, other);
        var result = page("offset", 0, "limit", 20);
        assertThat(data(result)).containsEntry("personnelMembers", null);
        assertThat(codes(result)).containsExactly("UPSTREAM_BAD_RESPONSE");
    }

    // ---- the four outcomes of a crew reference ---------------------------------------------------------------------

    /** The representation the router sends: the mapping subgraph's personnelId and mappingOutcome. A null id is NO_ENTRY, a non-null one MAPPED. */
    private static Map<String, Object> reference(String localRef, String personnelId) {
        return reference(localRef, personnelId, personnelId == null ? "NO_ENTRY" : "MAPPED");
    }

    private static Map<String, Object> reference(String localRef, String personnelId, String mappingOutcome) {
        Map<String, Object> representation = new HashMap<>();
        representation.put("__typename", "PersonnelReference");
        representation.put("localRef", localRef);
        representation.put("release", "1.1");
        representation.put("personnelId", personnelId);
        if (mappingOutcome != null) {
            representation.put("mappingOutcome", mappingOutcome);
        }
        return representation;
    }

    private static final String REFERENCES = "query($r: [_Any!]!) { _entities(representations: $r) { ... on PersonnelReference "
            + "{ localRef personnelId mappingOutcome resolution personnel { personnelId displayName dutyStatus " + DETAILS + " } } } }";

    private static List<Map<String, Object>> entities(Map<String, Object> result) {
        return (List<Map<String, Object>>) data(result).get("_entities");
    }

    @Test
    void resolvedUnresolvedAndUnmappedAreDataWithOneProbeAndOneRead() {
        var result = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"), reference("C-404", "PRS-9999"), reference("C-77", null))));
        var list = entities(result);
        assertThat(list.get(0)).containsEntry("resolution", "RESOLVED").containsEntry("personnelId", "PRS-0001").containsEntry("mappingOutcome", "MAPPED").containsEntry("localRef", "C-1");
        assertThat((Map<String, Object>) list.get(0).get("personnel")).containsEntry("personnelId", "PRS-0001").containsEntry("displayName", "Jean-Luc Picard");
        assertThat(list.get(1)).containsEntry("resolution", "UNRESOLVED").containsEntry("personnelId", "PRS-9999").containsEntry("personnel", null);
        assertThat(list.get(2)).containsEntry("resolution", "UNMAPPED").containsEntry("personnelId", null).containsEntry("mappingOutcome", "NO_ENTRY").containsEntry("personnel", null);
        assertThat(errors(result)).as("UNRESOLVED and UNMAPPED are data and add no errors entry").isEmpty();
        assertThat(STUB.calls()).as("one probe and one read for the batch, whatever its size; none for UNMAPPED, and no get call").containsExactly(PROBE, READ);
        assertThat(STUB.invalid()).isEmpty();
    }

    @Test
    void aRefusedReleaseIsItsOwnResolutionWithNoCallAndNoErrorsEntryFromThisAdapter() {
        var result = run(REFERENCES, Map.of("r", List.of(reference("C-1", null, "RELEASE_REFUSED"), reference("C-2", "PRS-0001", "RELEASE_REFUSED"))));
        assertThat(entities(result)).extracting(entry -> entry.get("resolution")).containsExactly("RELEASE_REFUSED", "RELEASE_REFUSED");
        assertThat(entities(result)).extracting(entry -> entry.get("personnel")).containsOnlyNulls();
        assertThat(errors(result)).as("the mapping subgraph made the errors entry of the refused release").isEmpty();
        assertThat(STUB.calls()).as("the outcome is read, never guessed from the id: no call").isEmpty();
    }

    @Test
    void mappedWithoutAnIdentifierIsAContradictionAndIsUnavailableWithNoCall() {
        var result = run(REFERENCES, Map.of("r", List.of(reference("C-1", null, "MAPPED"))));
        assertThat(entities(result).get(0)).containsEntry("resolution", "UNAVAILABLE");
        assertThat(code(errors(result).get(0))).isEqualTo("UPSTREAM_BAD_RESPONSE");
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void aRepresentationWithoutAMappingOutcomeOrWithAnUnknownOneIsAnAdapterFault() {
        for (String outcome : new String[] {null, "BOGUS"}) {
            var result = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001", outcome))));
            assertThat(errors(result)).hasSize(1);
            assertThat(code(errors(result).get(0))).isEqualTo("INTERNAL_SERVER_ERROR");
        }
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void aCivilianAndACrewMemberBothResolveAndTheirDutyStatusIsNotAJudgment() {
        var list = entities(run(REFERENCES, Map.of("r", List.of(reference("C-3", "PRS-0003"), reference("C-6", "PRS-0006"), reference("C-9", "PRS-0005")))));
        assertThat(list).extracting(entry -> entry.get("resolution")).containsExactly("RESOLVED", "RESOLVED", "RESOLVED");
        assertThat(list).extracting(entry -> ((Map<String, Object>) entry.get("personnel")).get("dutyStatus")).containsExactly("ACTIVE", "DECEASED", "INACTIVE");
        assertThat(list.stream().map(entry -> ((Map<String, Object>) ((Map<String, Object>) entry.get("personnel")).get("details")).get("__typename")).toList())
                .containsExactly("CivilianDetails", "CrewDetails", "CrewDetails");
    }

    @Test
    void theWesleyCaseResolvesToTheSnapshotThatAnswers() {
        STUB.use(StubPersonnel.SMALL_001);
        var civilian = entities(run(REFERENCES, Map.of("r", List.of(reference("C-714", "PRS-0714"))))).get(0);
        assertThat((Map<String, Object>) ((Map<String, Object>) civilian.get("personnel")).get("details")).containsEntry("__typename", "CivilianDetails");
        STUB.use(StubPersonnel.SMALL_002);
        var crew = entities(run(REFERENCES, Map.of("r", List.of(reference("C-714", "PRS-0714"))))).get(0);
        assertThat((Map<String, Object>) ((Map<String, Object>) crew.get("personnel")).get("details")).containsEntry("__typename", "CrewDetails").containsEntry("rank", "ENSIGN");
    }

    @Test
    void aServerErrorAndATimeoutOfTheProbeAreUnavailableWithOneEntryPerReference() {
        for (boolean timeout : new boolean[] {true, false}) {
            STUB.reset();
            snapshots.clear();
            if (timeout) {
                STUB.route(PROBE, 200, StubPersonnel.envelope("<Other/>"), 2000);
            } else {
                STUB.route(PROBE, 500, "Internal Server Error");
            }
            var result = run(REFERENCES, Map.of("r", List.of(reference("A-1", "PRS-0002"), reference("A-2", "PRS-0003"), reference("A-3", "PRS-0001"))));
            var list = entities(result);
            assertThat(list).extracting(entry -> entry.get("resolution")).containsExactly("UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE");
            assertThat(list.get(0)).containsEntry("personnel", null);
            assertThat(errors(result)).as("one entry per reference whose lookup failed, however many fields are selected").hasSize(3);
            assertThat(codes(result)).containsExactly("SERVICE_UNAVAILABLE", "SERVICE_UNAVAILABLE", "SERVICE_UNAVAILABLE");
            assertThat(errors(result).get(0).get("message")).isEqualTo("Personnel service unavailable");
            assertThat(errors(result).get(0).get("path")).isNotNull();
            assertThat(STUB.calls()).as("one failed probe is the whole batch's answer: nothing is read").containsExactly(PROBE);
            assertThat(snapshots.cachedVersion()).isNull();
        }
    }

    @Test
    void theFaultsServiceUnavailableAndInternalErrorAreUnavailableToo() {
        for (String fault : List.of("ServiceUnavailable", "InternalError")) {
            STUB.reset();
            snapshots.clear();
            STUB.route(PROBE, 500, StubPersonnel.fault(fault, null));
            var result = run(REFERENCES, Map.of("r", List.of(reference("A-1", "PRS-0002"), reference("A-2", "PRS-0003"))));
            assertThat(entities(result)).as(fault).extracting(entry -> entry.get("resolution")).containsExactly("UNAVAILABLE", "UNAVAILABLE");
            assertThat(codes(result)).as(fault).containsExactly("SERVICE_UNAVAILABLE", "SERVICE_UNAVAILABLE");
        }
    }

    @Test
    void aMalformedAnswerIsAnUpstreamBadResponse() {
        STUB.route(PROBE, 200, "[1,2]");
        var result = run(REFERENCES, Map.of("r", List.of(reference("A-1", "PRS-0002"))));
        assertThat(entities(result).get(0)).containsEntry("resolution", "UNAVAILABLE");
        assertThat(code(errors(result).get(0))).isEqualTo("UPSTREAM_BAD_RESPONSE");
    }

    @Test
    void anIdTheMappingGaveAndTheServiceRefusesIsNotTheClientsFault() {
        var result = run(REFERENCES, Map.of("r", List.of(reference("A-1", "PRS-0000"), reference("A-2", "PRS-é001"))));
        assertThat(entities(result)).extracting(entry -> entry.get("resolution")).containsExactly("UNAVAILABLE", "UNAVAILABLE");
        assertThat(codes(result)).containsExactly("UPSTREAM_BAD_RESPONSE", "UPSTREAM_BAD_RESPONSE");
        assertThat(STUB.calls()).as("the id that cannot be sent as XML text is never sent").containsExactly("invalid");
    }

    @Test
    void theServiceIsNotCalledForFieldsThatAreNotSelected() {
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on PersonnelReference { localRef release } } }",
                Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        assertThat(entities(result).get(0)).containsEntry("localRef", "C-1").containsEntry("release", "1.1");
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void severalFieldsOfOneReferenceMakeOneProbeAndOneRead() {
        run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        assertThat(STUB.calls()).containsExactly(PROBE, READ);
    }

    @Test
    void aRepresentationThatLacksTheReleaseOrCarriesANonTextIdIsAnAdapterFault() {
        Map<String, Object> bad = new HashMap<>(reference("C-1", "PRS-0001"));
        bad.remove("release");
        var result = run(REFERENCES, Map.of("r", List.of(bad)));
        assertThat(errors(result)).hasSize(1);
        assertThat(code(errors(result).get(0))).isEqualTo("INTERNAL_SERVER_ERROR");
        Map<String, Object> number = new HashMap<>(reference("C-1", null));
        number.put("personnelId", 1);
        var second = run(REFERENCES, Map.of("r", List.of(number)));
        assertThat(code(errors(second).get(0))).isEqualTo("INTERNAL_SERVER_ERROR");
        assertThat(STUB.calls()).isEmpty();
    }

    // ---- the Personnel entity --------------------------------------------------------------------------------------

    @Test
    void thePersonnelEntityResolvesByItsKeyAndAnUnknownKeyIsNullWithNoEntry() {
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on Personnel { personnelId displayName " + DETAILS + " } } }",
                Map.of("r", List.of(Map.of("__typename", "Personnel", "personnelId", "PRS-0004"), Map.of("__typename", "Personnel", "personnelId", "PRS-9999"))));
        var list = entities(result);
        assertThat(list.get(0)).containsEntry("personnelId", "PRS-0004").containsEntry("displayName", "Mara Venn");
        assertThat((Map<String, Object>) list.get(0).get("details")).containsEntry("__typename", "CrewDetails").containsEntry("rank", "LIEUTENANT");
        assertThat(list.get(1)).isNull();
        assertThat(errors(result)).isEmpty();
    }

    @Test
    void aPersonnelEntityWhoseLookupFailsIsNullWithOneEntryEach() {
        STUB.route(PROBE, 500, "x");
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on Personnel { personnelId } } }",
                Map.of("r", List.of(Map.of("__typename", "Personnel", "personnelId", "PRS-0002"), Map.of("__typename", "Personnel", "personnelId", "PRS-0003"),
                        Map.of("__typename", "Personnel", "personnelId", "PRS-0001"))));
        assertThat(entities(result)).containsExactly(null, null, null);
        assertThat(codes(result)).containsExactly("SERVICE_UNAVAILABLE", "SERVICE_UNAVAILABLE", "SERVICE_UNAVAILABLE");
        assertThat(STUB.calls()).containsExactly(PROBE);
    }

    @Test
    void aKeyThatCannotBeSentIsAnEntryAndNoCall() {
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on Personnel { personnelId } } }",
                Map.of("r", List.of(Map.of("__typename", "Personnel", "personnelId", "PRS-é"))));
        assertThat(entities(result).get(0)).isNull();
        assertThat(codes(result)).containsExactly("UPSTREAM_BAD_RESPONSE");
        assertThat(STUB.calls()).isEmpty();
    }

    // ---- the snapshot kept in memory -------------------------------------------------------------------------------

    private static final String TWO_HUNDRED_FIFTY = "personnel-v2-generated-250";
    private static final String ELSEWHERE = "personnel-v2-generated-elsewhere";
    private static final String PAGE_2 = "list?offset=100&limit=100";
    private static final String PAGE_3 = "list?offset=200&limit=100";

    private List<Object> resolutions(Map<String, Object> result) {
        return entities(result).stream().map(entry -> entry.get("resolution")).toList();
    }

    @Test
    void aSecondBatchOfTheSameVersionCostsOneProbeAndNoRead() {
        run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        assertThat(STUB.calls()).containsExactly(PROBE, READ);
        STUB.reset();
        var again = run(REFERENCES, Map.of("r", List.of(reference("C-3", "PRS-0003"), reference("C-4", "PRS-0004"))));
        assertThat(resolutions(again)).containsExactly("RESOLVED", "RESOLVED");
        assertThat(STUB.calls()).as("the service is asked which version it serves, nothing more").containsExactly(PROBE);
        assertThat(snapshots.cachedVersion()).isEqualTo(StubPersonnel.SMALL_002);
    }

    @Test
    void aSnapshotLargerThanOnePageIsReadInPagesOf100AndEveryMemberIsServedFromMemory() {
        STUB.useGenerated(TWO_HUNDRED_FIFTY, 250);
        List<Map<String, Object>> references = new java.util.ArrayList<>();
        for (int number = 1; number <= 250; number++) {
            references.add(reference("C-" + number, String.format("PRS-%04d", number)));
        }
        references.add(reference("C-251", "PRS-0251"));
        var result = run(REFERENCES, Map.of("r", references));
        assertThat(errors(result)).isEmpty();
        assertThat(resolutions(result).subList(0, 250)).containsOnly("RESOLVED");
        assertThat(resolutions(result).get(250)).as("a person who is not in the snapshot is UNRESOLVED").isEqualTo("UNRESOLVED");
        assertThat(((Map<String, Object>) entities(result).get(249).get("personnel")).get("displayName")).isEqualTo("Cadet 250");
        assertThat(STUB.calls()).as("one probe, then the three pages of the one read, and not a call per person").containsExactly(PROBE, READ, PAGE_2, PAGE_3);
        assertThat(snapshots.cachedVersion()).isEqualTo(TWO_HUNDRED_FIFTY);
        STUB.reset();
        STUB.useGenerated(TWO_HUNDRED_FIFTY, 250);
        assertThat(resolutions(run(REFERENCES, Map.of("r", List.of(reference("C-9", "PRS-0009")))))).containsExactly("RESOLVED");
        assertThat(STUB.calls()).containsExactly(PROBE);
    }

    @Test
    void anOutageAfterTheSnapshotIsKeptIsStillUnavailableAndTheCopyServesAgainWhenTheServiceIsBack() {
        run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        STUB.reset();
        STUB.route(PROBE, 500, StubPersonnel.fault("ServiceUnavailable", null));
        var down = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"), reference("C-404", "PRS-9999"))));
        assertThat(resolutions(down)).as("a person the copy holds and one it does not: neither is answered while the service is down").containsExactly("UNAVAILABLE", "UNAVAILABLE");
        assertThat(codes(down)).containsExactly("SERVICE_UNAVAILABLE", "SERVICE_UNAVAILABLE");
        assertThat(STUB.calls()).containsExactly(PROBE);
        STUB.reset();
        var back = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        assertThat(resolutions(back)).containsExactly("RESOLVED");
        assertThat(STUB.calls()).as("the same version: the copy is kept through the outage and read no more").containsExactly(PROBE);
    }

    @Test
    void aNewDatasetVersionEmptiesTheCopyAndReadsTheNewSnapshot() {
        STUB.use(StubPersonnel.SMALL_001);
        var civilian = entities(run(REFERENCES, Map.of("r", List.of(reference("C-714", "PRS-0714"))))).get(0);
        assertThat((Map<String, Object>) ((Map<String, Object>) civilian.get("personnel")).get("details")).containsEntry("__typename", "CivilianDetails");
        assertThat(snapshots.cachedVersion()).isEqualTo(StubPersonnel.SMALL_001);
        STUB.reset();
        var crew = entities(run(REFERENCES, Map.of("r", List.of(reference("C-714", "PRS-0714"))))).get(0);
        assertThat((Map<String, Object>) ((Map<String, Object>) crew.get("personnel")).get("details")).containsEntry("__typename", "CrewDetails");
        assertThat(STUB.calls()).as("the probe saw another version, so the snapshot was read again").containsExactly(PROBE, READ);
        assertThat(snapshots.cachedVersion()).isEqualTo(StubPersonnel.SMALL_002);
    }

    @Test
    void aVersionThatChangesBetweenPagesStartsTheReadOverAtOffset0() {
        STUB.useGenerated(TWO_HUNDRED_FIFTY, 250);
        STUB.routeOnce(PAGE_2, 200, StubPersonnel.page(ELSEWHERE, StubPersonnel.generatedBlocks(101, 200), 250, 100, 100, true));
        var result = run(REFERENCES, Map.of("r", List.of(reference("C-250", "PRS-0250"))));
        assertThat(resolutions(result)).containsExactly("RESOLVED");
        assertThat(errors(result)).isEmpty();
        assertThat(STUB.calls()).containsExactly(PROBE, READ, PAGE_2, READ, PAGE_2, PAGE_3);
        assertThat(snapshots.cachedVersion()).isEqualTo(TWO_HUNDRED_FIFTY);
    }

    @Test
    void aVersionThatKeepsChangingIsUnavailableAndLeavesNoCopy() {
        STUB.useGenerated(TWO_HUNDRED_FIFTY, 250);
        STUB.route(PAGE_2, 200, StubPersonnel.page(ELSEWHERE, StubPersonnel.generatedBlocks(101, 200), 250, 100, 100, true));
        var result = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        assertThat(resolutions(result)).containsExactly("UNAVAILABLE");
        assertThat(codes(result)).containsExactly("SERVICE_UNAVAILABLE");
        assertThat(STUB.calls()).as("the probe, then the read and its restarts, each cut short at the page that changed")
                .containsExactly(PROBE, READ, PAGE_2, READ, PAGE_2, READ, PAGE_2, READ, PAGE_2);
        assertThat(snapshots.cachedVersion()).isNull();
    }

    @Test
    void aPageThatFailsLeavesNoCopyAndTheNextBatchReadsAgain() {
        STUB.useGenerated(TWO_HUNDRED_FIFTY, 250);
        STUB.routeOnce(PAGE_3, 500, "Internal Server Error");
        var failed = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"), reference("C-2", "PRS-0002"))));
        assertThat(resolutions(failed)).containsExactly("UNAVAILABLE", "UNAVAILABLE");
        assertThat(codes(failed)).containsExactly("SERVICE_UNAVAILABLE", "SERVICE_UNAVAILABLE");
        assertThat(snapshots.cachedVersion()).as("a half-read snapshot is never kept").isNull();

        var again = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        assertThat(resolutions(again)).containsExactly("RESOLVED");
        assertThat(snapshots.cachedVersion()).isEqualTo(TWO_HUNDRED_FIFTY);
    }

    @Test
    void aPageThatDoesNotAddUpIsNotUsed() {
        STUB.useGenerated(TWO_HUNDRED_FIFTY, 250);
        // Same version, but the second page counts 251 members where the first counted 250.
        STUB.route(PAGE_2, 200, StubPersonnel.page(TWO_HUNDRED_FIFTY, StubPersonnel.generatedBlocks(101, 200), 251, 100, 100, true));
        var result = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        assertThat(resolutions(result)).containsExactly("UNAVAILABLE");
        assertThat(codes(result)).containsExactly("UPSTREAM_BAD_RESPONSE");
        STUB.reset();
        snapshots.clear();
        STUB.useGenerated(TWO_HUNDRED_FIFTY, 250);
        // The second page repeats members of the first.
        STUB.route(PAGE_2, 200, StubPersonnel.page(TWO_HUNDRED_FIFTY, StubPersonnel.generatedBlocks(51, 150), 250, 100, 100, true));
        var repeated = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        assertThat(codes(repeated)).containsExactly("UPSTREAM_BAD_RESPONSE");
        assertThat(snapshots.cachedVersion()).isNull();
    }

    @Test
    void aListFaultOfNotFoundIsSomethingTheAdapterCannotUse() {
        STUB.route(PROBE, 500, StubPersonnel.fault("PersonnelNotFound", "personnelId"));
        var result = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        assertThat(resolutions(result)).containsExactly("UNAVAILABLE");
        assertThat(codes(result)).containsExactly("UPSTREAM_BAD_RESPONSE");
    }

    @Test
    void batchesThatStartTogetherReadTheSnapshotOnce() throws Exception {
        int batches = 6;
        ExecutorService pool = Executors.newFixedThreadPool(batches);
        try {
            CountDownLatch start = new CountDownLatch(1);
            List<Future<Map<String, Object>>> answers = new java.util.ArrayList<>();
            for (int index = 0; index < batches; index++) {
                answers.add(pool.submit(() -> {
                    start.await();
                    return run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"), reference("C-3", "PRS-0003"))));
                }));
            }
            start.countDown();
            for (Future<Map<String, Object>> answer : answers) {
                assertThat(resolutions(answer.get())).containsExactly("RESOLVED", "RESOLVED");
            }
        } finally {
            pool.shutdownNow();
        }
        assertThat(STUB.calls().stream().filter(READ::equals).count()).as("one read, however many batches found the copy missing").isEqualTo(1);
        assertThat(STUB.calls().stream().filter(PROBE::equals).count()).as("one probe per batch").isEqualTo(batches);
    }

    @Test
    void anIdTheContractCannotHoldIsNeverLookedUpInTheCopyAndTheServiceRefusesIt() {
        run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"))));
        STUB.reset();
        var result = run(REFERENCES, Map.of("r", List.of(reference("A-1", "PRS-0000"), reference("A-2", "prs-0001"))));
        assertThat(resolutions(result)).containsExactly("UNAVAILABLE", "UNAVAILABLE");
        assertThat(codes(result)).containsExactly("UPSTREAM_BAD_RESPONSE", "UPSTREAM_BAD_RESPONSE");
        assertThat(STUB.calls()).as("each id went to the service, which refused it").containsExactly("invalid", "invalid");
    }

    // ---- every request conforms to the contract --------------------------------------------------------------------

    @Test
    void everyRequestTheAdapterSendsConformsToTheXsdAndCarriesTheContractsSoapAction() {
        run(ONE, Map.of("id", "PRS-0001"));
        page("department", "SECURITY", "dutyStatus", "DECEASED", "offset", 0, "limit", 100);
        page("offset", 3, "limit", 4);
        run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0002"))));
        assertThat(STUB.invalid()).isEmpty();
        assertThat(STUB.calls()).containsExactly("get/PRS-0001", "list?department=SECURITY&dutyStatus=DECEASED&offset=0&limit=100", "list?offset=3&limit=4", PROBE, READ);
        assertThat(STUB.actions()).containsExactly("\"urn:graphql-federation-lab:personnel:v2:GetPersonnelMember\"",
                "\"urn:graphql-federation-lab:personnel:v2:ListPersonnelMembers\"", "\"urn:graphql-federation-lab:personnel:v2:ListPersonnelMembers\"",
                "\"urn:graphql-federation-lab:personnel:v2:ListPersonnelMembers\"", "\"urn:graphql-federation-lab:personnel:v2:ListPersonnelMembers\"");
    }

    // ---- the Federation entry points -------------------------------------------------------------------------------

    @Test
    void theServiceAnswersItsSdlWithFederation2() {
        var sdl = (String) ((Map<String, Object>) data(run("{ _service { sdl } }")).get("_service")).get("sdl");
        assertThat(sdl).contains("https://specs.apollo.dev/federation/v2.0");
        assertThat(sdl).contains("type PersonnelReference").contains("type Personnel ").contains("union PersonnelDetails = CivilianDetails | CrewDetails");
        assertThat(sdl).contains("enum Resolution").contains("UNMAPPED").contains("UNAVAILABLE").contains("type CivilianDetails");
    }

    @Test
    void theSchemaUsesOnlyKeyRequiresAndExternal() throws IOException {
        String schema;
        try (InputStream stream = getClass().getResourceAsStream("/graphql/schema.graphqls")) {
            schema = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
        String code = schema.lines().filter(line -> !line.stripLeading().startsWith("#")).collect(Collectors.joining("\n"));
        Matcher matcher = Pattern.compile("@(\\w+)").matcher(code);
        java.util.Set<String> used = new java.util.TreeSet<>();
        while (matcher.find()) {
            used.add(matcher.group(1));
        }
        assertThat(used).containsExactlyInAnyOrder("link", "key", "requires", "external");
        assertThat(code).contains("@key(fields: \"personnelId\")").contains("@key(fields: \"localRef release\")");
        assertThat(code).contains("@requires(fields: \"personnelId mappingOutcome\")").contains("personnelId: ID @external")
                .contains("mappingOutcome: MappingOutcome! @external");
        assertThat(code).as("the redundant id field is gone").doesNotContain("  id: ID");
        assertThat(code).as("resolution is nullable: a null means only that the router could not ask this adapter")
                .contains("resolution: Resolution @requires(fields: \"personnelId mappingOutcome\")").doesNotContain("resolution: Resolution!");
    }

    @Test
    void theAdapterNeverReturnsANullResolution() {
        var result = run(REFERENCES, Map.of("r", List.of(reference("C-1", "PRS-0001"), reference("C-404", "PRS-9999"), reference("C-77", null),
                reference("C-2", null, "RELEASE_REFUSED"), reference("C-3", null, "MAPPED"))));
        assertThat(entities(result)).extracting(entry -> entry.get("resolution"))
                .containsExactly("RESOLVED", "UNRESOLVED", "UNMAPPED", "RELEASE_REFUSED", "UNAVAILABLE");
    }

    @Test
    void theEnumsCarryExactlyTheContractsValues() throws IOException {
        String xsd = Files.readString(StubPersonnel.root().resolve("uss-enterprise/personnel-v2/contracts/personnel-v2.xsd"), StandardCharsets.UTF_8);
        String schema;
        try (InputStream stream = getClass().getResourceAsStream("/graphql/schema.graphqls")) {
            schema = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
        for (String name : List.of("Rank", "Department", "SecurityClearance", "DutyStatus")) {
            Matcher type = Pattern.compile("(?s)<xs:simpleType name=\"" + name + "\">(.*?)</xs:simpleType>").matcher(xsd);
            assertThat(type.find()).as(name).isTrue();
            List<String> contract = Pattern.compile("<xs:enumeration value=\"([A-Z_]+)\"/>").matcher(type.group(1)).results().map(m -> m.group(1)).toList();
            Matcher graph = Pattern.compile("(?s)enum " + name + " \\{(.*?)\\}").matcher(schema);
            assertThat(graph.find()).as(name).isTrue();
            List<String> declared = graph.group(1).lines().map(String::strip).filter(line -> !line.isEmpty()).toList();
            assertThat(declared).as(name).containsExactlyElementsOf(contract);
        }
    }

    @Test
    void theClientNeverThrows() throws IOException {
        int closed;
        try (ServerSocket socket = new ServerSocket(0, 1, java.net.InetAddress.getLoopbackAddress())) {
            closed = socket.getLocalPort();
        }
        PersonnelClient client = new PersonnelClient("http://127.0.0.1:" + closed + "/soap/personnel-v2", 300, 500);
        HttpResult get = client.get("PRS-0001");
        assertThat(get.failed()).isTrue();
        assertThat(client.list(null, null, 0, 20).failed()).isTrue();
        assertThat(PersonnelCalls.outcome(get, body -> body).errorCode()).isEqualTo(lab.federation.common.ErrorCode.SERVICE_UNAVAILABLE);
    }
}
