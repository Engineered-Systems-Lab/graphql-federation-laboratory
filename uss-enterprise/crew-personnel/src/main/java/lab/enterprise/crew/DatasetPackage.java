package lab.enterprise.crew;

import com.fasterxml.jackson.core.StreamReadFeature;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.json.JsonMapper;
import jakarta.xml.bind.JAXBContext;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.*;
import lab.enterprise.crew.contract.*;

/** Format-1 package readiness. No discovery, extraction, or request-time resource access. */
final class DatasetPackage {
    private static final ObjectMapper JSON = JsonMapper.builder()
        .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
        .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build();
    @FunctionalInterface interface Resources { InputStream open(String basename) throws Exception; }
    private DatasetPackage() { }

    // Supplied identity/resources are a package-private test seam, never operator configuration.
    static Dataset load(String version, String manifestHash, int manifestLength, Resources resources) throws Exception {
        byte[] bytes = read(resources, "manifest.json", manifestLength);
        require(hash(bytes).equals(manifestHash), "Manifest hash mismatch");
        JsonNode manifest = JSON.readTree(bytes);
        fields(manifest, Set.of("formatVersion", "datasetVersion", "count", "pages", "generator", "recipe"));
        require(integer(manifest, "formatVersion") == 1, "Unsupported manifest format");
        require("crew-v1-large-003".equals(version) && version.equals(string(manifest, "datasetVersion")), "Package version mismatch");
        require(integer(manifest, "count") == 800, "Package count mismatch");
        // Recipe/generator provenance is bound by the raw manifest pin and audited by the release validator.
        provenance(manifest);
        JsonNode pages = manifest.path("pages");
        require(pages.isArray() && pages.size() == 8, "Expected eight pages");
        var records = new ArrayList<CrewMember>(800);
        var unmarshaller = JAXBContext.newInstance(ObjectFactory.class).createUnmarshaller();
        String previous = null;
        for (int i = 0; i < 8; i++) {
            JsonNode page = pages.get(i);
            fields(page, Set.of("filename", "byteLength", "sha256", "count", "offset"));
            String filename = "page-00" + i + ".xml";
            require(filename.equals(string(page, "filename")), "Unexpected ordered page name");
            require(integer(page, "count") == 100 && integer(page, "offset") == i * 100, "Page descriptor metadata mismatch");
            int length = integer(page, "byteLength");
            require(length > 0 && length <= 131072, "Page length out of bounds");
            String expected = string(page, "sha256");
            require(expected.matches("[0-9a-f]{64}"), "Invalid page hash");
            byte[] xml = read(resources, filename, length);
            require(hash(xml).equals(expected), "Page hash mismatch: " + filename);
            var root = Xml.parse(xml).getDocumentElement();
            Xml.validate(root);
            require("ListCrewMembersResponse".equals(root.getLocalName()), "Wrong page wrapper");
            var response = unmarshaller.unmarshal(root, ListCrewMembersResponseType.class).getValue();
            require(version.equals(response.getDatasetVersion()) && response.getTotalCount() == 800 &&
                response.getOffset() == i * 100 && response.getLimit() == 100 &&
                response.isHasMore() == (i < 7) && response.getCrewMember().size() == 100, "Page response metadata mismatch");
            for (var member : response.getCrewMember()) {
                require(previous == null || previous.compareTo(member.getCrewId()) < 0, "IDs must be strictly increasing across all pages");
                previous = member.getCrewId();
                records.add(member);
            }
        }
        require(records.size() == 800, "Aggregate count mismatch");
        // Resolve the entire graph only after all pages, allowing forward/backward references.
        return new Dataset(version, records);
    }

