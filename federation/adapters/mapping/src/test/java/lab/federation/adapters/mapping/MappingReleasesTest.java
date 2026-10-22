package lab.federation.adapters.mapping;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** The loader: a published release never changes, so any difference between the files and the manifest stops the start. */
class MappingReleasesTest {
    @TempDir
    Path temp;

    private static Path fixtures() throws URISyntaxException {
        return Path.of(MappingReleasesTest.class.getResource("/releases").toURI());
    }

    /** A copy of the fixture releases that a test may damage. */
    private Path copy() throws IOException, URISyntaxException {
        Path source = fixtures();
        try (Stream<Path> walk = Files.walk(source)) {
            for (Path path : walk.toList()) {
                Path target = temp.resolve(source.relativize(path).toString());
                if (Files.isDirectory(path)) {
                    Files.createDirectories(target);
                } else {
                    Files.copy(path, target);
                }
            }
        }
        return temp;
    }

    private static void write(Path file, String content) {
        try {
            Files.writeString(file, content, StandardCharsets.UTF_8);
        } catch (IOException error) {
            throw new UncheckedIOException(error);
        }
    }

    @Test
    void theFixtureReleasesLoadOldestFirstAndAreIndependent() throws Exception {
        MappingReleases releases = new MappingReleases(fixtures());
        assertThat(releases.all()).extracting(MappingReleases.Release::release).containsExactly("0.1", "0.2", "0.3");
        assertThat(releases.find("0.1").assetId("EQ-64")).isEqualTo("AST-9004");
        assertThat(releases.find("0.2").assetId("EQ-64")).isEqualTo("AST-8004");
        assertThat(releases.find("0.3").assetId("EQ-64")).as("no assets section: null, not an error").isNull();
        assertThat(releases.find("latest")).isNull();
        assertThat(releases.find("0")).isNull();
    }

    @Test
    void releasesAreOrderedByNumberNotByText() throws Exception {
        Path folder = copy();
        for (String name : List.of("0.10", "1.0", "0.9")) {
            Files.createDirectories(folder.resolve(name));
            Files.copy(folder.resolve("0.2/assets.json"), folder.resolve(name).resolve("assets.json"));
            write(folder.resolve(name).resolve("manifest.json"), Files.readString(folder.resolve("0.2/manifest.json")).replace("\"0.2\"", "\"" + name + "\""));
        }
        assertThat(new MappingReleases(folder).all()).extracting(MappingReleases.Release::release)
                .containsExactly("0.1", "0.2", "0.3", "0.9", "0.10", "1.0");
    }

    @Test
    void loadedDataCannotBeChanged() throws Exception {
        MappingReleases.Release release = new MappingReleases(fixtures()).find("0.1");
        assertThatThrownBy(() -> release.sections().get("assets").put("EQ-1", "AST-0001")).isInstanceOf(UnsupportedOperationException.class);
        assertThatThrownBy(() -> release.sections().put("x", java.util.Map.of())).isInstanceOf(UnsupportedOperationException.class);
        assertThatThrownBy(() -> release.checkedAgainst().add(java.util.Map.of())).isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void aChangedFileStopsTheLoad() throws Exception {
        Path folder = copy();
        write(folder.resolve("0.1/assets.json"), Files.readString(folder.resolve("0.1/assets.json")).replace("AST-9004", "AST-9005"));
        assertThatThrownBy(() -> new MappingReleases(folder)).isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Release 0.1").hasMessageContaining("assets.json").hasMessageContaining("hash");
    }

    @Test
    void aChangedUnservedSectionAlsoStopsTheLoad() throws Exception {
        Path folder = copy();
        write(folder.resolve("0.1/crew.json"), Files.readString(folder.resolve("0.1/crew.json")).replace("PRS-0001", "PRS-0009"));
        assertThatThrownBy(() -> new MappingReleases(folder)).isInstanceOf(IllegalStateException.class).hasMessageContaining("crew.json");
    }

    @Test
    void aFileWithLfOrCrlfLineEndsHasTheSameHash() throws Exception {
        Path folder = copy();
        write(folder.resolve("0.2/assets.json"), Files.readString(folder.resolve("0.2/assets.json")).replace("\n", "\r\n"));
        assertThat(new MappingReleases(folder).find("0.2").assetId("EQ-64")).isEqualTo("AST-8004");
    }

    @Test
    void anUnlistedFileOrAMissingFileStopsTheLoad() throws Exception {
        Path folder = copy();
        write(folder.resolve("0.2/extra.json"), "{\"entries\":{}}\n");
        assertThatThrownBy(() -> new MappingReleases(folder)).isInstanceOf(IllegalStateException.class).hasMessageContaining("differ");
        Files.delete(folder.resolve("0.2/extra.json"));
        Files.delete(folder.resolve("0.1/crew.json"));
        assertThatThrownBy(() -> new MappingReleases(folder)).isInstanceOf(IllegalStateException.class).hasMessageContaining("differ");
    }

    @Test
    void aManifestThatNamesAnotherReleaseOrHasNoCheckedAgainstListStopsTheLoad() throws Exception {
        Path folder = copy();
        Path manifest = folder.resolve("0.2/manifest.json");
        String original = Files.readString(manifest);
        write(manifest, original.replace("\"release\": \"0.2\"", "\"release\": \"0.9\""));
        assertThatThrownBy(() -> new MappingReleases(folder)).isInstanceOf(IllegalStateException.class).hasMessageContaining("names release");
        write(manifest, original.replaceAll("(?s)\"checkedAgainst\":.*\\]", "\"checkedAgainst\": []"));
        assertThatThrownBy(() -> new MappingReleases(folder)).isInstanceOf(IllegalStateException.class).hasMessageContaining("checkedAgainst");
    }

    @Test
    void aFolderNotNamedMajorMinorOrALooseFileStopsTheLoad() throws Exception {
        Path folder = copy();
        Files.createDirectories(folder.resolve("latest"));
        assertThatThrownBy(() -> new MappingReleases(folder)).isInstanceOf(IllegalStateException.class).hasMessageContaining("MAJOR.MINOR");
        Files.delete(folder.resolve("latest"));
        write(folder.resolve("notes.txt"), "x");
        assertThatThrownBy(() -> new MappingReleases(folder)).isInstanceOf(IllegalStateException.class).hasMessageContaining("Unexpected file");
    }

    @Test
    void aMissingOrEmptyFolderStopsTheLoad() throws Exception {
        assertThatThrownBy(() -> new MappingReleases(temp.resolve("nowhere"))).isInstanceOf(IllegalStateException.class).hasMessageContaining("not found");
        assertThatThrownBy(() -> new MappingReleases(temp)).isInstanceOf(IllegalStateException.class).hasMessageContaining("No mapping release");
    }

    @Test
    void aSectionFileWithAnInvalidNameStopsTheLoad() throws Exception {
        Path folder = copy();
        Path manifest = folder.resolve("0.2/manifest.json");
        Files.move(folder.resolve("0.2/assets.json"), folder.resolve("0.2/Assets.json"));
        write(manifest, Files.readString(manifest).replace("\"assets.json\"", "\"Assets.json\""));
        assertThatThrownBy(() -> new MappingReleases(folder)).isInstanceOf(IllegalStateException.class).hasMessageContaining("not a section file name");
    }
}
