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
    void theDeprecatedListAtTheLargestOffsetIsEmptyAndItsSecondCallDoesNotOverflow() {
        STUB.route("/assets?offset=2147483647&limit=50", 200, "{\"items\":[],\"offset\":2147483647,\"limit\":50,\"total\":32}");
        STUB.route("/assets?offset=2147483697&limit=50", 200, "{\"items\":[],\"offset\":2147483697,\"limit\":50,\"total\":32}");
        var result = run("{ assets(offset: 2147483647, limit: 100) { assetId } }");
        assertThat(errors(result)).isEmpty();
        assertThat(data(result).get("assets")).isEqualTo(List.of());
        assertThat(STUB.calls()).containsExactly("/assets?offset=2147483647&limit=50", "/assets?offset=2147483697&limit=50");
        STUB.reset();
        STUB.route("/assets?offset=2147483600&limit=50", 200, "{\"items\":[],\"offset\":2147483600,\"limit\":50,\"total\":32}");
        STUB.route("/assets?offset=2147483650&limit=50", 200, "{\"items\":[],\"offset\":2147483650,\"limit\":50,\"total\":32}");
        assertThat(errors(run("{ assets(offset: 2147483600, limit: 100) { assetId } }"))).isEmpty();
        assertThat(STUB.calls()).containsExactly("/assets?offset=2147483600&limit=50", "/assets?offset=2147483650&limit=50");
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

    // ---- the page field -------------------------------------------------------------------------------------------

    private static final String PAGE_FIELDS = "items { assetId } totalCount offset limit hasMore";

    /** A service answer of `count` assets numbered from `offset`, with the given total text (any JSON value). */
    private static String counted(int offset, int limit, String total, int count) {
        String[] items = new String[count];
        for (int index = 0; index < count; index++) {
            items[index] = asset(String.format("AST-%04d", offset + index + 1), "ACTIVE");
        }
        return "{\"items\":[" + String.join(",", items) + "],\"offset\":" + offset + ",\"limit\":" + limit + ",\"total\":" + total + "}";
    }

    /** The routes of a dataset of `total` assets for the calls of the window [offset, offset + limit). */
    private static void dataset(int total, int offset, int limit) {
        for (int from = 0; from < limit; from += 50) {
            int size = Math.min(50, limit - from);
            int start = offset + from;
            STUB.route("/assets?offset=" + start + "&limit=" + size, 200, counted(start, size, Integer.toString(total), Math.max(0, Math.min(size, total - start))));
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> page(Map<String, Object> result) {
        return (Map<String, Object>) data(result).get("assetsPage");
    }

    @SuppressWarnings("unchecked")
    private static List<String> idsIn(Object items) {
        return ((List<Map<String, Object>>) items).stream().map(asset -> (String) asset.get("assetId")).toList();
    }

    /** The page and the deprecated list over the same routes: the same calls, the same items. */
    private Map<String, Object> pageAgainstList(int total, int offset, int limit) {
        dataset(total, offset, limit);
        String window = "(offset: " + offset + ", limit: " + limit + ")";
        var list = run("{ assets" + window + " { assetId } }");
        assertThat(errors(list)).isEmpty();
        List<String> listCalls = STUB.calls();
        STUB.reset();
        dataset(total, offset, limit);
        var result = run("{ assetsPage" + window + " { " + PAGE_FIELDS + " } }");
        assertThat(errors(result)).as(window).isEmpty();
        assertThat(STUB.calls()).as("the page makes the list's calls: " + window).isEqualTo(listCalls);
        STUB.reset();
        Map<String, Object> page = page(result);
        assertThat(idsIn(page.get("items"))).as(window).isEqualTo(idsIn(data(list).get("assets")));
        assertThat(page).as(window).containsEntry("totalCount", total).containsEntry("offset", offset).containsEntry("limit", limit);
        return page;
    }

    @Test
    void thePageHasTheListsItemsAndCallsAndTheServicesTotal() {
        assertThat(pageAgainstList(173, 0, 20)).containsEntry("hasMore", true);
        assertThat(idsIn(pageAgainstList(173, 7, 13).get("items"))).startsWith("AST-0008").hasSize(13);
        assertThat(idsIn(pageAgainstList(173, 10, 75).get("items"))).hasSize(75);
        assertThat(idsIn(pageAgainstList(173, 30, 100).get("items"))).hasSize(100).endsWith("AST-0130");
    }

    @Test
    void aFilteredTotalIsTheServicesTotalForTheFilters() {
        STUB.route("/assets?kind=SHUTTLE&status=DESTROYED&offset=5&limit=10", 200, counted(5, 10, "12", 7));
        var result = run("{ assetsPage(kind: SHUTTLE, status: DESTROYED, offset: 5, limit: 10) { " + PAGE_FIELDS + " } }");
        assertThat(errors(result)).isEmpty();
        assertThat(page(result)).containsEntry("totalCount", 12).containsEntry("hasMore", false);
        assertThat(idsIn(page(result).get("items"))).hasSize(7);
        assertThat(STUB.calls()).containsExactly("/assets?kind=SHUTTLE&status=DESTROYED&offset=5&limit=10");
    }

    @Test
    void zeroMatchesIsAnEmptyPageWithTotalZeroAndNoMore() {
        assertThat(pageAgainstList(0, 0, 20)).containsEntry("items", List.of()).containsEntry("hasMore", false);
        assertThat(pageAgainstList(0, 0, 100)).containsEntry("items", List.of()).containsEntry("hasMore", false);
    }

    @Test
    void aPageBeyondTheEndIsEmptyWithTheWholeTotal() {
        assertThat(pageAgainstList(173, 173, 20)).containsEntry("items", List.of()).containsEntry("hasMore", false);
        assertThat(pageAgainstList(173, 5000, 100)).containsEntry("items", List.of()).containsEntry("hasMore", false);
        dataset(173, 2000000000, 5);
        var far = run("{ assetsPage(offset: 2000000000, limit: 5) { " + PAGE_FIELDS + " } }");
        assertThat(errors(far)).isEmpty();
        assertThat(page(far)).containsEntry("items", List.of()).containsEntry("totalCount", 173).containsEntry("hasMore", false);
    }

    @Test
    void hasMoreIsFalseExactlyFromTheLastRow() {
        assertThat(pageAgainstList(173, 153, 20)).containsEntry("hasMore", false);
        assertThat(pageAgainstList(173, 152, 20)).containsEntry("hasMore", true);
        assertThat(pageAgainstList(173, 172, 1)).containsEntry("hasMore", false);
        assertThat(pageAgainstList(173, 171, 1)).containsEntry("hasMore", true);
        assertThat(pageAgainstList(100, 0, 100)).containsEntry("hasMore", false);
        assertThat(pageAgainstList(101, 0, 100)).containsEntry("hasMore", true);
        assertThat(pageAgainstList(50, 0, 100)).containsEntry("hasMore", false);
        assertThat(pageAgainstList(173, 150, 100)).containsEntry("hasMore", false);
    }

    @Test
    void countMetadataTheAdapterCannotUseIsOneUpstreamBadResponseForThePageAndChangesNothingForTheList() {
        Map<String, String> cases = new java.util.LinkedHashMap<>();
        cases.put("a missing total", "{\"items\":[" + asset("AST-0001", "ACTIVE") + "],\"offset\":0,\"limit\":20}");
        cases.put("a null total", counted(0, 20, "null", 1));
        cases.put("a string total", counted(0, 20, "\"1\"", 1));
        cases.put("a float total", counted(0, 20, "1.0", 1));
        cases.put("a boolean total", counted(0, 20, "true", 1));
        cases.put("a negative total", counted(0, 20, "-1", 1));
        cases.put("a total above a GraphQL Int", counted(0, 20, "2147483648", 20));
        cases.put("a total far above a long", counted(0, 20, "99999999999999999999999", 20));
        cases.put("fewer rows than the total says", counted(0, 20, "30", 5));
        cases.put("more rows than the total says", counted(0, 20, "3", 5));
        cases.put("rows on an empty total", counted(0, 20, "0", 2));
        cases.put("another offset echoed", counted(0, 20, "1", 1).replace("\"offset\":0", "\"offset\":1"));
        cases.put("another limit echoed", counted(0, 20, "1", 1).replace("\"limit\":20", "\"limit\":50"));
        for (var entry : cases.entrySet()) {
            STUB.route("/assets?offset=0&limit=20", 200, entry.getValue());
            var result = run("{ assetsPage { " + PAGE_FIELDS + " } }");
            assertThat(data(result)).as(entry.getKey()).containsEntry("assetsPage", null);
            assertThat(errors(result)).as(entry.getKey()).hasSize(1);
            assertThat(code(errors(result).get(0))).as(entry.getKey()).isEqualTo("UPSTREAM_BAD_RESPONSE");
            assertThat((String) errors(result).get(0).get("message")).as(entry.getKey()).startsWith(AssetsGraph.COUNT_FAULT);
            assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("assetsPage"));
            assertThat(errors(run("{ assets { assetId } }"))).as("the deprecated list does not check the counts: " + entry.getKey()).isEmpty();
            STUB.reset();
        }
        STUB.route("/assets?offset=0&limit=50", 200, counted(0, 50, "75", 50));
        STUB.route("/assets?offset=50&limit=50", 200, counted(50, 50, "76", 26));
        var differing = run("{ assetsPage(limit: 100) { " + PAGE_FIELDS + " } }");
        assertThat(data(differing)).containsEntry("assetsPage", null);
        assertThat((String) errors(differing).get(0).get("message")).contains("different totals");
        assertThat(errors(run("{ assets(limit: 100) { assetId } }"))).isEmpty();
    }

    @Test
    void anOutageATimeoutOrABadBodyMakesTheWholePageNullWithOneEntry() {
        STUB.route("/assets?offset=0&limit=20", 500, "{}");
        var down = run("{ assetsPage { " + PAGE_FIELDS + " } }");
        assertThat(data(down)).containsEntry("assetsPage", null);
        assertThat(errors(down)).hasSize(1);
        assertThat(code(errors(down).get(0))).isEqualTo("SERVICE_UNAVAILABLE");
        assertThat(errors(down).get(0).get("message")).isEqualTo("Assets service unavailable");
        STUB.reset();
        STUB.route("/assets?offset=0&limit=20", 200, counted(0, 20, "1", 1), 2000);
        var slow = run("{ assetsPage { " + PAGE_FIELDS + " } }");
        assertThat(data(slow)).containsEntry("assetsPage", null);
        assertThat(code(errors(slow).get(0))).isEqualTo("SERVICE_UNAVAILABLE");
        STUB.reset();
        STUB.route("/assets?offset=0&limit=50", 200, counted(0, 50, "75", 50));
        STUB.route("/assets?offset=50&limit=25", 503, "{}");
        var second = run("{ assetsPage(limit: 75) { " + PAGE_FIELDS + " } }");
        assertThat(data(second)).containsEntry("assetsPage", null);
        assertThat(errors(second)).hasSize(1);
        assertThat(code(errors(second).get(0))).isEqualTo("SERVICE_UNAVAILABLE");
        STUB.reset();
        STUB.route("/assets?offset=0&limit=50", 500, "{}");
        var first = run("{ assetsPage(limit: 100) { " + PAGE_FIELDS + " } }");
        assertThat(errors(first)).hasSize(1);
        assertThat(STUB.calls()).as("no call after the first failed").containsExactly("/assets?offset=0&limit=50");
        STUB.reset();
        for (String body : List.of("not json", "[]", "{\"offset\":0,\"limit\":20,\"total\":0}")) {
            STUB.route("/assets?offset=0&limit=20", 200, body);
            var bad = run("{ assetsPage { " + PAGE_FIELDS + " } }");
            assertThat(data(bad)).as(body).containsEntry("assetsPage", null);
            assertThat(errors(bad)).as(body).hasSize(1);
            assertThat(code(errors(bad).get(0))).as(body).isEqualTo("UPSTREAM_BAD_RESPONSE");
            assertThat(errors(bad).get(0).get("message")).as(body).isEqualTo("Assets service answered something the adapter cannot use");
            STUB.reset();
        }
    }

    @Test
    void theLargestOffsetIsAnEmptyPageWithTheTotalAndTheSecondCallDoesNotOverflow() {
        STUB.route("/assets?offset=2147483647&limit=50", 200, counted(2147483647, 50, "173", 0));
        STUB.route("/assets?offset=2147483697&limit=50", 200,
                "{\"items\":[],\"offset\":2147483697,\"limit\":50,\"total\":173}");
        var result = run("{ assetsPage(offset: 2147483647, limit: 100) { " + PAGE_FIELDS + " } }");
        assertThat(errors(result)).isEmpty();
        assertThat(page(result)).containsEntry("items", List.of()).containsEntry("totalCount", 173).containsEntry("hasMore", false)
                .containsEntry("offset", 2147483647).containsEntry("limit", 100);
        assertThat(STUB.calls()).containsExactly("/assets?offset=2147483647&limit=50", "/assets?offset=2147483697&limit=50");
    }

    @Test
    void aJsonNullBodyIsAnUpstreamBadResponseNotAnAdapterFault() {
        STUB.route("/assets?offset=0&limit=20", 200, "null");
        var result = run("{ assetsPage { " + PAGE_FIELDS + " } }");
        assertThat(data(result)).containsEntry("assetsPage", null);
        assertThat(errors(result)).hasSize(1);
        assertThat(code(errors(result).get(0))).isEqualTo("UPSTREAM_BAD_RESPONSE");
        assertThat(errors(result).get(0).get("message")).isEqualTo("Assets service answered something the adapter cannot use");
        var list = run("{ assets { assetId } }");
        assertThat(code(errors(list).get(0))).as("the deprecated list, as before").isEqualTo("UPSTREAM_BAD_RESPONSE");
    }

    @Test
    void theWindowOfThePageIsCheckedAsTheListsIs() {
        for (String arguments : List.of("limit: 101", "limit: 0", "offset: -1")) {
            var result = run("{ assetsPage(" + arguments + ") { totalCount } }");
            assertThat(data(result)).as(arguments).containsEntry("assetsPage", null);
            assertThat(code(errors(result).get(0))).as(arguments).isEqualTo("BAD_USER_INPUT");
        }
        assertThat(STUB.calls()).isEmpty();
    }

    @Test
    @SuppressWarnings("unchecked")
    void aDefaultIntrospectionShowsThePageAndNotTheDeprecatedList() {
        var plain = run("{ __type(name: \"Query\") { fields { name } } }");
        List<String> names = ((List<Map<String, Object>>) ((Map<String, Object>) data(plain).get("__type")).get("fields")).stream()
                .map(field -> (String) field.get("name")).toList();
        assertThat(names).contains("asset", "assetsPage").doesNotContain("assets");
        var all = run("{ __type(name: \"Query\") { fields(includeDeprecated: true) { name isDeprecated deprecationReason } } }");
        Map<String, Object> assets = ((List<Map<String, Object>>) ((Map<String, Object>) data(all).get("__type")).get("fields")).stream()
                .filter(field -> "assets".equals(field.get("name"))).findFirst().orElseThrow();
        assertThat(assets).containsEntry("isDeprecated", true)
                .containsEntry("deprecationReason", "Use assetsPage: the same filters, offset, limit and items, with totalCount and hasMore.");
        var page = run("{ __type(name: \"AssetPage\") { fields { name } } }");
        assertThat(((List<Map<String, Object>>) ((Map<String, Object>) data(page).get("__type")).get("fields")).stream().map(field -> field.get("name")))
                .containsExactly("items", "totalCount", "offset", "limit", "hasMore");
    }

    // ---- the Federation entry points -------------------------------------------------------------------------------

    @Test
    void theServiceAnswersItsSdlWithFederation2() {
        var sdl = (String) ((Map<String, Object>) data(run("{ _service { sdl } }")).get("_service")).get("sdl");
        assertThat(sdl).contains("https://specs.apollo.dev/federation/v2.0");
        assertThat(sdl).contains("type AssetReference").contains("type Asset ").contains("enum Resolution").contains("enum MappingOutcome");
        assertThat(sdl).contains("UNMAPPED").contains("UNAVAILABLE").contains("RELEASE_REFUSED").contains("parent: Asset");
        assertThat(sdl).contains("assetsPage(").contains("type AssetPage").contains("@deprecated(reason");
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
        assertThat(used).containsExactlyInAnyOrder("link", "key", "requires", "external", "deprecated");
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