    private static byte[] read(Resources resources, String name, int length) throws Exception {
        require(length > 0 && length <= 1048576, "Resource length out of bounds");
        try (InputStream stream = resources.open(name)) {
            require(stream != null, "Missing registered resource: " + name);
            byte[] bytes = stream.readNBytes(length + 1);
            require(bytes.length == length, "Resource length mismatch: " + name);
            return bytes;
        }
    }
    static String hash(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    private static int integer(JsonNode object, String name) {
        JsonNode value = object.path(name);
        require(value.isIntegralNumber() && value.canConvertToInt(), "Expected integer: " + name);
        return value.intValue();
    }
    private static String string(JsonNode object, String name) {
        JsonNode value = object.path(name);
        require(value.isTextual(), "Expected string: " + name);
        return value.textValue();
    }
    private static void fields(JsonNode object, Set<String> expected) {
        require(object != null && object.isObject(), "Expected object");
        var actual = new HashSet<String>();
        object.fieldNames().forEachRemaining(actual::add);
        require(actual.equals(expected), "Unexpected manifest fields");
    }
    // Closed format/type checks only; Python release validation owns recipe interpretation.
    // s = string, i = integer, o = object, a = array.
    private static void shape(JsonNode node, String definition) {
        var names = new HashSet<String>();
        for (String entry : definition.split(" ")) {
            String[] pair = entry.split(":"); names.add(pair[0]);
            JsonNode value = node.path(pair[0]);
            boolean valid = switch (pair[1]) {
                case "s" -> value.isTextual();
                case "i" -> value.isIntegralNumber() && value.canConvertToInt();
                case "o" -> value.isObject();
                case "a" -> value.isArray();
                default -> false;
            };
            require(valid, "Invalid manifest type: " + pair[0]);
        }
        fields(node, names);
    }
    private static void strings(JsonNode array, int size) {
        require(array.isArray() && array.size() == size, "Invalid manifest array size");
        for (var item : array) require(item.isTextual(), "Expected string array");
    }
    private static void provenance(JsonNode manifest) {
        var generator = manifest.path("generator");
        shape(generator, "identity:s algorithm:s toolchain:o source:o");
        shape(generator.path("toolchain"), "implementation:s version:s dependencies:s");
        shape(generator.path("source"), "path:s hashing:s sha256:s");
        var recipe = manifest.path("recipe");
        shape(recipe, "seed:s referenceClock:s departments:a ranks:a distribution:a givenNames:a familyNames:a roster:a identityLedger:a positionTitles:o departmentLeads:o allocation:o names:o reporting:o status:o serialization:o");
        strings(recipe.path("departments"), 7); strings(recipe.path("ranks"), 8);
        strings(recipe.path("givenNames"), 32); strings(recipe.path("familyNames"), 32);
        var distribution = recipe.path("distribution");
        require(distribution.size() == 7, "Invalid distribution size");
        for (var row : distribution) {
            require(row.isArray() && row.size() == 8, "Invalid distribution row");
            for (var cell : row) require(cell.isIntegralNumber() && cell.canConvertToInt(), "Invalid distribution cell");
        }
        shape(recipe.path("positionTitles"), "LIEUTENANT_COMMANDER:s LIEUTENANT:s ENSIGN:s CHIEF_PETTY_OFFICER:s CREWMAN:s CIVILIAN:s");
        shape(recipe.path("departmentLeads"), "COMMAND:s OPERATIONS:s ENGINEERING:s SCIENCE:s MEDICAL:s SECURITY:s");
        shape(recipe.path("allocation"), "backgroundStart:i backgroundCount:i namedReservation:a order:s");
        var reservation = recipe.path("allocation").path("namedReservation");
        require(reservation.size() == 2, "Invalid reservation size");
        for (var id : reservation) require(id.isIntegralNumber() && id.canConvertToInt(), "Invalid reservation type");
        shape(recipe.path("names"), "candidateCount:i familyRadix:i hashInput:s order:s deduplicate:s");
        shape(recipe.path("reporting"), "flightLeadRank:s flightLeadChoice:s flightLeadSupervisor:s flightLeadTitle:s sectionRank:s sectionChoice:s sectionTitle:s directLeadModulo:i localOrder:s");
        shape(recipe.path("status"), "inactiveModulo:i onLeaveModulo:i precedence:a");
        strings(recipe.path("status").path("precedence"), 4);
        shape(recipe.path("serialization"), "xml:s json:s pageSize:i recordOrder:s fieldOrder:a");
        strings(recipe.path("serialization").path("fieldOrder"), 7);
        require(recipe.path("roster").size() == 14, "Invalid roster size");
        for (var member : recipe.path("roster"))
            shape(member, "crewId:s displayName:s rank:s department:s positionTitle:s dutyStatus:s" +
                (member.has("supervisorCrewId") ? " supervisorCrewId:s" : ""));
        require(recipe.path("identityLedger").size() == 800, "Invalid ledger size");
        int index = 0;
        for (var entry : recipe.path("identityLedger")) {
            fields(entry, Set.of("crewId", "displayName", "slot", "nameCandidate"));
            string(entry, "crewId"); string(entry, "displayName");
            for (String name : List.of("slot", "nameCandidate")) {
                if (index < 14) require(entry.path(name).isNull(), "Named ledger entry requires null");
                else integer(entry, name);
            }
            index++;
        }
    }
    private static void require(boolean valid, String message) {
        if (!valid) throw new IllegalArgumentException(message);
    }
}
