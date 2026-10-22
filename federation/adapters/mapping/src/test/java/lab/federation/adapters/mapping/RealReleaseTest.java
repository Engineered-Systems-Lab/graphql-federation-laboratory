package lab.federation.adapters.mapping;

import static org.assertj.core.api.Assertions.assertThat;

import graphql.ExecutionInput;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import lab.federation.common.Json;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.graphql.execution.GraphQlSource;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * The real releases 1.0 (assets only), 1.1 (assets and crew) and 1.2 (assets, crew and participants) of federation/mapping-releases, served exactly as the image serves
 * them. The asset entries are the expected mapping of the Assets dataset release 1.1; the crew entries are built by the process of
 * federation/personnel-mapping. The Python gate re-derives both and checks the checked-against lists against the current system
 * files, which live outside this module's build context.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@SuppressWarnings("unchecked")
class RealReleaseTest {
    /** Under Maven the working folder is the module folder, two levels below federation/. */
    private static final Path RELEASES = Path.of("../../mapping-releases").toAbsolutePath().normalize();

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("mapping.releases-dir", RELEASES::toString);
    }

    @Autowired
    GraphQlSource source;

    private Map<String, Object> run(String query, Map<String, Object> variables) {
        return source.graphQl().execute(ExecutionInput.newExecutionInput(query).variables(variables).build()).toSpecification();
    }

    private static Map<String, Object> representation(String localRef, String release) {
        Map<String, Object> representation = new HashMap<>();
        representation.put("__typename", "AssetReference");
        representation.put("localRef", localRef);
        representation.put("release", release);
        return representation;
    }

    private List<Map<String, Object>> assetIds(String release, String... references) {
        List<Map<String, Object>> representations = new java.util.ArrayList<>();
        for (String reference : references) {
            representations.add(representation(reference, release));
        }
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on AssetReference { localRef release assetId mappingOutcome } } }",
                Map.of("r", representations));
        assertThat(result.get("errors")).isNull();
        return (List<Map<String, Object>>) ((Map<String, Object>) result.get("data")).get("_entities");
    }

    @Test
    void theNineMissionsReferencesOfTheExpectedMappingAnswerAsTheDatasetSays() {
        Map<String, String> expected = new LinkedHashMap<>();
        expected.put("EQ-64", "AST-0004");
        expected.put("EQ-75", "AST-0005");
        expected.put("EQ-86", "AST-0006");
        expected.put("EQ-97", "AST-0097");
        expected.put("EQ-108", null);
        expected.put("EQ-119", "AST-0007");
        expected.put("SH-42", "AST-0024");
        expected.put("SH-53", "AST-0025");
        expected.put("VS-31", "AST-0029");
        var answered = assetIds("1.0", expected.keySet().toArray(new String[0]));
        for (int i = 0; i < answered.size(); i++) {
            String reference = (String) answered.get(i).get("localRef");
            assertThat(answered.get(i)).as(reference).containsEntry("release", "1.0").containsEntry("assetId", expected.get(reference))
                    .containsEntry("mappingOutcome", expected.get(reference) == null ? "NO_ENTRY" : "MAPPED");
        }
    }

    @Test
    void aReferenceThatIsNotInTheReleaseHasNoAstId() {
        assertThat(assetIds("1.0", "ZZ-1", "AST-0004", "C-85").stream().map(entity -> entity.get("assetId"))).containsOnlyNulls();
    }

    @Test
    void thereIsNoImplicitLatest() {
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on AssetReference { assetId } } }",
                Map.of("r", List.of(representation("EQ-64", "2.0"), representation("EQ-64", "latest"), representation("EQ-64", ""))));
        var errors = (List<Map<String, Object>>) result.get("errors");
        assertThat(errors).extracting(error -> ((Map<String, Object>) error.get("extensions")).get("code"))
                .containsExactlyInAnyOrder("MAPPING_RELEASE_NOT_FOUND", "MAPPING_RELEASE_NOT_FOUND", "MAPPING_RELEASE_REQUIRED");
    }

    @Test
    void theManifestHoldsTheHashOfEveryFileAndTheFilesMatchIt() throws IOException {
        Map<String, Object> manifest = Json.object(Files.readString(RELEASES.resolve("1.0/manifest.json"), StandardCharsets.UTF_8));
        assertThat(manifest).containsEntry("release", "1.0");
        Map<String, Object> files = (Map<String, Object>) manifest.get("files");
        assertThat(files.keySet()).containsExactly("assets.json");
        for (Map.Entry<String, Object> file : files.entrySet()) {
            String content = Files.readString(RELEASES.resolve("1.0").resolve(file.getKey()), StandardCharsets.UTF_8).replace("\r\n", "\n");
            assertThat(MappingReleases.sha256(content)).as(file.getKey()).isEqualTo(file.getValue());
        }
        try (var folder = Files.list(RELEASES.resolve("1.0"))) {
            assertThat(folder.map(path -> path.getFileName().toString())).containsExactlyInAnyOrder("assets.json", "manifest.json");
        }
    }

    @Test
    void theCheckedAgainstListNamesTheMissionsReleaseTheAssetsContractAndTheAssetsDatasetRelease() {
        var release = new MappingReleases(RELEASES).find("1.0");
        assertThat(release.checkedAgainst()).extracting(entry -> entry.get("system") + " " + entry.get("artifact") + " " + entry.get("version"))
                .containsExactly("missions dataset release manifest 1.0", "assets contract file 1.1", "assets dataset release manifest 1.1");
        assertThat(release.checkedAgainst()).allSatisfy(entry -> assertThat((String) entry.get("sha256")).matches("[0-9a-f]{64}"));
    }

    private List<Map<String, Object>> personnelIds(String release, String... references) {
        List<Map<String, Object>> representations = new java.util.ArrayList<>();
        for (String reference : references) {
            Map<String, Object> representation = representation(reference, release);
            representation.put("__typename", "PersonnelReference");
            representations.add(representation);
        }
        var result = run("query($r: [_Any!]!) { _entities(representations: $r) { ... on PersonnelReference { localRef release personnelId mappingOutcome } } }",
                Map.of("r", representations));
        assertThat(result.get("errors")).isNull();
        return (List<Map<String, Object>>) ((Map<String, Object>) result.get("data")).get("_entities");
    }

    /** The expected crew mapping of the ten Missions crew references, written by hand from the released datasets. */
    private static Map<String, String> expectedCrew() {
        Map<String, String> expected = new LinkedHashMap<>();
        expected.put("C-71", "PRS-0001");
        expected.put("C-78", "PRS-1048");
        expected.put("C-85", "PRS-0002");
        expected.put("C-92", "PRS-1049");
        expected.put("C-99", "PRS-1058");
        expected.put("C-106", "PRS-1053");
        expected.put("C-113", "PRS-1054");
        expected.put("C-120", "PRS-0714");
        expected.put("C-127", "PRS-1057");
        expected.put("C-134", "PRS-1100");
        return expected;
    }

    @Test
    void release11AnswersTheTenCrewReferencesAsTheCrewMappingSays() {
        var expected = expectedCrew();
        var answered = personnelIds("1.1", expected.keySet().toArray(new String[0]));
        assertThat(answered).hasSize(expected.size());
        for (var entity : answered) {
            String reference = (String) entity.get("localRef");
            assertThat(entity).as(reference).containsEntry("release", "1.1").containsEntry("personnelId", expected.get(reference)).containsEntry("mappingOutcome", "MAPPED");
        }
    }

    @Test
    void release11KeepsTheAssetsOfRelease10UnchangedAndRelease10StillHasNoCrew() {
        var releases = new MappingReleases(RELEASES);
        assertThat(releases.find("1.1").sections().get("assets")).isEqualTo(releases.find("1.0").sections().get("assets"));
        assertThat(releases.find("1.1").files().get("assets.json")).isEqualTo(releases.find("1.0").files().get("assets.json"));
        assertThat(personnelIds("1.0", "C-71", "C-85", "C-120").stream().map(entity -> entity.get("personnelId"))).containsOnlyNulls();
        assertThat(personnelIds("1.0", "C-71").get(0)).as("a release without a crew section is NO_ENTRY").containsEntry("mappingOutcome", "NO_ENTRY");
        assertThat(assetIds("1.1", "EQ-64", "EQ-108").stream().map(entity -> entity.get("assetId"))).containsExactly("AST-0004", null);
    }

    @Test
    void aCrewReferenceWithNoEntryInRelease11IsUnmappedAndAnAssetReferenceIsNotACrewEntry() {
        assertThat(personnelIds("1.1", "C-999", "EQ-64", "AST-0004").stream().map(entity -> entity.get("personnelId"))).containsOnlyNulls();
        assertThat(assetIds("1.1", "C-85", "C-71").stream().map(entity -> entity.get("assetId"))).containsOnlyNulls();
    }

    @Test
    void release11ManifestHoldsTheHashOfBothFilesAndTheCheckedAgainstListAddsThePersonnelSnapshot() throws IOException {
        Map<String, Object> manifest = Json.object(Files.readString(RELEASES.resolve("1.1/manifest.json"), StandardCharsets.UTF_8));
        assertThat(manifest).containsEntry("release", "1.1");
        Map<String, Object> files = (Map<String, Object>) manifest.get("files");
        assertThat(files.keySet()).containsExactly("assets.json", "crew.json");
        for (Map.Entry<String, Object> file : files.entrySet()) {
            String content = Files.readString(RELEASES.resolve("1.1").resolve(file.getKey()), StandardCharsets.UTF_8).replace("\r\n", "\n");
            assertThat(MappingReleases.sha256(content)).as(file.getKey()).isEqualTo(file.getValue());
        }
        var release = new MappingReleases(RELEASES).find("1.1");
        assertThat(release.sections().keySet()).containsExactly("assets", "crew");
        assertThat(release.sections().get("crew")).isEqualTo(expectedCrew());
        assertThat(release.checkedAgainst()).extracting(entry -> entry.get("system") + " " + entry.get("artifact") + " " + entry.get("version"))
                .containsExactly("missions dataset release manifest 1.0", "assets contract file 1.1", "assets dataset release manifest 1.1",
                        "personnel dataset snapshot personnel-v2-small-003");
        assertThat(release.checkedAgainst()).allSatisfy(entry -> assertThat((String) entry.get("sha256")).matches("[0-9a-f]{64}"));
    }

    @Test
    void release12HoldsTheCrewOfMissionsRelease11AndTheParticipantsSectionAndAnswersTheCrewReferences() throws IOException {
        Map<String, Object> manifest = Json.object(Files.readString(RELEASES.resolve("1.2/manifest.json"), StandardCharsets.UTF_8));
        assertThat(manifest).containsEntry("release", "1.2");
        Map<String, Object> files = (Map<String, Object>) manifest.get("files");
        assertThat(files.keySet()).containsExactly("assets.json", "crew.json", "participants.json");
        for (Map.Entry<String, Object> file : files.entrySet()) {
            String content = Files.readString(RELEASES.resolve("1.2").resolve(file.getKey()), StandardCharsets.UTF_8).replace("\r\n", "\n");
            assertThat(MappingReleases.sha256(content)).as(file.getKey()).isEqualTo(file.getValue());
        }
        var releases = new MappingReleases(RELEASES);
        var release = releases.find("1.2");
        assertThat(release.sections().keySet()).containsExactly("assets", "crew", "participants");
        assertThat(release.sections().get("assets")).isEqualTo(releases.find("1.1").sections().get("assets"));
        assertThat(release.sections().get("crew")).hasSize(800).containsAllEntriesOf(expectedCrew());
        assertThat(release.sections().get("participants")).containsOnly(Map.entry("P-1003", "PRS-3001"), Map.entry("P-1068", "PRS-0003"));
        assertThat(release.checkedAgainst()).extracting(entry -> entry.get("system") + " " + entry.get("artifact") + " " + entry.get("version"))
                .containsExactly("missions dataset release manifest 1.0", "assets contract file 1.1", "assets dataset release manifest 1.1",
                        "personnel dataset snapshot personnel-v2-small-003", "missions dataset release manifest 1.1",
                        "personnel dataset snapshot personnel-v2-large-004");
        var answered = personnelIds("1.2", "C-71", "C-120", "C-9329", "C-2372", "O-860", "P-1068");
        assertThat(answered.stream().map(entity -> entity.get("personnelId")).toList())
                .containsExactly("PRS-0001", "PRS-0714", "PRS-2707", null, null, null);
        assertThat(answered.stream().map(entity -> entity.get("mappingOutcome")).toList())
                .containsExactly("MAPPED", "MAPPED", "MAPPED", "NO_ENTRY", "NO_ENTRY", "NO_ENTRY");
        assertThat(personnelIds("1.1", "C-9329").get(0)).as("release 1.1 never grew").containsEntry("mappingOutcome", "NO_ENTRY");
    }

    @Test
    void theAssetsSectionHasTheEightEntriesAndNoEntryForTheUnmappedReference() {
        var assets = new MappingReleases(RELEASES).find("1.0").sections().get("assets");
        assertThat(assets).hasSize(8).doesNotContainKey("EQ-108");
        assertThat(new MappingReleases(RELEASES).find("1.0").sections().keySet()).containsExactly("assets");
    }

    @Test
    void thePlainLookupsAnswerFromRelease13AMappedAnUnmappedAndARefusedReference() {
        var assets = run("{ assetReferences(release: \"1.3\", localRefs: [\"EQ-64\", \"EQ-108\"]) { localRef release assetId mappingOutcome } }", Map.of());
        assertThat(assets.get("errors")).isNull();
        var assetList = (List<Map<String, Object>>) ((Map<String, Object>) assets.get("data")).get("assetReferences");
        assertThat(assetList).extracting(entry -> entry.get("assetId")).containsExactly("AST-0004", null);
        assertThat(assetList).extracting(entry -> entry.get("mappingOutcome")).containsExactly("MAPPED", "NO_ENTRY");
        // The participants section of 1.3 holds P-1068 and no O-reference has an entry anywhere; the lookup still refuses both classes.
        var crew = run("{ personnelReferences(release: \"1.3\", localRefs: [\"C-71\", \"C-120\", \"C-2372\", \"O-860\", \"P-1068\"]) { localRef personnelId mappingOutcome } }", Map.of());
        var crewList = (List<Map<String, Object>>) ((Map<String, Object>) crew.get("data")).get("personnelReferences");
        assertThat(crewList).extracting(entry -> entry.get("personnelId")).containsExactly("PRS-0001", "PRS-0714", null, null, null);
        assertThat(crewList).extracting(entry -> entry.get("mappingOutcome")).containsExactly("MAPPED", "MAPPED", "NO_ENTRY", "NO_ENTRY", "NO_ENTRY");
        assertThat((List<Map<String, Object>>) crew.get("errors")).extracting(entry -> ((Map<String, Object>) entry.get("extensions")).get("code"))
                .containsExactly("MAPPING_CLASS_REFUSED", "MAPPING_CLASS_REFUSED");
    }
}
