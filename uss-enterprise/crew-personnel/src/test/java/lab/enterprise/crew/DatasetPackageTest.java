package lab.enterprise.crew;

import static org.junit.jupiter.api.Assertions.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;
import java.util.function.UnaryOperator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class DatasetPackageTest {
    static final String VERSION = "crew-v1-large-003";
    private static final ObjectMapper JSON = new ObjectMapper();
    private final Map<String, byte[]> files = new HashMap<>();
    DatasetPackageTest() throws Exception {
        for (String name : names()) files.put(name, Files.readAllBytes(Path.of("datasets/released", VERSION, name)));
    }
    private static List<String> names() {
        var names = new ArrayList<String>(); names.add("manifest.json");
        for (int i = 0; i < 8; i++) names.add("page-00" + i + ".xml");
        return names;
    }
    private Dataset load() throws Exception {
        byte[] manifest = files.get("manifest.json");
        return DatasetPackage.load(VERSION, DatasetPackage.hash(manifest), manifest.length,
            name -> files.containsKey(name) ? new ByteArrayInputStream(files.get(name)) : null);
    }
    private void manifest(Consumer<ObjectNode> change) throws Exception {
        var node = (ObjectNode) JSON.readTree(files.get("manifest.json")); change.accept(node);
        files.put("manifest.json", JSON.writeValueAsBytes(node));
    }
    private void page(int index, UnaryOperator<String> change) throws Exception {
        String name = "page-00" + index + ".xml";
        byte[] bytes = change.apply(new String(files.get(name), StandardCharsets.UTF_8)).getBytes(StandardCharsets.UTF_8);
        files.put(name, bytes);
        String hash = DatasetPackage.hash(bytes);
        manifest(m -> { var p = (ObjectNode) m.path("pages").get(index); p.put("sha256", hash); p.put("byteLength", bytes.length); });
    }
    @Test void realRegistrationAndDefensiveConstruction() throws Exception {
        var loaded = Dataset.load(VERSION);
        assertEquals(800, loaded.records().size());
        assertEquals("CRW-2785", loaded.records().get(799).getCrewId());
        var records = loaded.records(); var copy = new Dataset(VERSION, records);
        records.get(0).setCrewId("CRW-9999");
        assertEquals("CRW-1047", loaded.records().get(0).getCrewId());
        assertEquals("CRW-1047", copy.records().get(0).getCrewId());
        assertThrows(UnsupportedOperationException.class, () -> copy.records().clear());
        assertEquals("crew-v1-small-002", Dataset.DEFAULT_VERSION);
    }
    @Test void rawIdentityRejectsCheckoutChangesAndMissingManifest() throws Exception {
        byte[] original = files.get("manifest.json"); String hash = DatasetPackage.hash(original);
        for (String changed : List.of(new String(original, StandardCharsets.UTF_8).replace("\n", "\r\n"),
                "\uFEFF" + new String(original, StandardCharsets.UTF_8), new String(original, StandardCharsets.UTF_8).replace("  ", " "),
                new String(original, StandardCharsets.UTF_8).replace("800", "801"))) {
            files.put("manifest.json", changed.getBytes(StandardCharsets.UTF_8));
            assertThrows(Exception.class, () -> DatasetPackage.load(VERSION, hash, original.length,
                n -> new ByteArrayInputStream(files.get(n))));
        }
        assertThrows(Exception.class, () -> DatasetPackage.load(VERSION, hash, original.length, n -> null));
    }
    @ParameterizedTest @ValueSource(strings={"missing", "length", "hash", "crlf", "bom"})
    void pageIntegrity(String mode) throws Exception {
        String name = "page-004.xml"; byte[] bytes = files.get(name);
        switch (mode) {
            case "missing" -> files.remove(name);
            case "length" -> files.put(name, Arrays.copyOf(bytes, bytes.length - 1));
            case "hash" -> { bytes[200] ^= 1; files.put(name, bytes); }
            case "crlf" -> files.put(name, new String(bytes, StandardCharsets.UTF_8).replace("\n", "\r\n").getBytes(StandardCharsets.UTF_8));
            case "bom" -> files.put(name, ("\uFEFF" + new String(bytes, StandardCharsets.UTF_8)).getBytes(StandardCharsets.UTF_8));
        }
        assertThrows(Exception.class, this::load);
    }
    @ParameterizedTest @ValueSource(strings={"../page-000.xml", "/page-000.xml", "file:///page-000.xml", "https://example.test/page", "page-001.xml", "page\\000.xml"})
    void exactNamesRejectTraversalAndDuplicateDescriptors(String name) throws Exception {
        manifest(m -> ((ObjectNode) m.path("pages").get(0)).put("filename", name));
        assertThrows(Exception.class, this::load);
    }
    @ParameterizedTest @ValueSource(strings={"format", "version", "count", "string", "float", "boolean", "null", "extra", "missing", "pages", "reorder", "offset", "pageCount", "huge", "recipe", "nestedType"})
    void strictManifest(String mode) throws Exception {
        manifest(m -> {
            var p = (ObjectNode) m.path("pages").get(0);
            switch (mode) {
                case "format" -> m.put("formatVersion", 2);
                case "version" -> m.put("datasetVersion", "crew-v1-small-002");
                case "count" -> m.put("count", 799);
                case "string" -> m.put("count", "800");
                case "float" -> m.put("count", 800.0);
                case "boolean" -> m.put("formatVersion", true);
                case "null" -> m.putNull("count");
                case "extra" -> m.put("unknown", 1);
                case "missing" -> m.remove("count");
                case "pages" -> ((ArrayNode) m.path("pages")).remove(7);
                case "reorder" -> { var a = (ArrayNode) m.path("pages"); var b = a.get(1); a.set(1, a.get(0)); a.set(0, b); }
                case "offset" -> p.put("offset", 1);
                case "pageCount" -> p.put("count", 99);
                case "huge" -> p.put("byteLength", Long.MAX_VALUE);
                case "recipe" -> m.put("recipe", "opaque");
                case "nestedType" -> ((ObjectNode) m.path("recipe").path("status")).put("inactiveModulo", true);
            }
        });
        assertThrows(Exception.class, this::load);
    }
    @ParameterizedTest @ValueSource(strings={"rootDuplicate", "nestedDuplicate", "trailing", "malformed"})
    void strictJson(String mode) throws Exception {
        String original = new String(files.get("manifest.json"), StandardCharsets.UTF_8);
        String changed = switch (mode) {
            case "rootDuplicate" -> original.replaceFirst("\\{", "{\"count\":800,");
            case "nestedDuplicate" -> original.replace("\"algorithm\":", "\"algorithm\":\"x\",\"algorithm\":");
            case "trailing" -> original + " {}";
            default -> "{";
        };
        files.put("manifest.json", changed.getBytes(StandardCharsets.UTF_8));
        assertThrows(Exception.class, this::load);
    }
    @ParameterizedTest @ValueSource(strings={"version", "total", "offset", "limit", "hasMore", "count", "schema", "malformed", "dtd", "duplicate", "order", "dangling", "self", "cycle"})
    void rehashedPagesExerciseReadiness(String mode) throws Exception {
        switch (mode) {
            case "version" -> page(1, s -> s.replace(VERSION, "crew-v1-small-002"));
            case "total" -> page(1, s -> s.replace("<cp:totalCount>800", "<cp:totalCount>799"));
            case "offset" -> page(1, s -> s.replace("<cp:offset>100", "<cp:offset>0"));
            case "limit" -> page(1, s -> s.replace("<cp:limit>100", "<cp:limit>99"));
            case "hasMore" -> page(7, s -> s.replace("<cp:hasMore>false", "<cp:hasMore>true"));
            case "count" -> page(1, s -> s.replaceFirst("(?s)  <cp:crewMember>.*?</cp:crewMember>\\n", ""));
            case "schema" -> page(1, s -> s.replaceFirst("<cp:rank>[^<]+", "<cp:rank>INVALID"));
            case "malformed" -> page(1, s -> s + "<");
            case "dtd" -> page(1, s -> s.replace("?>", "?><!DOCTYPE x [<!ENTITY x SYSTEM 'file:///secret'>]>"));
            case "duplicate" -> page(1, s -> s.replaceFirst("<cp:crewId>[^<]+", "<cp:crewId>CRW-2085"));
            case "order" -> page(1, s -> s.replaceFirst("<cp:crewId>[^<]+", "<cp:crewId>CRW-0001"));
            case "dangling" -> page(1, s -> s.replaceFirst("<cp:supervisorCrewId>[^<]+", "<cp:supervisorCrewId>CRW-9999"));
            case "self" -> page(1, s -> s.replaceFirst("<cp:supervisorCrewId>[^<]+", "<cp:supervisorCrewId>CRW-2086"));
            case "cycle" -> {
                page(1, s -> s.replaceFirst("<cp:supervisorCrewId>[^<]+", "<cp:supervisorCrewId>CRW-2186"));
                page(2, s -> s.replaceFirst("<cp:supervisorCrewId>[^<]+", "<cp:supervisorCrewId>CRW-2086"));
            }
        }
        assertThrows(Exception.class, this::load);
    }
    @Test void validForwardAndBackwardCrossPageReferences() throws Exception {
        page(1, s -> s.replaceFirst("<cp:supervisorCrewId>[^<]+", "<cp:supervisorCrewId>CRW-2785"));
        assertEquals(800, load().records().size());
    }
    @Test void readsAreBoundedBeforeXmlParsing() throws Exception {
        byte[] manifest = files.get("manifest.json");
        var consumed = new java.util.concurrent.atomic.AtomicInteger();
        assertThrows(Exception.class, () -> DatasetPackage.load(VERSION, DatasetPackage.hash(manifest), manifest.length,
            name -> name.equals("manifest.json") ? new ByteArrayInputStream(manifest) : new InputStream() {
                public int read() { consumed.incrementAndGet(); return 'x'; }
            }));
        assertEquals(35980, consumed.get());
    }
}
