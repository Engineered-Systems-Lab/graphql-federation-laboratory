package lab.federation.adapters.assets;

import static org.assertj.core.api.Assertions.assertThat;

import graphql.ExecutionInput;
import java.io.IOException;
import java.io.InputStream;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
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

/** The adapter against a stub of the Assets service: every outcome, the errors entries, the paging and the Federation entry points. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@SuppressWarnings("unchecked")
class AssetsAdapterTest {
    private static final StubAssets STUB = start();

    private static StubAssets start() {
        try {
            return new StubAssets();
        } catch (IOException error) {
            throw new IllegalStateException(error);
        }
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("assets.service-url", STUB::url);
        registry.add("assets.connect-timeout-ms", () -> "300");
        registry.add("assets.read-timeout-ms", () -> "500");
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

    private static String asset(String id, String status) {
        return "{\"assetId\":\"" + id + "\",\"kind\":\"STARSHIP\",\"category\":\"VEHICLE\",\"name\":\"Ship " + id
                + "\",\"description\":\"A ship.\",\"status\":\"" + status + "\",\"parentAssetId\":null}";
    }

    private static String page(int offset, int limit, String... items) {
        return "{\"items\":[" + String.join(",", items) + "],\"offset\":" + offset + ",\"limit\":" + limit + ",\"total\":" + items.length + "}";
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> run(String query, Map<String, Object> variables) {
        return source.graphQl().execute(ExecutionInput.newExecutionInput(query).variables(variables).build()).toSpecification();
    }

    private Map<String, Object> run(String query) {
        return run(query, Map.of());
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> data(Map<String, Object> result) {
        return (Map<String, Object>) result.get("data");
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> errors(Map<String, Object> result) {
        return result.get("errors") == null ? List.of() : (List<Map<String, Object>>) result.get("errors");
    }

    private static String code(Map<String, Object> error) {
        @SuppressWarnings("unchecked")
        Map<String, Object> extensions = (Map<String, Object>) error.get("extensions");
        return (String) extensions.get("code");
    }

    /** The representation the router sends: the mapping subgraph's assetId and mappingOutcome. A null id is NO_ENTRY, a non-null one MAPPED. */
    private static Map<String, Object> reference(String localRef, String assetId) {
        return reference(localRef, assetId, assetId == null ? "NO_ENTRY" : "MAPPED");
    }

    private static Map<String, Object> reference(String localRef, String assetId, String mappingOutcome) {
        Map<String, Object> representation = new java.util.HashMap<>();
        representation.put("__typename", "AssetReference");
        representation.put("localRef", localRef);
        representation.put("release", "1.0");
        representation.put("assetId", assetId);
        if (mappingOutcome != null) {
            representation.put("mappingOutcome", mappingOutcome);
        }
        return representation;
    }

    private static final String REFERENCES = "query($r: [_Any!]!) { _entities(representations: $r) { ... on AssetReference "
            + "{ localRef assetId mappingOutcome resolution asset { assetId name status } } } }";

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> entities(Map<String, Object> result) {
        return (List<Map<String, Object>>) data(result).get("_entities");
    }

    // ---- the four outcomes -----------------------------------------------------------------------------------------

    @Test
    void resolvedUnresolvedAndUnmappedAreDataWithOneCallEach() {
        STUB.route("/assets/AST-0001", 200, asset("AST-0001", "ACTIVE"));
        STUB.route("/assets/AST-0404", 404, StubAssets.ASSET_NOT_FOUND);
        var result = run(REFERENCES, Map.of("r", List.of(reference("SH-17", "AST-0001"), reference("EQ-97", "AST-0404"), reference("XX-99", null))));
        var list = entities(result);
        assertThat(list.get(0)).containsEntry("resolution", "RESOLVED").containsEntry("assetId", "AST-0001").containsEntry("mappingOutcome", "MAPPED");
        assertThat(((Map<String, Object>) list.get(0).get("asset"))).containsEntry("assetId", "AST-0001").containsEntry("status", "ACTIVE");
        assertThat(list.get(1)).containsEntry("resolution", "UNRESOLVED").containsEntry("assetId", "AST-0404").containsEntry("asset", null);
        assertThat(list.get(2)).containsEntry("resolution", "UNMAPPED").containsEntry("assetId", null).containsEntry("mappingOutcome", "NO_ENTRY").containsEntry("asset", null);
        assertThat(errors(result)).as("UNRESOLVED and UNMAPPED are data and add no errors entry").isEmpty();
        assertThat(STUB.calls()).as("one call per mapped reference, none for UNMAPPED").containsExactly("/assets/AST-0001", "/assets/AST-0404");
    }

    @Test
    void aRefusedReleaseIsItsOwnResolutionWithNoCallAndNoErrorsEntryFromThisAdapter() {
        var result = run(REFERENCES, Map.of("r", List.of(reference("SH-17", null, "RELEASE_REFUSED"), reference("SH-18", "AST-0001", "RELEASE_REFUSED"))));
        assertThat(entities(result)).extracting(entry -> entry.get("resolution")).containsExactly("RELEASE_REFUSED", "RELEASE_REFUSED");
        assertThat(entities(result)).extracting(entry -> entry.get("asset")).containsOnlyNulls();
        assertThat(entities(result).get(0)).containsEntry("mappingOutcome", "RELEASE_REFUSED");
        assertThat(errors(result)).as("the mapping subgraph made the errors entry of the refused release").isEmpty();
        assertThat(STUB.calls()).as("the outcome is read, never guessed from the id: no call").isEmpty();
    }

    @Test
    void mappedWithoutAnIdentifierIsAContradictionAndIsUnavailableWithNoCall() {
        var result = run(REFERENCES, Map.of("r", List.of(reference("SH-17", null, "MAPPED"))));
        assertThat(entities(result).get(0)).containsEntry("resolution", "UNAVAILABLE");
        assertThat(code(errors(result).get(0))).isEqualTo("UPSTREAM_BAD_RESPONSE");
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void aRepresentationWithoutAMappingOutcomeOrWithAnUnknownOneIsAnAdapterFault() {
        for (String outcome : new String[] {null, "BOGUS"}) {
            var result = run(REFERENCES, Map.of("r", List.of(reference("SH-17", "AST-0001", outcome))));
            assertThat(errors(result)).hasSize(1);
            assertThat(code(errors(result).get(0))).isEqualTo("INTERNAL_SERVER_ERROR");
        }
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void destroyedAndMissingAssetsAreResolvedWithTheirStatus() {
        STUB.route("/assets/AST-0020", 200, asset("AST-0020", "DESTROYED"));
        STUB.route("/assets/AST-0021", 200, asset("AST-0021", "MISSING"));
        var list = entities(run(REFERENCES, Map.of("r", List.of(reference("SH-53", "AST-0020"), reference("EQ-86", "AST-0021")))));
        assertThat(list).extracting(entry -> entry.get("resolution")).containsExactly("RESOLVED", "RESOLVED");
        assertThat(list).extracting(entry -> ((Map<String, Object>) entry.get("asset")).get("status")).containsExactly("DESTROYED", "MISSING");
    }

    @Test
    void aPathNotFoundIsNotUnresolved() {
        STUB.route("/assets/AST-0007", 404, StubAssets.PATH_NOT_FOUND);
        var result = run(REFERENCES, Map.of("r", List.of(reference("EQ-1", "AST-0007"))));
        assertThat(entities(result).get(0)).containsEntry("resolution", "UNAVAILABLE").containsEntry("asset", null);
        assertThat(errors(result)).hasSize(1);
        assertThat(code(errors(result).get(0))).isEqualTo("UPSTREAM_BAD_RESPONSE");
    }

    @Test
    void aServerErrorAndATimeoutAreUnavailableWithOneEntryPerFailedCall() {
        STUB.route("/assets/AST-0500", 200, asset("AST-0500", "ACTIVE"), 2000);
        STUB.route("/assets/AST-0501", 500, "{\"code\":\"INTERNAL_ERROR\",\"message\":\"x\"}");
        STUB.route("/assets/AST-0001", 200, asset("AST-0001", "ACTIVE"));
        var result = run(REFERENCES, Map.of("r", List.of(reference("A-1", "AST-0500"), reference("A-2", "AST-0501"), reference("A-3", "AST-0001"))));
        var list = entities(result);
        assertThat(list).extracting(entry -> entry.get("resolution")).containsExactly("UNAVAILABLE", "UNAVAILABLE", "RESOLVED");
        assertThat(list.get(0)).containsEntry("asset", null);
        assertThat(errors(result)).as("two failed calls, two entries, however many fields are selected").hasSize(2);
        assertThat(errors(result)).extracting(CODE).containsExactly("SERVICE_UNAVAILABLE", "SERVICE_UNAVAILABLE");
        assertThat(errors(result).get(0).get("message")).isEqualTo("Assets service unavailable");
        assertThat(errors(result).get(0).get("path")).isNotNull();
    }

    private static final java.util.function.Function<Map<String, Object>, Object> CODE = AssetsAdapterTest::code;

    @Test
    void aMalformedAnswerIsAnUpstreamBadResponse() {
        STUB.route("/assets/AST-0009", 200, "[1,2]");
        var result = run(REFERENCES, Map.of("r", List.of(reference("A-1", "AST-0009"))));
        assertThat(entities(result).get(0)).containsEntry("resolution", "UNAVAILABLE");
        assertThat(code(errors(result).get(0))).isEqualTo("UPSTREAM_BAD_RESPONSE");
    }

    @Test
    void theServiceIsNotCalledForFieldsThatAreNotSelected() {
        STUB.route("/assets/AST-0001", 200, asset("AST-0001", "ACTIVE"));
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on AssetReference { localRef release assetId mappingOutcome } } }",
                Map.of("r", List.of(reference("SH-17", "AST-0001"))));
        assertThat(entities(result).get(0)).containsEntry("localRef", "SH-17").containsEntry("assetId", "AST-0001").containsEntry("mappingOutcome", "MAPPED");
        assertThat(STUB.calls()).as("the fields the mapping owns need no call to the service").isEmpty();
    }

    @Test
    void severalFieldsOfOneReferenceMakeOneCall() {
        STUB.route("/assets/AST-0001", 200, asset("AST-0001", "ACTIVE"));
        run(REFERENCES, Map.of("r", List.of(reference("SH-17", "AST-0001"))));
        assertThat(STUB.calls()).containsExactly("/assets/AST-0001");
    }

    @Test
    void aRepresentationThatLacksTheReleaseIsAnAdapterFault() {
        Map<String, Object> bad = new java.util.HashMap<>(reference("SH-17", "AST-0001"));
        bad.remove("release");
        var result = run(REFERENCES, Map.of("r", List.of(bad)));
        assertThat(errors(result)).hasSize(1);
        assertThat(code(errors(result).get(0))).isEqualTo("INTERNAL_SERVER_ERROR");
    }

    // ---- the Asset entity and the queries --------------------------------------------------------------------------

    @Test
    void theAssetEntityResolvesByItsKeyAndAnUnknownKeyIsNull() {
        STUB.route("/assets/AST-0002", 200, asset("AST-0002", "MAINTENANCE"));
        STUB.route("/assets/AST-9999", 404, StubAssets.ASSET_NOT_FOUND);
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on Asset { assetId name status kind category description parentAssetId } } }",
                Map.of("r", List.of(Map.of("__typename", "Asset", "assetId", "AST-0002"), Map.of("__typename", "Asset", "assetId", "AST-9999"))));
        assertThat(entities(result).get(0)).containsEntry("assetId", "AST-0002").containsEntry("status", "MAINTENANCE").containsEntry("kind", "STARSHIP");
        assertThat(entities(result).get(1)).isNull();
        assertThat(errors(result)).isEmpty();
    }

    @Test
    void theAssetQuery() {
        STUB.route("/assets/AST-0002", 200, asset("AST-0002", "ACTIVE"));
        STUB.route("/assets/AST-9999", 404, StubAssets.ASSET_NOT_FOUND);
        STUB.route("/assets/AST-0500", 500, "{}");
        STUB.route("/assets/sh-17", 400, "{\"code\":\"INVALID_ASSET_ID\",\"message\":\"x\"}");
        assertThat(((Map<String, Object>) data(run("{ asset(assetId: \"AST-0002\") { assetId name } }")).get("asset"))).containsEntry("name", "Ship AST-0002");
        var missing = run("{ asset(assetId: \"AST-9999\") { assetId } }");
        assertThat(data(missing)).containsEntry("asset", null);
        assertThat(errors(missing)).isEmpty();
        var down = run("{ asset(assetId: \"AST-0500\") { assetId } }");
        assertThat(data(down)).containsEntry("asset", null);
        assertThat(code(errors(down).get(0))).isEqualTo("SERVICE_UNAVAILABLE");
        var malformed = run("{ asset(assetId: \"sh-17\") { assetId } }");
        assertThat(code(errors(malformed).get(0))).isEqualTo("BAD_USER_INPUT");
    }

    // ---- Asset.parent --------------------------------------------------------------------------------------------------

    private static String assetWithParent(String id, String parent) {
        return asset(id, "ACTIVE").replace("\"parentAssetId\":null", "\"parentAssetId\":" + (parent == null ? "null" : "\"" + parent + "\""));
    }

    private static final String CHAIN = "{ asset(assetId: \"AST-0004\") { assetId parent { assetId parent { assetId parent { assetId parent { assetId } } } } } }";

    @Test
    void theParentChainIsOneQueryWithOneCallPerLevelAndEndsInNull() {
        STUB.route("/assets/AST-0004", 200, assetWithParent("AST-0004", "AST-0023"));
        STUB.route("/assets/AST-0023", 200, assetWithParent("AST-0023", "AST-0029"));
        STUB.route("/assets/AST-0029", 200, assetWithParent("AST-0029", null));
        var result = run(CHAIN);
        assertThat(errors(result)).isEmpty();
        var root = (Map<String, Object>) data(result).get("asset");
        var second = (Map<String, Object>) root.get("parent");
        var third = (Map<String, Object>) second.get("parent");
        assertThat(List.of(root.get("assetId"), second.get("assetId"), third.get("assetId"))).containsExactly("AST-0004", "AST-0023", "AST-0029");
        assertThat(third.get("parent")).as("the top of the chain has no parent").isNull();
        assertThat(STUB.calls()).as("one call per level, none for a missing parentAssetId").containsExactly("/assets/AST-0004", "/assets/AST-0023", "/assets/AST-0029");
    }

    @Test
    void theParentIsNotFetchedWhenItIsNotSelected() {
        STUB.route("/assets/AST-0004", 200, assetWithParent("AST-0004", "AST-0023"));
        run("{ asset(assetId: \"AST-0004\") { assetId parentAssetId } }");
        assertThat(STUB.calls()).containsExactly("/assets/AST-0004");
    }

    @Test
    void aParentThatDoesNotExistIsNullWithNoErrorsEntry() {
        STUB.route("/assets/AST-0004", 200, assetWithParent("AST-0004", "AST-0999"));
        STUB.route("/assets/AST-0999", 404, StubAssets.ASSET_NOT_FOUND);
        var result = run("{ asset(assetId: \"AST-0004\") { assetId parent { assetId } } }");
        assertThat((Map<String, Object>) data(result).get("asset")).containsEntry("assetId", "AST-0004").containsEntry("parent", null);
        assertThat(errors(result)).isEmpty();
    }

    @Test
    void aFailedParentCallIsNullWithOneServiceUnavailableEntryForThatCall() {
        STUB.route("/assets/AST-0004", 200, assetWithParent("AST-0004", "AST-0023"));
        STUB.route("/assets/AST-0023", 500, "{}");
        var result = run("{ asset(assetId: \"AST-0004\") { assetId parent { assetId parent { assetId } } } }");
        assertThat((Map<String, Object>) data(result).get("asset")).containsEntry("assetId", "AST-0004").containsEntry("parent", null);
        assertThat(errors(result)).hasSize(1);
        assertThat(code(errors(result).get(0))).isEqualTo("SERVICE_UNAVAILABLE");
        assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("asset", "parent"));
        assertThat(STUB.calls()).as("no call for the parent of a parent that failed").containsExactly("/assets/AST-0004", "/assets/AST-0023");
    }

    @Test
    void theParentOfAnAssetReachedThroughAReferenceFollowsTheSameRules() {
        STUB.route("/assets/AST-0004", 200, assetWithParent("AST-0004", "AST-0023"));
        STUB.route("/assets/AST-0023", 200, assetWithParent("AST-0023", null));
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on AssetReference { asset { assetId parent { assetId } } } } }",
                Map.of("r", List.of(reference("EQ-64", "AST-0004"))));
        var asset = (Map<String, Object>) entities(result).get(0).get("asset");
        assertThat((Map<String, Object>) asset.get("parent")).containsEntry("assetId", "AST-0023");
        assertThat(errors(result)).isEmpty();
    }

    // ---- paging ----------------------------------------------------------------------------------------------------

    @Test
    void aDefaultPageIsOneCallWithOffset0AndLimit20() {
        STUB.route("/assets?offset=0&limit=20", 200, page(0, 20, asset("AST-0001", "ACTIVE")));
        var result = run("{ assets { assetId } }");
        assertThat(data(result).get("assets")).isEqualTo(List.of(Map.of("assetId", "AST-0001")));
        assertThat(STUB.calls()).containsExactly("/assets?offset=0&limit=20");
    }

    @Test
    void theFiltersReachTheServiceInOrder() {
        STUB.route("/assets?kind=SHUTTLE&status=DESTROYED&parentAssetId=AST-0003&offset=5&limit=10", 200, page(5, 10));
        var result = run("{ assets(kind: SHUTTLE, status: DESTROYED, parentAssetId: \"AST-0003\", offset: 5, limit: 10) { assetId } }");
        assertThat(data(result).get("assets")).isEqualTo(List.of());
        assertThat(errors(result)).isEmpty();
        assertThat(STUB.calls()).containsExactly("/assets?kind=SHUTTLE&status=DESTROYED&parentAssetId=AST-0003&offset=5&limit=10");
        STUB.reset();
        STUB.route("/assets?category=EQUIPMENT&offset=0&limit=20", 200, page(0, 20));
        run("{ assets(category: EQUIPMENT) { assetId } }");
        assertThat(STUB.calls()).containsExactly("/assets?category=EQUIPMENT&offset=0&limit=20");
    }

    @Test
    void aPageAboveFiftyTakesTwoCallsInOrder() {
        STUB.route("/assets?offset=10&limit=50", 200, page(10, 50, asset("AST-0001", "ACTIVE")));
        STUB.route("/assets?offset=60&limit=25", 200, page(60, 25, asset("AST-0002", "ACTIVE")));
        var result = run("{ assets(offset: 10, limit: 75) { assetId } }");
        assertThat(data(result).get("assets")).isEqualTo(List.of(Map.of("assetId", "AST-0001"), Map.of("assetId", "AST-0002")));
        assertThat(STUB.calls()).containsExactly("/assets?offset=10&limit=50", "/assets?offset=60&limit=25");
        STUB.reset();
        STUB.route("/assets?offset=0&limit=50", 200, page(0, 50));
        STUB.route("/assets?offset=50&limit=50", 200, page(50, 50));
        run("{ assets(limit: 100) { assetId } }");
        assertThat(STUB.calls()).containsExactly("/assets?offset=0&limit=50", "/assets?offset=50&limit=50");
    }

    @Test
    void aLimitAbove100OrBelow1OrANegativeOffsetIsBadUserInputWithNoCall() {
        for (String arguments : List.of("limit: 101", "limit: 0", "offset: -1")) {
            var result = run("{ assets(" + arguments + ") { assetId } }");
            assertThat(data(result)).containsEntry("assets", null);
            assertThat(errors(result)).hasSize(1);
            assertThat(code(errors(result).get(0))).isEqualTo("BAD_USER_INPUT");
        }
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    void ifTheSecondCallOfAPageFailsTheWholeListIsNullWithOneEntry() {
        STUB.route("/assets?offset=0&limit=50", 200, page(0, 50, asset("AST-0001", "ACTIVE")));
        STUB.route("/assets?offset=50&limit=25", 500, "{}");
        var result = run("{ assets(limit: 75) { assetId } }");
        assertThat(data(result)).containsEntry("assets", null);
        assertThat(errors(result)).hasSize(1);
        assertThat(code(errors(result).get(0))).isEqualTo("SERVICE_UNAVAILABLE");
        assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("assets"));
    }

    @Test
    void ifTheFirstCallFailsTheSecondIsNotMade() {
        STUB.route("/assets?offset=0&limit=50", 500, "{}");
        var result = run("{ assets(limit: 100) { assetId } }");
        assertThat(data(result)).containsEntry("assets", null);
        assertThat(errors(result)).hasSize(1);
        assertThat(STUB.calls()).containsExactly("/assets?offset=0&limit=50");
    }

    // ---- the Federation entry points -------------------------------------------------------------------------------

    @Test
    void theServiceAnswersItsSdlWithFederation2() {
        var sdl = (String) ((Map<String, Object>) data(run("{ _service { sdl } }")).get("_service")).get("sdl");
        assertThat(sdl).contains("https://specs.apollo.dev/federation/v2.0");
        assertThat(sdl).contains("type AssetReference").contains("type Asset ").contains("enum Resolution").contains("enum MappingOutcome");
        assertThat(sdl).contains("UNMAPPED").contains("UNAVAILABLE").contains("RELEASE_REFUSED").contains("parent: Asset");
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
        assertThat(code).contains("@key(fields: \"assetId\")").contains("@key(fields: \"localRef release\")");
        assertThat(code).contains("@requires(fields: \"assetId mappingOutcome\")").contains("assetId: ID @external")
                .contains("mappingOutcome: MappingOutcome! @external");
        assertThat(code).as("the redundant id field is gone").doesNotContain("  id: ID");
        assertThat(code).as("resolution is nullable: a null means only that the router could not ask this adapter")
                .contains("resolution: Resolution @requires(fields: \"assetId mappingOutcome\")").doesNotContain("resolution: Resolution!");
    }

    @Test
    void theAdapterNeverReturnsANullResolution() {
        STUB.route("/assets/AST-0001", 200, asset("AST-0001", "ACTIVE"));
        STUB.route("/assets/AST-0404", 404, StubAssets.ASSET_NOT_FOUND);
        STUB.route("/assets/AST-0500", 500, "{}");
        var result = run(REFERENCES, Map.of("r", List.of(reference("A-1", "AST-0001"), reference("A-2", "AST-0404"), reference("A-3", null),
                reference("A-4", null, "RELEASE_REFUSED"), reference("A-5", "AST-0500"), reference("A-6", null, "MAPPED"))));
        assertThat(entities(result)).extracting(entry -> entry.get("resolution"))
                .containsExactly("RESOLVED", "UNRESOLVED", "UNMAPPED", "RELEASE_REFUSED", "UNAVAILABLE", "UNAVAILABLE");
    }

    @Test
    void theClientNeverThrows() throws IOException {
        int closed;
        try (ServerSocket socket = new ServerSocket(0, 1, java.net.InetAddress.getLoopbackAddress())) {
            closed = socket.getLocalPort();
        }
        HttpResult result = new AssetsClient("http://127.0.0.1:" + closed, 300, 500).asset("AST-0001");
        assertThat(result.failed()).isTrue();
    }
}
