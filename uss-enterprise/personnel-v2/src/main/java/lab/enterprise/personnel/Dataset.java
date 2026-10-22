package lab.enterprise.personnel;

import jakarta.xml.bind.JAXBContext;
import java.security.MessageDigest;
import java.util.*;
import lab.enterprise.personnel.contract.*;

/** A single immutable snapshot, checked before publishing the HTTP endpoint. */
final class Dataset {
    static final String DEFAULT_VERSION = "personnel-v2-small-002";
    private sealed interface Registration permits Snapshot, PagedPackage { }
    /** One complete response (a small snapshot) pinned by the SHA-256 of its raw bytes. */
    private record Snapshot(String hash) implements Registration { }
    /** Pages of the unchanged contract: the pinned manifest and the pinned page hashes in order (see DatasetPackage). */
    record PagedPackage(String manifestHash, int manifestLength, int count, List<String> pageHashes) implements Registration { }
    private static final Map<String, Registration> REGISTERED = Map.of(
        "personnel-v2-small-001", new Snapshot("cecd2f407ccfd47356b07fc7d11b2cb84d4fb30a7701a241e067d51d36e174df"),
        "personnel-v2-small-002", new Snapshot("c7550f57350846f3a7833caf23461916ebef12ab26f34c631d92a115299168f8"),
        "personnel-v2-small-003", new Snapshot("d89651c9966108a57e109f8bb0b4879109b7cdaad64825b85ba4093db795293b"),
        "personnel-v2-large-004", new PagedPackage("d44e96b8853290b8423be5fe53dc8270f4e1155a52287ebe30e486c2eae7ef47", 4145, 1000, List.of(
            "0d5b60e81d0757eae3b208ee8b6fa04823004bd515d4091cc4f863c4c4ec931e",
            "38439a7dcc414e913fbdf1bbcc82c337434cdd116980d6dd190f3bae09250e5d",
            "6b98815625ecce7c46e9cdabe7f30caf080fed1364bb09b922456979548a9a7f",
            "19a5da376a9fa0ee06126da4d3f253d7f9a8c6353cd31727d991fda3af5a087f",
            "f5d1a3d150a78f65675384670c11e0acb4ef78bccb625956f38dec46ef8acb2d",
            "b547a2bd06c6f7e18007ef387d756374580f0f7cf1f3586dba8553ce2e59da00",
            "bb0035e30909040c2889c1f3140b63d08d40eb68306777af0d3068842d92880c",
            "70af8313dafaf6ed98ec17969801922f573014e4170df4b1805a3063abc882ae",
            "1a07850589a86f519aa76993e9202b3240dca5a6de722e4871db973a82405aac",
            "3fc12bd1afb15d9e3efe3b0bff7ccc3dcf87d73b48fd295b9f58b3e43e1818ff")));
    final String version;
    private final List<PersonnelMember> members;

    static Dataset load(String version) throws Exception {
        var registration = REGISTERED.get(version);
        if (registration == null) throw new IllegalArgumentException("Unknown canonical dataset: " + version);
        if (registration instanceof PagedPackage paged)
            return DatasetPackage.load(version, paged, name -> Dataset.class.getResourceAsStream("/datasets/" + version + "/" + name));
        try (var stream = Dataset.class.getResourceAsStream("/datasets/" + version + ".xml")) {
            if (stream == null) throw new IllegalStateException("Missing registered dataset");
            return load(version, stream.readAllBytes());
        }
    }

    // Exact raw-byte snapshot identity; no v1 CRLF hash normalization is applied.
    static Dataset load(String version, byte[] bytes) throws Exception {
        if (!(REGISTERED.get(version) instanceof Snapshot registration)) throw new IllegalArgumentException("Unknown v2 dataset: " + version);
        String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        if (!registration.hash().equals(hash)) throw new IllegalStateException("Immutable dataset hash mismatch");
        Dataset dataset = parse(bytes);
        if (!version.equals(dataset.version)) throw new IllegalStateException("Dataset version mismatch");
        return dataset;
    }

    // Package access permits negative readiness tests; startup only loads registered snapshots.
    static Dataset parse(byte[] bytes) throws Exception {
        var root = Xml.parse(bytes).getDocumentElement();
        Xml.validate(root);
        var snapshot = JAXBContext.newInstance(ObjectFactory.class).createUnmarshaller()
            .unmarshal(root, ListPersonnelMembersResponseType.class).getValue();
        if (!"ListPersonnelMembersResponse".equals(root.getLocalName()) ||
            snapshot.getTotalCount() != snapshot.getPersonnelMember().size() || snapshot.getOffset() != 0 ||
            snapshot.getLimit() != 20 || snapshot.isHasMore() || snapshot.getTotalCount() > 20)
            throw new IllegalArgumentException("Incomplete small dataset snapshot");
        return new Dataset(snapshot.getDatasetVersion(), snapshot.getPersonnelMember());
    }

    Dataset(String version, List<PersonnelMember> records) {
        this.version = version;
        var byId = new TreeMap<String, PersonnelMember>();
        for (var member : records)
            if (byId.putIfAbsent(member.getPersonnelId(), member) != null)
                throw new IllegalArgumentException("Duplicate personnel ID");
        for (var member : records) {
            var visited = new HashSet<String>();
            String id = member.getPersonnelId();
            while (id != null) {
                if (!visited.add(id)) throw new IllegalArgumentException("Supervisor cycle");
                var next = byId.get(id);
                if (next == null) throw new IllegalArgumentException("Dangling supervisor");
                id = next.getCrewDetails() == null ? null : next.getCrewDetails().getSupervisorPersonnelId();
            }
        }
        members = byId.values().stream().map(Dataset::copy).toList();
    }

    List<PersonnelMember> records() { return members.stream().map(Dataset::copy).toList(); }
    private static PersonnelMember copy(PersonnelMember source) {
        var result = new PersonnelMember();
        result.setPersonnelId(source.getPersonnelId()); result.setDisplayName(source.getDisplayName());
        result.setPositionTitle(source.getPositionTitle()); result.setDutyStatus(source.getDutyStatus());
        if (source.getCrewDetails() != null) {
            var details = new CrewDetails();
            details.setRank(source.getCrewDetails().getRank());
            details.setDepartment(source.getCrewDetails().getDepartment());
            details.setSecurityClearance(source.getCrewDetails().getSecurityClearance());
            details.setSupervisorPersonnelId(source.getCrewDetails().getSupervisorPersonnelId());
            result.setCrewDetails(details);
        } else result.setCivilianDetails(new CivilianDetails());
        return result;
    }
}
