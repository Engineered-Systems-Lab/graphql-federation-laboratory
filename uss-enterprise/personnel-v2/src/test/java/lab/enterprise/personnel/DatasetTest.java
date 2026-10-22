package lab.enterprise.personnel;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import lab.enterprise.personnel.contract.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class DatasetTest {
    private String snapshot() throws Exception { return Files.readString(Path.of("datasets/personnel-v2-small-002.xml")); }
    private Dataset parse(String xml) throws Exception { return Dataset.parse(xml.getBytes(StandardCharsets.UTF_8)); }
    private void invalid(String xml) { assertThrows(Exception.class, () -> parse(xml)); }
    @Test void rawIntegrityAndClosedRegistration() throws Exception {
        for (String version : List.of("personnel-v2-small-001", "personnel-v2-small-002", "personnel-v2-small-003")) {
            byte[] raw = Files.readAllBytes(Path.of("datasets/" + version + ".xml"));
            assertEquals(version.endsWith("003") ? 14 : 7, Dataset.load(version, raw).records().size());
            assertThrows(IllegalStateException.class, () -> Dataset.load(version, (new String(raw, StandardCharsets.UTF_8) + " ").getBytes(StandardCharsets.UTF_8)));
            assertThrows(IllegalStateException.class, () -> Dataset.load(version, new String(raw, StandardCharsets.UTF_8).replace("\n", "\r\n").getBytes(StandardCharsets.UTF_8)));
        }
        assertThrows(IllegalArgumentException.class, () -> Dataset.load("crew-v1-small-002"));
        assertThrows(IllegalArgumentException.class, () -> Dataset.load("../other"));
    }
    @Test void thirdSnapshotKeepsTheSevenAndAddsTheMigratedCast() throws Exception {
        var second = Dataset.load("personnel-v2-small-002").records();
        var third = Dataset.load("personnel-v2-small-003").records();
        assertEquals(14, third.size());
        for (var member : second) {
            var same = third.stream().filter(m -> m.getPersonnelId().equals(member.getPersonnelId())).findFirst().orElseThrow();
            assertEquals(member.getDisplayName(), same.getDisplayName());
            assertEquals(member.getPositionTitle(), same.getPositionTitle());
            assertEquals(member.getDutyStatus(), same.getDutyStatus());
            assertEquals(member.getCrewDetails() == null, same.getCrewDetails() == null);
            if (member.getCrewDetails() != null) {
                assertEquals(member.getCrewDetails().getRank(), same.getCrewDetails().getRank());
                assertEquals(member.getCrewDetails().getSecurityClearance(), same.getCrewDetails().getSecurityClearance());
                assertEquals(member.getCrewDetails().getSupervisorPersonnelId(), same.getCrewDetails().getSupervisorPersonnelId());
            }
        }
        // id, name, rank, department, clearance, supervisor: the cast the federation crew mapping refers to.
        String[][] migrated = {
            {"PRS-1048", "William Riker", "COMMANDER", "COMMAND", "SECRET", "PRS-0001"},
            {"PRS-1049", "Geordi La Forge", "LIEUTENANT_COMMANDER", "ENGINEERING", "SECRET", "PRS-1048"},
            {"PRS-1053", "Beverly Crusher", "COMMANDER", "MEDICAL", "SECRET", "PRS-0001"},
            {"PRS-1054", "Deanna Troi", "LIEUTENANT_COMMANDER", "MEDICAL", "SECRET", "PRS-0001"},
            {"PRS-1057", "Reginald Barclay", "LIEUTENANT", "ENGINEERING", "NONE", "PRS-1049"},
            {"PRS-1058", "Worf", "LIEUTENANT", "SECURITY", "SECRET", "PRS-1048"},
            {"PRS-1100", "Miles O'Brien", "CHIEF_PETTY_OFFICER", "OPERATIONS", "NONE", "PRS-1048"}};
        for (String[] row : migrated) {
            var member = third.stream().filter(m -> m.getPersonnelId().equals(row[0])).findFirst().orElseThrow();
            assertEquals(row[1], member.getDisplayName());
            var details = member.getCrewDetails();
            assertEquals(row[2], details.getRank().name());
            assertEquals(row[3], details.getDepartment().name());
            assertEquals(row[4], details.getSecurityClearance().name());
            assertEquals(row[5], details.getSupervisorPersonnelId());
        }
        assertEquals(second.size() + migrated.length, third.size());
    }
    @ParameterizedTest @ValueSource(strings={"PRS-0000", "PRS-00001", "PRS-001", "prs-0001", " PRS-0001", "PRS-0001 ", "CRW-0001", "PRS-１２３４"})
    void invalidIds(String id) throws Exception { invalid(snapshot().replace("PRS-0001", id)); }
    @Test void schemaRequiresExactlyOneBranchAndCrewFields() throws Exception {
        String xml=snapshot();
        for (String replacement : List.of("", "<civilianDetails/><civilianDetails/>", "<civilianDetails><rank>CIVILIAN</rank></civilianDetails>", "<civilianDetails/><crewDetails><rank>ENSIGN</rank><department>OPERATIONS</department><securityClearance>NONE</securityClearance></crewDetails>"))
            invalid(xml.replace("<civilianDetails/>", replacement));
        invalid(xml.replace("<securityClearance>NONE</securityClearance>", ""));
        invalid(xml.replace("<rank>ENSIGN</rank>", "<rank>CIVILIAN</rank>"));
        invalid(xml.replace("<department>OPERATIONS</department>", "<department>CIVILIAN</department>"));
        invalid(xml.replace("<securityClearance>NONE</securityClearance>", "<securityClearance>PUBLIC</securityClearance>"));
        for (String nil : List.of("true","false","1","0"))
            invalid(xml.replace("<civilianDetails/>", "<civilianDetails xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xsi:nil='"+nil+"'/>"));
    }
    @Test void readinessRejectsBadCountsDuplicatesAndReporting() throws Exception {
        String xml=snapshot();
        invalid(xml.replace("<totalCount>7", "<totalCount>6"));
        invalid(xml.replace("<hasMore>false", "<hasMore>true"));
        invalid(xml.replace("<offset>0", "<offset>1"));
        invalid(xml.replace("<personnelId>PRS-0003", "<personnelId>PRS-0002"));
        invalid(xml.replace("<supervisorPersonnelId>PRS-0001", "<supervisorPersonnelId>PRS-9999"));
        invalid(xml.replace("<supervisorPersonnelId>PRS-0001", "<supervisorPersonnelId>PRS-0002"));
        invalid(xml.replace("<securityClearance>TOP_SECRET</securityClearance>", "<securityClearance>TOP_SECRET</securityClearance><supervisorPersonnelId>PRS-0002</supervisorPersonnelId>"));
        invalid(xml.replace("<supervisorPersonnelId>PRS-0001</supervisorPersonnelId>", "<supervisorPersonnelId/>"));
    }
    @Test void reportingCanTargetCivilianAndInactivePersonnelWithoutRankOrdering() throws Exception {
        String xml=snapshot().replace("<supervisorPersonnelId>PRS-0001", "<supervisorPersonnelId>PRS-0003");
        assertEquals(7,parse(xml).records().size());
        xml=xml.replace("<supervisorPersonnelId>PRS-0002", "<supervisorPersonnelId>PRS-0003");
        xml=xml.replace("<supervisorPersonnelId>PRS-0003</supervisorPersonnelId></crewDetails></personnelMember>\n  <personnelMember><personnelId>PRS-0003", "<supervisorPersonnelId>PRS-0005</supervisorPersonnelId></crewDetails></personnelMember>\n  <personnelMember><personnelId>PRS-0003");
        assertEquals(7,parse(xml).records().size());
    }
    @Test void nestedCopiesCannotMutateSnapshot() throws Exception {
        var dataset=Dataset.load(Dataset.DEFAULT_VERSION);
        var result=dataset.records();
        result.get(0).getCrewDetails().setRank(Rank.CREWMAN);
        result.get(0).setPersonnelId("PRS-9999");
        result.get(2).setCrewDetails(new CrewDetails());
        assertEquals(Rank.CAPTAIN,dataset.records().get(0).getCrewDetails().getRank());
        assertEquals("PRS-0001",dataset.records().get(0).getPersonnelId());
        assertNull(dataset.records().get(2).getCrewDetails());
        assertNotNull(dataset.records().get(2).getCivilianDetails());
    }
    @Test void textRulesAndNoStatusTransitionMatrix() throws Exception {
        String xml=snapshot();
        assertEquals(7,parse(xml.replace("Jean-Luc Picard", "🚀".repeat(100))).records().size());
        invalid(xml.replace("Jean-Luc Picard", "🚀".repeat(101)));
        invalid(xml.replace("Jean-Luc Picard", "  "));
        assertEquals(7,parse(xml.replace("<dutyStatus>DECEASED", "<dutyStatus>ACTIVE")).records().size());
        assertEquals(7,parse(xml.replace("PRS-0714", "PRS-9999")).records().size());
    }
    @Test void maliciousXmlRejected() throws Exception {
        invalid(snapshot().replace("<ListPersonnelMembersResponse", "<!DOCTYPE x [<!ENTITY leak SYSTEM 'file:///etc/passwd'>]><ListPersonnelMembersResponse"));
    }
}
