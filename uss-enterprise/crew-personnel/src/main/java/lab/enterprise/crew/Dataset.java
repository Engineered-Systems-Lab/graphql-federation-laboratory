package lab.enterprise.crew;

import jakarta.xml.bind.JAXBContext;
import java.security.MessageDigest;
import java.util.*;
import lab.enterprise.crew.contract.*;

/** A single immutable snapshot, checked before publishing the HTTP endpoint. */
final class Dataset {
    static final String DEFAULT_VERSION = "crew-v1-small-002";
    private sealed interface Registration permits LegacySnapshot, PagedPackage { }
    private record LegacySnapshot(String hash) implements Registration { }
    private record PagedPackage(String root, String manifestHash, int manifestLength) implements Registration { }
    private static final Map<String, Registration> REGISTERED = Map.of(
        "crew-v1-small-001", new LegacySnapshot("daeebe24706e3345d3f14c320a8fb9eb866fcfea7ce2dc8f01ce1977bbc0a35e"),
        "crew-v1-small-002", new LegacySnapshot("6cf7e7ec590fa247aa8f884916a4014ce86aa27276c7bcbe409abd65465da8b9"),
        "crew-v1-large-003", new PagedPackage("/datasets/released/crew-v1-large-003/",
            "c06125dbe6883981293b485497474c46a0128372056efca389d7421f35ba2690", 116874));
    final String version;
    private final List<CrewMember> members;

    static Dataset load(String version) throws Exception {
        var registration = REGISTERED.get(version);
        if (registration == null) throw new IllegalArgumentException("Unknown canonical dataset: " + version);
        if (registration instanceof PagedPackage pkg)
            return DatasetPackage.load(version, pkg.manifestHash(), pkg.manifestLength(),
                name -> Dataset.class.getResourceAsStream(pkg.root() + name));
        try (var stream = Dataset.class.getResourceAsStream("/datasets/" + version + ".xml")) {
            if (stream == null) throw new IllegalStateException("Missing registered dataset");
            return load(version, stream.readAllBytes());
        }
    }

    // Shared startup integrity/readiness path; tests supply alternate checkout representations.
    static Dataset load(String version, byte[] bytes) throws Exception {
        if (!(REGISTERED.get(version) instanceof LegacySnapshot registration))
            throw new IllegalArgumentException("Unknown legacy dataset: " + version);
        // Git LF identity: remove only CR immediately followed by LF, without decoding or changing parser input.
        var digest = MessageDigest.getInstance("SHA-256");
        for (int i = 0; i < bytes.length; i++) {
            if (bytes[i] == '\r' && i + 1 < bytes.length && bytes[i + 1] == '\n') continue;
            digest.update(bytes[i]);
        }
        String hash = HexFormat.of().formatHex(digest.digest());
        if (!registration.hash().equals(hash)) throw new IllegalStateException("Immutable dataset hash mismatch");
        Dataset dataset = parse(bytes);
        if (!version.equals(dataset.version)) throw new IllegalStateException("Dataset version mismatch");
        return dataset;
    }

    // Package access permits readiness tests with existing negative/edge fixtures; startup only loads registered snapshots.
    static Dataset parse(byte[] bytes) throws Exception {
        var root = Xml.parse(bytes).getDocumentElement();
        Xml.validate(root);
        var snapshot = JAXBContext.newInstance(ObjectFactory.class).createUnmarshaller()
            .unmarshal(root, ListCrewMembersResponseType.class).getValue();
        if (!"ListCrewMembersResponse".equals(root.getLocalName()) ||
            snapshot.getTotalCount() != snapshot.getCrewMember().size() || snapshot.getOffset() != 0 ||
            snapshot.getLimit() != 20 || snapshot.isHasMore() || snapshot.getTotalCount() > 20)
            throw new IllegalArgumentException("Incomplete small dataset snapshot");
        return new Dataset(snapshot.getDatasetVersion(), snapshot.getCrewMember());
    }

    Dataset(String version, List<CrewMember> records) {
        this.version = version;
        var byId = new TreeMap<String, CrewMember>();
        for (var member : records)
            if (byId.putIfAbsent(member.getCrewId(), member) != null)
                throw new IllegalArgumentException("Duplicate crew ID");
        for (var member : records) {
            var visited = new HashSet<String>();
            String id = member.getCrewId();
            while (id != null) {
                if (!visited.add(id)) throw new IllegalArgumentException("Supervisor cycle");
                var next = byId.get(id);
                if (next == null) throw new IllegalArgumentException("Dangling supervisor");
                id = next.getSupervisorCrewId();
            }
        }
        members = byId.values().stream().map(Dataset::copy).toList();
    }

    List<CrewMember> records() { return members.stream().map(Dataset::copy).toList(); }
    private static CrewMember copy(CrewMember source) {
        var result = new CrewMember();
        result.setCrewId(source.getCrewId()); result.setDisplayName(source.getDisplayName());
        result.setRank(source.getRank()); result.setDepartment(source.getDepartment());
        result.setPositionTitle(source.getPositionTitle()); result.setDutyStatus(source.getDutyStatus());
        result.setSupervisorCrewId(source.getSupervisorCrewId());
        return result;
    }
}
