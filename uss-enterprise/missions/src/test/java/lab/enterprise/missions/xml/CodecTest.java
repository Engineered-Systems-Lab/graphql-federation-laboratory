package lab.enterprise.missions.xml;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.xml.bind.JAXBContext;
import javax.xml.bind.JAXBElement;
import org.junit.jupiter.api.Test;

class CodecTest {
    private static <T> T fixture(String name, Class<T> type) throws Exception {
        var unmarshaller = JAXBContext.newInstance("lab.enterprise.missions.xml").createUnmarshaller();
        JAXBElement<T> element = unmarshaller.unmarshal(new javax.xml.transform.stream.StreamSource(Path.of("fixtures", "valid", name).toFile()), type);
        return element.getValue();
    }

    private static String text(byte[] bytes) { return new String(bytes, StandardCharsets.UTF_8); }

    @Test void missionUsesTheDefaultNamespaceAndKeepsContractOrder() throws Exception {
        String xml = text(Codec.mission(fixture("mission-response.xml", Mission.class)));
        assertTrue(xml.contains("<mission xmlns=\"urn:starfleet:missions:v1\">"), xml);
        int previous = -1;
        for (String element : new String[] {"missionId", "title", "type", "classification", "status", "priority", "stardate",
                "durationHours", "objective", "location", "issuingAuthority", "commandingOfficerId", "assignedCrewIds",
                "participantIds", "assignedAssetIds", "estimatedCostCredits", "actualCostCredits", "outcome", "lastUpdated"}) {
            int at = xml.indexOf("<" + element + ">");
            assertTrue(at > previous, element + " out of order in " + xml);
            previous = at;
        }
        assertTrue(xml.contains("<crewId>C-10</crewId><crewId>C-2</crewId>"), xml);
    }

    @Test void emptyContainersStillOccurExactlyOnce() throws Exception {
        Mission mission = fixture("mission-response.xml", Mission.class);
        mission.getAssignedCrewIds().getCrewId().clear();
        mission.getParticipantIds().getParticipantId().clear();
        mission.getAssignedAssetIds().getAssetId().clear();
        String xml = text(Codec.mission(mission));
        assertTrue(xml.contains("<assignedCrewIds/>") && xml.contains("<participantIds/>") && xml.contains("<assignedAssetIds/>"), xml);
    }

    @Test void emptyListHasOnlyMetadata() throws Exception {
        String xml = text(Codec.missionList(fixture("mission-list-empty.xml", MissionList.class)));
        assertTrue(xml.contains("<page>1</page><pageSize>20</pageSize><totalCount>0</totalCount><totalPages>0</totalPages></missionList>"), xml);
    }

    @Test void changeListRoundTripsThroughTheSchema() throws Exception {
        String xml = text(Codec.changeList(fixture("change-list.xml", ChangeList.class)));
        assertTrue(xml.contains("<changeId>16</changeId>"), xml);
    }

    @Test void errorBodyIsNamespacedAndBounded() {
        String xml = text(Codec.error("MISSION_NOT_FOUND", "No mission"));
        assertTrue(xml.contains("<code>MISSION_NOT_FOUND</code><message>No mission</message>"), xml);
        String longMessage = "🚀".repeat(1500);
        String bounded = text(Codec.error("INTERNAL_ERROR", longMessage));
        assertEquals(1000, bounded.substring(bounded.indexOf("<message>") + 9, bounded.indexOf("</message>")).codePointCount(0,
                bounded.indexOf("</message>") - bounded.indexOf("<message>") - 9));
    }

    @Test void markupInTextIsEscaped() {
        String xml = text(Codec.error("INVALID_REQUEST", "a<b&c"));
        assertTrue(xml.contains("<message>a&lt;b&amp;c</message>"), xml);
    }
}
