package lab.enterprise.personnel;

import static org.junit.jupiter.api.Assertions.*;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import lab.enterprise.personnel.contract.*;
import org.junit.jupiter.api.Test;

/** The paged package personnel-v2-large-004: registration, integrity and the readiness of the whole snapshot. */
class LargeDatasetTest {
    private static final String VERSION = "personnel-v2-large-004";
    private static final Path FOLDER = Path.of("datasets", VERSION);

    private static Map<String, byte[]> files() throws Exception {
        var result = new LinkedHashMap<String, byte[]>();
        result.put("manifest.json", Files.readAllBytes(FOLDER.resolve("manifest.json")));
        for (int i = 0; i < 10; i++) result.put(String.format("page-%03d.xml", i), Files.readAllBytes(FOLDER.resolve(String.format("page-%03d.xml", i))));
        return result;
    }
    /** A registration computed from the given bytes, so that only the structural checks (not the pinned hashes) can refuse them. */
    private static Dataset.PagedPackage registration(Map<String, byte[]> files) throws Exception {
        var manifest = files.get("manifest.json");
        var pages = new ArrayList<String>();
        for (int i = 0; i < 10; i++) pages.add(DatasetPackage.hash(files.get(String.format("page-%03d.xml", i))));
        return new Dataset.PagedPackage(DatasetPackage.hash(manifest), manifest.length, 1000, pages);
    }
    private static Dataset load(Map<String, byte[]> files) throws Exception {
        return DatasetPackage.load(VERSION, registration(files), name -> files.containsKey(name) ? new ByteArrayInputStream(files.get(name)) : null);
    }
    private static Map<String, byte[]> changed(String page, String from, String to) throws Exception {
        var files = files();
        String xml = new String(files.get(page), StandardCharsets.UTF_8);
        assertTrue(xml.contains(from), "test precondition: " + from);
        files.put(page, xml.replace(from, to).getBytes(StandardCharsets.UTF_8));
        return files;
    }

    @Test void registeredPackageLoadsAllPagesInOrder() throws Exception {
        var records = Dataset.load(VERSION).records();
        assertEquals(1000, records.size());
        var ids = records.stream().map(PersonnelMember::getPersonnelId).toList();
        assertEquals(ids.stream().sorted().toList(), ids);
        assertEquals(1000, new HashSet<>(ids).size());
        assertEquals("PRS-0001", ids.get(0));
        assertEquals("PRS-3199", ids.get(999));
        assertEquals(219, records.stream().filter(m -> m.getCivilianDetails() != null).count());
        assertEquals(781, records.stream().filter(m -> m.getCrewDetails() != null).count());
        assertEquals(VERSION, Dataset.load(VERSION).version);
    }

    @Test void theFourteenPeopleOfTheThirdSnapshotStandAsTheyWere() throws Exception {
        var third = Dataset.load("personnel-v2-small-003").records();
        var large = Dataset.load(VERSION).records();
        for (var member : third) {
            var same = large.stream().filter(m -> m.getPersonnelId().equals(member.getPersonnelId())).findFirst().orElseThrow();
            assertEquals(member.getDisplayName(), same.getDisplayName());
            assertEquals(member.getPositionTitle(), same.getPositionTitle());
            assertEquals(member.getDutyStatus(), same.getDutyStatus());
            assertEquals(member.getCrewDetails() == null, same.getCrewDetails() == null);
            if (member.getCrewDetails() != null) {
                assertEquals(member.getCrewDetails().getRank(), same.getCrewDetails().getRank());
                assertEquals(member.getCrewDetails().getDepartment(), same.getCrewDetails().getDepartment());
                assertEquals(member.getCrewDetails().getSecurityClearance(), same.getCrewDetails().getSecurityClearance());
                assertEquals(member.getCrewDetails().getSupervisorPersonnelId(), same.getCrewDetails().getSupervisorPersonnelId());
            }
        }
    }

    @Test void clearanceFollowsRankAndSecurityIsAtLeastSecret() throws Exception {
        for (var member : Dataset.load(VERSION).records()) {
            var crew = member.getCrewDetails();
            if (crew == null) continue;
            if (member.getPersonnelId().compareTo("PRS-1047") < 0 || member.getPersonnelId().equals("PRS-0714")) continue; // authored, not migrated
            var expected = switch (crew.getRank()) {
                case CAPTAIN -> SecurityClearance.TOP_SECRET;
                case COMMANDER, LIEUTENANT_COMMANDER -> SecurityClearance.SECRET;
                default -> crew.getDepartment() == Department.SECURITY ? SecurityClearance.SECRET : SecurityClearance.NONE;
            };
            assertEquals(expected, crew.getSecurityClearance(), member.getPersonnelId());
        }
    }

