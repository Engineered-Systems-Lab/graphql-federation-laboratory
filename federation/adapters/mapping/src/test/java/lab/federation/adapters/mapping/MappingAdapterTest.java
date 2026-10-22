package lab.federation.adapters.mapping;

import static org.assertj.core.api.Assertions.assertThat;

import graphql.ExecutionInput;
import java.io.IOException;
import java.io.InputStream;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.graphql.execution.GraphQlSource;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * The adapter against fixture releases (0.1, 0.2 and 0.3, made for the tests): the entity through _entities with the representations
 * the router sends, the release errors, the independence of releases and the sections the adapter does not serve. The real release
 * 1.0 is in RealReleaseTest.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@SuppressWarnings("unchecked")
class MappingAdapterTest {
    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) throws URISyntaxException {
        Path releases = Path.of(MappingAdapterTest.class.getResource("/releases").toURI());
        registry.add("mapping.releases-dir", releases::toString);
    }

    @Autowired
    GraphQlSource source;

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

    private static List<Map<String, Object>> entities(Map<String, Object> result) {
        return (List<Map<String, Object>>) data(result).get("_entities");
    }

    private static Map<String, Object> representation(String localRef, String release) {
        Map<String, Object> representation = new HashMap<>();
        representation.put("__typename", "AssetReference");
        representation.put("localRef", localRef);
        representation.put("release", release);
        return representation;
    }

    private static final String ENTITIES = "query($r: [_Any!]!) { _entities(representations: $r) { ... on AssetReference { localRef release assetId mappingOutcome } } }";

    private Map<String, Object> resolve(Map<String, Object>... representations) {
        return run(ENTITIES, Map.of("r", List.of(representations)));
    }

    // ---- the entity ------------------------------------------------------------------------------------------------

    @Test
    void aMappedReferenceGivesItsAssetIdAndAReferenceWithNoEntryGivesNullAndNoEntryAsItsOutcome() {
        var result = resolve(representation("EQ-64", "0.1"), representation("SH-17", "0.1"), representation("EQ-108", "0.1"));
        var list = entities(result);
        assertThat(list.get(0)).containsEntry("localRef", "EQ-64").containsEntry("release", "0.1").containsEntry("assetId", "AST-9004")
                .containsEntry("mappingOutcome", "MAPPED");
        assertThat(list.get(1)).containsEntry("assetId", "AST-9023").containsEntry("mappingOutcome", "MAPPED");
        assertThat(list.get(2)).containsEntry("localRef", "EQ-108").containsEntry("assetId", null).containsEntry("mappingOutcome", "NO_ENTRY");
        assertThat(errors(result)).as("UNMAPPED is data: a missing entry adds no errors entry").isEmpty();
    }

    @Test
    void releasesAreIndependent() {
        var list = entities(resolve(representation("EQ-64", "0.1"), representation("EQ-64", "0.2"), representation("SH-17", "0.2")));
        assertThat(list).extracting(entry -> entry.get("assetId")).containsExactly("AST-9004", "AST-8004", null);
    }

    @Test
    void aReleaseWithoutAnAssetsSectionGivesNullNotAnError() {
        var result = resolve(representation("EQ-64", "0.3"));
        assertThat(entities(result).get(0)).containsEntry("assetId", null).containsEntry("release", "0.3").containsEntry("mappingOutcome", "NO_ENTRY");
        assertThat(errors(result)).isEmpty();
    }

    @Test
    void theCrewSectionOfARelease_isListedAndNeverReturnedAsAnAsset() {
        var releases = data(run("{ mappingReleases { release sections } }")).get("mappingReleases");
        assertThat(releases).isEqualTo(List.of(
                Map.of("release", "0.1", "sections", List.of("assets", "crew")),
                Map.of("release", "0.2", "sections", List.of("assets")),
                Map.of("release", "0.3", "sections", List.of("crew"))));
        // The crew entry C-1 of release 0.1 is not an asset reference and is never returned as one.
        assertThat(entities(resolve(representation("C-1", "0.1"))).get(0)).containsEntry("assetId", null).containsEntry("mappingOutcome", "NO_ENTRY");
    }

    // ---- the crew reference ------------------------------------------------------------------------------------------

    private static Map<String, Object> crewRepresentation(String localRef, String release) {
        Map<String, Object> representation = representation(localRef, release);
        representation.put("__typename", "PersonnelReference");
        return representation;
    }

    private static final String CREW_ENTITIES = "query($r: [_Any!]!) { _entities(representations: $r) { __typename ... on PersonnelReference { localRef release personnelId mappingOutcome } } }";

    @Test
    void aCrewReferenceAnswersItsPersonnelIdFromTheCrewSectionOfTheNamedRelease() {
        // C-1 is PRS-0001 in release 0.1 and PRS-0002 in release 0.3: each release answers for itself. Release 0.2 has no crew section.
        var result = run(CREW_ENTITIES, Map.of("r", List.of(crewRepresentation("C-1", "0.1"), crewRepresentation("C-1", "0.3"), crewRepresentation("C-1", "0.2"))));
        assertThat(entities(result)).extracting(entry -> entry.get("__typename")).containsOnly("PersonnelReference");
        assertThat(entities(result)).extracting(entry -> entry.get("personnelId")).containsExactly("PRS-0001", "PRS-0002", null);
        assertThat(entities(result)).extracting(entry -> entry.get("release")).containsExactly("0.1", "0.3", "0.2");
        assertThat(entities(result)).extracting(entry -> entry.get("mappingOutcome")).containsExactly("MAPPED", "MAPPED", "NO_ENTRY");
        assertThat(errors(result)).as("a release without the section is data, not an error").isEmpty();
    }

    @Test
    void aCrewReferenceWithNoEntryInTheReleaseHasANullPersonnelId() {
        var result = run(CREW_ENTITIES, Map.of("r", List.of(crewRepresentation("C-999", "0.1"), crewRepresentation("EQ-64", "0.1"))));
        assertThat(entities(result)).extracting(entry -> entry.get("personnelId")).containsOnlyNulls();
        assertThat(entities(result)).extracting(entry -> entry.get("mappingOutcome")).containsOnly("NO_ENTRY");
        assertThat(errors(result)).as("NO_ENTRY is data: no errors entry").isEmpty();
    }

    @Test
    void aCrewReferenceKeepsTheSameReleaseRulesAsAnAssetReference() {
        var blank = run(CREW_ENTITIES, Map.of("r", List.of(crewRepresentation("C-1", " "))));
        assertThat(entities(blank).get(0)).containsEntry("personnelId", null).containsEntry("mappingOutcome", "RELEASE_REFUSED");
        assertThat(errors(blank)).extracting(MappingAdapterTest::code).containsExactly("MAPPING_RELEASE_REQUIRED");
        var unknown = run(CREW_ENTITIES, Map.of("r", List.of(crewRepresentation("C-1", "latest"))));
        assertThat(entities(unknown).get(0)).containsEntry("personnelId", null).containsEntry("mappingOutcome", "RELEASE_REFUSED");
        assertThat(errors(unknown)).extracting(MappingAdapterTest::code).containsExactly("MAPPING_RELEASE_NOT_FOUND");
    }

    @Test
    void assetAndCrewReferencesInOneCallEachGetTheirOwnType() {
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { __typename ... on AssetReference { assetId mappingOutcome } ... on PersonnelReference { personnelId mappingOutcome } } }",
                Map.of("r", List.of(representation("EQ-64", "0.1"), crewRepresentation("C-1", "0.1"))));
        var list = entities(result);
        assertThat(list.get(0)).containsEntry("__typename", "AssetReference").containsEntry("assetId", "AST-9004").containsEntry("mappingOutcome", "MAPPED");
        assertThat(list.get(1)).containsEntry("__typename", "PersonnelReference").containsEntry("personnelId", "PRS-0001").containsEntry("mappingOutcome", "MAPPED");
    }

    // ---- the release is required and never guessed ------------------------------------------------------------------

    @Test
    void aBlankReleaseIsRefusedWithMappingReleaseRequiredAndOneEntry() {
        for (String blank : new String[] {"", " ", "\t"}) {
            var result = resolve(representation("EQ-64", blank), representation("SH-17", blank));
            assertThat(entities(result)).as("a refused release is still an entity, with its outcome stated and no identifier")
                    .extracting(entry -> entry.get("mappingOutcome")).containsExactly("RELEASE_REFUSED", "RELEASE_REFUSED");
            assertThat(entities(result)).extracting(entry -> entry.get("assetId")).containsOnlyNulls();
            assertThat(entities(result)).extracting(entry -> entry.get("release")).containsExactly(blank, blank);
            assertThat(errors(result)).as("one entry, however many representations share the cause").hasSize(1);
            assertThat(code(errors(result).get(0))).isEqualTo("MAPPING_RELEASE_REQUIRED");
        }
    }

    @Test
    void aRepresentationWithNoReleaseOrANullReleaseIsRefusedTheSameWay() {
        Map<String, Object> missing = representation("EQ-64", "0.1");
        missing.remove("release");
        for (Map<String, Object> bad : List.of(missing, representation("EQ-64", null))) {
            var result = resolve(bad);
            assertThat(entities(result)).extracting(entry -> entry.get("mappingOutcome")).containsExactly("RELEASE_REFUSED");
            assertThat(entities(result).get(0)).containsEntry("assetId", null).containsEntry("release", "");
            assertThat(errors(result)).hasSize(1);
            assertThat(code(errors(result).get(0))).isEqualTo("MAPPING_RELEASE_REQUIRED");
        }
    }

    @Test
    void anUnknownReleaseIsRefusedWithMappingReleaseNotFoundAndThereIsNoImplicitLatest() {
        for (String unknown : new String[] {"7.7", "latest", "1", "0.1.0", " 0.1", "0.10"}) {
            var result = resolve(representation("EQ-64", unknown), representation("SH-17", unknown));
            assertThat(entities(result)).as(unknown).extracting(entry -> entry.get("mappingOutcome")).containsExactly("RELEASE_REFUSED", "RELEASE_REFUSED");
            assertThat(entities(result)).extracting(entry -> entry.get("release")).containsExactly(unknown, unknown);
            assertThat(entities(result)).extracting(entry -> entry.get("assetId")).containsOnlyNulls();
            assertThat(errors(result)).as(unknown).hasSize(1);
            assertThat(code(errors(result).get(0))).as(unknown).isEqualTo("MAPPING_RELEASE_NOT_FOUND");
            assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("_entities"));
        }
    }

    @Test
    void goodAndBadRepresentationsInOneCallAnswerIndependentlyWithOneEntryPerCause() {
        var result = resolve(representation("EQ-64", "0.1"), representation("EQ-64", "9.9"), representation("SH-17", "9.9"),
                representation("EQ-64", ""), representation("EQ-64", "8.8"));
        var list = entities(result);
        assertThat(list.get(0)).containsEntry("assetId", "AST-9004").containsEntry("mappingOutcome", "MAPPED");
        assertThat(list.subList(1, 5)).extracting(entry -> entry.get("mappingOutcome")).containsOnly("RELEASE_REFUSED");
        assertThat(list.subList(1, 5)).extracting(entry -> entry.get("assetId")).containsOnlyNulls();
        assertThat(errors(result)).extracting(entry -> code(entry))
                .containsExactlyInAnyOrder("MAPPING_RELEASE_NOT_FOUND", "MAPPING_RELEASE_REQUIRED", "MAPPING_RELEASE_NOT_FOUND");
    }

    @Test
    void aRepresentationWithNoLocalRefIsAnAdapterFault() {
        Map<String, Object> bad = representation("EQ-64", "0.1");
        bad.remove("localRef");
        var result = resolve(bad);
        assertThat(errors(result)).hasSize(1);
        assertThat(code(errors(result).get(0))).isEqualTo("INTERNAL_SERVER_ERROR");
    }

    // ---- the plain lookups --------------------------------------------------------------------------------------------

    private static final String ASSET_LOOKUP = "query($release: String!, $refs: [ID!]!) { assetReferences(release: $release, localRefs: $refs) { localRef release assetId mappingOutcome } }";
    private static final String PERSONNEL_LOOKUP = "query($release: String!, $refs: [ID!]!) { personnelReferences(release: $release, localRefs: $refs) { localRef release personnelId mappingOutcome } }";

    private Map<String, Object> lookup(String query, String release, List<String> references) {
        return run(query, Map.of("release", release, "refs", references));
    }

    private static List<Map<String, Object>> answers(Map<String, Object> result, String field) {
        return (List<Map<String, Object>>) data(result).get(field);
    }

    @Test
    void theAssetLookupGivesTheEntitysAnswerForAMappedAndAnUnmappedReferenceInTheOrderGiven() {
        var result = lookup(ASSET_LOOKUP, "0.1", List.of("EQ-108", "EQ-64", "SH-17", "EQ-64"));
        var list = answers(result, "assetReferences");
        assertThat(list).extracting(entry -> entry.get("localRef")).containsExactly("EQ-108", "EQ-64", "SH-17", "EQ-64");
        assertThat(list).extracting(entry -> entry.get("assetId")).containsExactly(null, "AST-9004", "AST-9023", "AST-9004");
        assertThat(list).extracting(entry -> entry.get("mappingOutcome")).containsExactly("NO_ENTRY", "MAPPED", "MAPPED", "MAPPED");
        assertThat(list).extracting(entry -> entry.get("release")).containsOnly("0.1");
        assertThat(errors(result)).as("UNMAPPED is data: a missing entry adds no errors entry").isEmpty();
        // The same references through _entities give the same answers, field for field.
        var entities = entities(resolve(representation("EQ-108", "0.1"), representation("EQ-64", "0.1"), representation("SH-17", "0.1"),
                representation("EQ-64", "0.1")));
        assertThat(list).isEqualTo(entities);
    }

    @Test
    void thePersonnelLookupGivesTheEntitysAnswerForACrewReference() {
        var mapped = lookup(PERSONNEL_LOOKUP, "0.1", List.of("C-1", "C-999"));
        assertThat(answers(mapped, "personnelReferences")).extracting(entry -> entry.get("personnelId")).containsExactly("PRS-0001", null);
        assertThat(answers(mapped, "personnelReferences")).extracting(entry -> entry.get("mappingOutcome")).containsExactly("MAPPED", "NO_ENTRY");
        assertThat(errors(mapped)).isEmpty();
        // Each release answers for itself, and a release without a crew section is NO_ENTRY with no errors entry.
        assertThat(answers(lookup(PERSONNEL_LOOKUP, "0.3", List.of("C-1")), "personnelReferences").get(0)).containsEntry("personnelId", "PRS-0002");
        var none = lookup(PERSONNEL_LOOKUP, "0.2", List.of("C-1"));
        assertThat(answers(none, "personnelReferences").get(0)).containsEntry("personnelId", null).containsEntry("mappingOutcome", "NO_ENTRY");
        assertThat(errors(none)).isEmpty();
        var entities = entities(run(CREW_ENTITIES, Map.of("r", List.of(crewRepresentation("C-1", "0.1"), crewRepresentation("C-999", "0.1")))));
        assertThat(answers(mapped, "personnelReferences")).isEqualTo(entities.stream().map(entry -> {
            Map<String, Object> copy = new java.util.LinkedHashMap<>(entry);
            copy.remove("__typename");
            return copy;
        }).toList());
    }

    @Test
    void anOutsiderReferenceIsRefusedByClassAndAParticipantIsNotResolvedEachWithOneEntry() {
        var result = lookup(PERSONNEL_LOOKUP, "0.1", List.of("O-860", "C-1", "P-1068", "O-2836", "P-1003"));
        var list = answers(result, "personnelReferences");
        assertThat(list).extracting(entry -> entry.get("personnelId")).containsExactly(null, "PRS-0001", null, null, null);
        assertThat(list).extracting(entry -> entry.get("mappingOutcome")).containsExactly("NO_ENTRY", "MAPPED", "NO_ENTRY", "NO_ENTRY", "NO_ENTRY");
        assertThat(list).extracting(entry -> entry.get("release")).containsOnly("0.1");
        assertThat(errors(result)).as("one entry per class, however many references share it").extracting(MappingAdapterTest::code)
                .containsExactly("MAPPING_CLASS_REFUSED", "MAPPING_CLASS_REFUSED");
        assertThat(errors(result)).extracting(entry -> (String) entry.get("message"))
                .anySatisfy(message -> assertThat(message).contains("outsider").contains("refused by class"))
                .anySatisfy(message -> assertThat(message).contains("participant").contains("not resolved"));
        assertThat(errors(result).get(0).get("path")).isEqualTo(List.of("personnelReferences"));
    }

    @Test
    void theClassRuleIsTheLookupsOnlyTheEntitiesAndTheAssetLookupAreUnchanged() {
        var entities = run(CREW_ENTITIES, Map.of("r", List.of(crewRepresentation("O-860", "0.1"), crewRepresentation("P-1068", "0.1"))));
        assertThat(entities(entities)).extracting(entry -> entry.get("mappingOutcome")).containsOnly("NO_ENTRY");
        assertThat(errors(entities)).isEmpty();
        var assets = lookup(ASSET_LOOKUP, "0.1", List.of("O-860", "P-1068"));
        assertThat(answers(assets, "assetReferences")).extracting(entry -> entry.get("mappingOutcome")).containsOnly("NO_ENTRY");
        assertThat(errors(assets)).isEmpty();
    }

    @Test
    void theLookupsKeepTheReleaseRulesAndTheReleaseRuleComesBeforeTheClassRule() {
        for (String field : List.of("assetReferences", "personnelReferences")) {
            String query = field.equals("assetReferences") ? ASSET_LOOKUP : PERSONNEL_LOOKUP;
            var blank = lookup(query, " ", List.of("EQ-64", "O-860"));
            assertThat(answers(blank, field)).extracting(entry -> entry.get("mappingOutcome")).containsExactly("RELEASE_REFUSED", "RELEASE_REFUSED");
            assertThat(answers(blank, field)).extracting(entry -> entry.get("release")).containsOnly(" ");
            assertThat(errors(blank)).extracting(MappingAdapterTest::code).containsExactly("MAPPING_RELEASE_REQUIRED");
            for (String unknown : new String[] {"latest", "2.0", "1", "0.1.0", " 0.1"}) {
                var result = lookup(query, unknown, List.of("EQ-64", "C-1"));
                assertThat(answers(result, field)).as(unknown).extracting(entry -> entry.get("mappingOutcome")).containsOnly("RELEASE_REFUSED");
                assertThat(errors(result)).as(unknown).extracting(MappingAdapterTest::code).containsExactly("MAPPING_RELEASE_NOT_FOUND");
            }
        }
    }

    @Test
    void theReleaseIsAlwaysAnArgument() {
        var result = run("{ assetReferences(localRefs: [\"EQ-64\"]) { assetId } }");
        assertThat(errors(result)).as("a missing release is a validation error, never an implicit latest").isNotEmpty();
        assertThat(result.get("data")).isNull();
    }

    @Test
    void aLookupAnswersAtMostOneHundredReferences() {
        List<String> hundred = new java.util.ArrayList<>();
        for (int i = 0; i < 100; i++) {
            hundred.add("EQ-" + i);
        }
        var full = lookup(ASSET_LOOKUP, "0.1", hundred);
        assertThat(answers(full, "assetReferences")).hasSize(100);
        assertThat(errors(full)).isEmpty();
        hundred.add("EQ-64");
        var over = lookup(ASSET_LOOKUP, "0.1", hundred);
        assertThat(data(over).get("assetReferences")).isNull();
        assertThat(errors(over)).extracting(MappingAdapterTest::code).containsExactly("BAD_USER_INPUT");
        var empty = lookup(PERSONNEL_LOOKUP, "0.1", List.of());
        assertThat(answers(empty, "personnelReferences")).isEmpty();
        assertThat(errors(empty)).isEmpty();
    }

    // ---- the diagnostic list and the Federation entry points --------------------------------------------------------

    @Test
    void theDiagnosticListShowsEachReleaseWithItsCheckedAgainstList() {
        var result = run("{ mappingReleases { release sections checkedAgainst { system artifact version sha256 } } }");
        assertThat(errors(result)).isEmpty();
        var releases = (List<Map<String, Object>>) data(result).get("mappingReleases");
        assertThat(releases).extracting(entry -> entry.get("release")).containsExactly("0.1", "0.2", "0.3");
        assertThat(((List<Map<String, Object>>) releases.get(0).get("checkedAgainst")).get(0)).containsEntry("system", "fixture");
    }

    @Test
    void theServiceAnswersItsSdlWithFederation2AndTheCompositeKey() {
        var sdl = (String) ((Map<String, Object>) data(run("{ _service { sdl } }")).get("_service")).get("sdl");
        assertThat(sdl).contains("https://specs.apollo.dev/federation/v2.0");
        assertThat(sdl).contains("type AssetReference").contains("assetId").contains("mappingOutcome: MappingOutcome!");
        assertThat(sdl).contains("type PersonnelReference").contains("enum MappingOutcome").contains("MAPPED").contains("NO_ENTRY").contains("RELEASE_REFUSED");
        assertThat(sdl).containsPattern("@key\\(fields\\s*:\\s*\"localRef release\"");
        // The printer sorts the arguments, so only the field, its type and the directive are compared here.
        assertThat(sdl).containsPattern("assetReferences\\([^)]*\\): \\[AssetReference!\\] @inaccessible")
                .containsPattern("personnelReferences\\([^)]*\\): \\[PersonnelReference!\\] @inaccessible");
    }

    @Test
    void theSchemaUsesOnlyKey() throws IOException {
        String schema;
        try (InputStream stream = getClass().getResourceAsStream("/graphql/schema.graphqls")) {
            schema = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
        String code = schema.lines().filter(line -> !line.stripLeading().startsWith("#")).collect(Collectors.joining("\n"));
        Matcher matcher = Pattern.compile("@(\\w+)").matcher(code);
        TreeSet<String> used = new TreeSet<>();
        while (matcher.find()) {
            used.add(matcher.group(1));
        }
        assertThat(used).containsExactly("inaccessible", "key", "link");
        assertThat(code).contains("@key(fields: \"localRef release\")").contains("assetId: ID\n").contains("mappingOutcome: MappingOutcome!");
        assertThat(code).as("the redundant id field is gone").doesNotContain("  id: ID");
        // @inaccessible is on the two plain lookups and nowhere else, so the supergraph a router serves does not change.
        assertThat(code.lines().filter(line -> line.contains("@inaccessible") && !line.startsWith("extend schema")).map(String::strip).toList())
                .containsExactly("assetReferences(release: String!, localRefs: [ID!]!): [AssetReference!] @inaccessible",
                        "personnelReferences(release: String!, localRefs: [ID!]!): [PersonnelReference!] @inaccessible");
    }
}
