package lab.federation.adapters.mapping;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.SortedMap;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import lab.federation.common.Json;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * The immutable mapping releases, read from a folder with one sub-folder per MAJOR.MINOR release. A release holds manifest.json and
 * one file per kind of reference (a section: assets.json, and crew.json from release 1.1). The manifest lists every file with its
 * SHA-256, so a changed, missing or unlisted file stops the start: a published release never changes. Hashes are taken over the
 * LF-normalized text (the repository's canonical Git-content form). Sections this adapter does not serve are loaded and checked all the
 * same, and a lookup in a section a release lacks gives null, never an error.
 */
@Component
public class MappingReleases {
    private static final Pattern RELEASE = Pattern.compile("[0-9]+\\.[0-9]+");
    private static final Pattern FILE = Pattern.compile("[a-z][a-z0-9-]*\\.json");
    static final String ASSETS = "assets";
    static final String CREW = "crew";

    /** One release as loaded: its number, its file hashes, its sections (kind, then local reference to identifier) and its checked-against list. */
    public record Release(String release, Map<String, String> files, Map<String, Map<String, String>> sections,
                          List<Map<String, Object>> checkedAgainst) {
        /** The Assets identifier of a Missions-local asset reference, or null when this release has no entry for it. */
        public String assetId(String localRef) {
            Map<String, String> assets = sections.get(ASSETS);
            return assets == null ? null : assets.get(localRef);
        }

        /** The Personnel v2 identifier of a Missions-local crew reference, or null when this release has no crew section or no entry for it. */
        public String personnelId(String localRef) {
            Map<String, String> crew = sections.get(CREW);
            return crew == null ? null : crew.get(localRef);
        }
    }

    private final SortedMap<String, Release> releases;

    @Autowired
    public MappingReleases(@Value("${mapping.releases-dir}") String directory) {
        this(Path.of(directory));
    }

    public MappingReleases(Path directory) {
        this.releases = load(directory);
    }

    /** The release with exactly this number, or null. There is no implicit latest and no partial match. */
    public Release find(String release) {
        return releases.get(release);
    }

    /** All releases, oldest first. */
    public List<Release> all() {
        return List.copyOf(releases.values());
    }

    // ---- loading ---------------------------------------------------------------------------------------------------

    private static int compare(String left, String right) {
        String[] a = left.split("\\.");
        String[] b = right.split("\\.");
        int major = Integer.compare(Integer.parseInt(a[0]), Integer.parseInt(b[0]));
        return major != 0 ? major : Integer.compare(Integer.parseInt(a[1]), Integer.parseInt(b[1]));
    }

    private static SortedMap<String, Release> load(Path directory) {
        if (!Files.isDirectory(directory)) {
            throw new IllegalStateException("Mapping releases folder not found: " + directory);
        }
        // Keys are always MAJOR.MINOR here (a folder with another name stops the load), and find() may be asked for anything.
        SortedMap<String, Release> found = new TreeMap<>((left, right) -> RELEASE.matcher(left).matches() && RELEASE.matcher(right).matches()
                ? compare(left, right) : left.compareTo(right));
        try (Stream<Path> children = Files.list(directory)) {
            for (Path child : children.sorted().toList()) {
                if (!Files.isDirectory(child)) {
                    throw new IllegalStateException("Unexpected file in the mapping releases folder: " + child.getFileName());
                }
                Release release = loadRelease(child);
                found.put(release.release(), release);
            }
        } catch (IOException error) {
            throw new IllegalStateException("Cannot read the mapping releases folder " + directory, error);
        }
        if (found.isEmpty()) {
            throw new IllegalStateException("No mapping release in " + directory);
        }
        return Collections.unmodifiableSortedMap(found);
    }

    @SuppressWarnings("unchecked")
    private static Release loadRelease(Path folder) throws IOException {
        String name = folder.getFileName().toString();
        if (!RELEASE.matcher(name).matches()) {
            throw new IllegalStateException("A mapping release folder must be named MAJOR.MINOR, not '" + name + "'");
        }
        Map<String, Object> manifest = Json.object(text(folder.resolve("manifest.json")));
        if (!name.equals(manifest.get("release"))) {
            throw new IllegalStateException("Release " + name + ": the manifest names release '" + manifest.get("release") + "'");
        }
        if (!(manifest.get("files") instanceof Map<?, ?> listed) || listed.isEmpty()) {
            throw new IllegalStateException("Release " + name + ": the manifest lists no files");
        }
        Set<String> onDisk = new HashSet<>();
        try (Stream<Path> children = Files.list(folder)) {
            children.forEach(child -> onDisk.add(child.getFileName().toString()));
        }
        onDisk.remove("manifest.json");
        if (!onDisk.equals(listed.keySet())) {
            throw new IllegalStateException("Release " + name + ": the files on disk " + new TreeSet<>(onDisk)
                    + " differ from the files the manifest lists " + new TreeSet<>(listed.keySet()));
        }
        Map<String, String> files = new LinkedHashMap<>();
        Map<String, Map<String, String>> sections = new LinkedHashMap<>();
        for (Map.Entry<?, ?> item : listed.entrySet()) {
            String file = (String) item.getKey();
            if (!FILE.matcher(file).matches()) {
                throw new IllegalStateException("Release " + name + ": '" + file + "' is not a section file name");
            }
            String content = text(folder.resolve(file));
            String actual = sha256(content);
            if (!actual.equals(item.getValue())) {
                throw new IllegalStateException("Release " + name + ": " + file + " does not match its hash in the manifest (a published release never changes)");
            }
            files.put(file, actual);
            sections.put(file.substring(0, file.length() - ".json".length()), entries(name, file, content));
        }
        if (!(manifest.get("checkedAgainst") instanceof List<?> checked) || checked.isEmpty()) {
            throw new IllegalStateException("Release " + name + ": the manifest has no checkedAgainst list");
        }
        List<Map<String, Object>> checkedAgainst = new ArrayList<>();
        for (Object item : checked) {
            checkedAgainst.add(Collections.unmodifiableMap(new LinkedHashMap<>((Map<String, Object>) item)));
        }
        return new Release(name, Collections.unmodifiableMap(files), Collections.unmodifiableMap(sections), List.copyOf(checkedAgainst));
    }

    private static Map<String, String> entries(String release, String file, String content) {
        if (!(Json.object(content).get("entries") instanceof Map<?, ?> raw)) {
            throw new IllegalStateException("Release " + release + ": " + file + " has no entries object");
        }
        Map<String, String> entries = new LinkedHashMap<>();
        for (Map.Entry<?, ?> entry : raw.entrySet()) {
            if (!(entry.getValue() instanceof String value)) {
                throw new IllegalStateException("Release " + release + ": " + file + " entry '" + entry.getKey() + "' is not a string");
            }
            entries.put((String) entry.getKey(), value);
        }
        return Collections.unmodifiableMap(entries);
    }

    private static String text(Path file) throws IOException {
        return Files.readString(file, StandardCharsets.UTF_8).replace("\r\n", "\n");
    }

    static String sha256(String content) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException(error);
        }
    }
}