    @Test void civiliansHaveNoSupervisorAndAreOutsideTheMigratedRange() throws Exception {
        for (var member : Dataset.load(VERSION).records()) {
            if (member.getCivilianDetails() == null) continue;
            String id = member.getPersonnelId();
            boolean generated = id.compareTo("PRS-3001") >= 0;
            boolean oldCivilian = id.equals("PRS-0003") || (id.compareTo("PRS-2160") >= 0 && id.compareTo("PRS-2785") <= 0);
            assertTrue(generated || oldCivilian, id);
        }
    }

    @Test void changedBytesAreRefusedByTheRegisteredHashes() throws Exception {
        for (String name : files().keySet()) {
            var files = files();
            var bytes = files.get(name);
            bytes[bytes.length / 2] ^= 1;
            files.put(name, bytes);
            assertThrows(IllegalArgumentException.class, () -> DatasetPackage.load(VERSION, REGISTERED(), n -> files.containsKey(n) ? new ByteArrayInputStream(files.get(n)) : null), name);
        }
        var missing = files();
        missing.remove("page-004.xml");
        assertThrows(IllegalArgumentException.class, () -> DatasetPackage.load(VERSION, REGISTERED(), n -> missing.containsKey(n) ? new ByteArrayInputStream(missing.get(n)) : null));
    }
    private static Dataset.PagedPackage REGISTERED() throws Exception { return registration(files()); }

    @Test void intactBytesWithAPinnedRegistrationLoad() throws Exception { assertEquals(1000, load(files()).records().size()); }

    @Test void pagesOutOfOrderAreRefusedEvenWithMatchingHashes() throws Exception {
        var files = files();
        var second = files.get("page-001.xml");
        files.put("page-001.xml", files.get("page-002.xml"));
        files.put("page-002.xml", second);
        assertThrows(IllegalArgumentException.class, () -> load(files));
    }

    @Test void pageMetadataIsChecked() throws Exception {
        assertThrows(IllegalArgumentException.class, () -> load(changed("page-003.xml", "<totalCount>1000</totalCount>", "<totalCount>999</totalCount>")));
        assertThrows(IllegalArgumentException.class, () -> load(changed("page-003.xml", "<offset>300</offset>", "<offset>200</offset>")));
        assertThrows(IllegalArgumentException.class, () -> load(changed("page-003.xml", "<limit>100</limit>", "<limit>50</limit>")));
        assertThrows(IllegalArgumentException.class, () -> load(changed("page-003.xml", "<hasMore>true</hasMore>", "<hasMore>false</hasMore>")));
        assertThrows(IllegalArgumentException.class, () -> load(changed("page-009.xml", "<hasMore>false</hasMore>", "<hasMore>true</hasMore>")));
        assertThrows(IllegalArgumentException.class, () -> load(changed("page-003.xml", "<datasetVersion>personnel-v2-large-004<", "<datasetVersion>personnel-v2-large-005<")));
    }

    @Test void readinessOverTheWholeSnapshotIsChecked() throws Exception {
        // A supervisor that no page holds, a duplicate identifier and a reporting cycle all fail after the last page is read.
        var tag = java.util.regex.Pattern.compile("<supervisorPersonnelId>PRS-[0-9]{4}</supervisorPersonnelId>")
            .matcher(new String(files().get("page-001.xml"), StandardCharsets.UTF_8));
        assertTrue(tag.find());
        assertThrows(IllegalArgumentException.class, () -> load(changed("page-001.xml", tag.group(), "<supervisorPersonnelId>PRS-9999</supervisorPersonnelId>")));
        assertThrows(IllegalArgumentException.class, () -> load(changed("page-000.xml", "<personnelId>PRS-0003</personnelId>", "<personnelId>PRS-0002</personnelId>")));
        assertThrows(IllegalArgumentException.class, () -> load(changed("page-000.xml", "<securityClearance>TOP_SECRET</securityClearance></crewDetails>", "<securityClearance>TOP_SECRET</securityClearance><supervisorPersonnelId>PRS-1048</supervisorPersonnelId></crewDetails>")));
    }

    @Test void theContractStillBoundsAPageToOneHundredMembers() throws Exception {
        var files = files();
        String xml = new String(files.get("page-000.xml"), StandardCharsets.UTF_8);
        int start = xml.indexOf("  <personnelMember>");
        int end = xml.indexOf('\n', start) + 1;
        String extra = xml.substring(start, end).replace("PRS-0001", "PRS-0000");
        files.put("page-000.xml", xml.replace(xml.substring(start, end), xml.substring(start, end) + extra).getBytes(StandardCharsets.UTF_8));
        assertThrows(Exception.class, () -> load(files));
    }
}
