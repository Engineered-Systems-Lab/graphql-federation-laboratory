package lab.enterprise.personnel;

import jakarta.xml.bind.JAXBContext;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.*;
import lab.enterprise.personnel.contract.*;

/**
 * A snapshot too large for one response (the contract returns at most 100 members), kept as pages of the unchanged contract:
 * page-000.xml and the following, each a valid ListPersonnelMembersResponse of 100 members (the last holds the rest), plus
 * manifest.json. The registration pins the raw bytes of the manifest and of every page; the manifest is provenance and is not parsed.
 * No discovery, extraction or request-time resource access.
 */
final class DatasetPackage {
    static final int PAGE_SIZE = 100;
    @FunctionalInterface interface Resources { InputStream open(String basename) throws Exception; }
    private DatasetPackage() { }

    // Supplied resources are a package-private test seam, never operator configuration.
    static Dataset load(String version, Dataset.PagedPackage registration, Resources resources) throws Exception {
        byte[] manifest = read(resources, "manifest.json", registration.manifestLength());
        require(hash(manifest).equals(registration.manifestHash()), "Manifest hash mismatch");
        int pages = registration.pageHashes().size();
        int count = registration.count();
        require(pages == (count + PAGE_SIZE - 1) / PAGE_SIZE, "Registration page count mismatch");
        var records = new ArrayList<PersonnelMember>(count);
        var unmarshaller = JAXBContext.newInstance(ObjectFactory.class).createUnmarshaller();
        String previous = null;
        for (int i = 0; i < pages; i++) {
            String filename = String.format("page-%03d.xml", i);
            byte[] xml = read(resources, filename, 262144);
            require(hash(xml).equals(registration.pageHashes().get(i)), "Page hash mismatch: " + filename);
            var root = Xml.parse(xml).getDocumentElement();
            Xml.validate(root);
            require("ListPersonnelMembersResponse".equals(root.getLocalName()), "Wrong page wrapper");
            var response = unmarshaller.unmarshal(root, ListPersonnelMembersResponseType.class).getValue();
            int expected = Math.min(PAGE_SIZE, count - i * PAGE_SIZE);
            require(version.equals(response.getDatasetVersion()) && response.getTotalCount() == count &&
                response.getOffset() == i * PAGE_SIZE && response.getLimit() == PAGE_SIZE &&
                response.isHasMore() == (i < pages - 1) && response.getPersonnelMember().size() == expected,
                "Page response metadata mismatch: " + filename);
            for (var member : response.getPersonnelMember()) {
                require(previous == null || previous.compareTo(member.getPersonnelId()) < 0,
                    "IDs must be strictly increasing across all pages");
                previous = member.getPersonnelId();
                records.add(member);
            }
        }
        require(records.size() == count, "Aggregate count mismatch");
        // Unique IDs, known supervisors and no reporting cycle are checked over the whole snapshot, after every page.
        return new Dataset(version, records);
    }

    // The resource is read up to the given length plus one byte, so that a longer or shorter file is refused.
    private static byte[] read(Resources resources, String name, int length) throws Exception {
        try (InputStream stream = resources.open(name)) {
            require(stream != null, "Missing registered resource: " + name);
            byte[] bytes = stream.readNBytes(length + 1);
            if (name.equals("manifest.json")) require(bytes.length == length, "Resource length mismatch: " + name);
            else require(bytes.length > 0 && bytes.length <= length, "Resource length out of bounds: " + name);
            return bytes;
        }
    }

    static String hash(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private static void require(boolean valid, String message) {
        if (!valid) throw new IllegalArgumentException(message);
    }
}
