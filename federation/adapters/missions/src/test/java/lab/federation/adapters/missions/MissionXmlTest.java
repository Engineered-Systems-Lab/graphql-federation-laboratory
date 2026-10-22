package lab.federation.adapters.missions;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import lab.federation.common.HttpResult;
import org.junit.jupiter.api.Test;

/** The XML reading: the contract's own fixtures and the released dataset, then every way a body can be wrong or hostile. */
class MissionXmlTest {
    private static final String NS = StubMissions.NS;

    // ---- the contract's fixtures and the released dataset -----------------------------------------------------------

    @Test
    void theResponseFixtureReadsWithEveryFieldAndTheCostsAsTheirExactText() {
        Map<String, Object> mission = MissionXml.mission(StubMissions.fixture("valid/mission-response.xml"));
        assertThat(mission).containsEntry("missionId", "ST-0000000A1").containsEntry("type", "EXPLORATION").containsEntry("classification", "SECRET")
                .containsEntry("status", "COMPLETED").containsEntry("priority", 3).containsEntry("stardate", "43125.80")
                .containsEntry("durationHours", 72).containsEntry("issuingAuthority", "STARFLEET_COMMAND").containsEntry("commandingOfficerId", "C-2")
                .containsEntry("assignedCrewIds", List.of("C-10", "C-2")).containsEntry("participantIds", List.of("O-7", "P-3"))
                .containsEntry("assignedAssetIds", List.of("SH-17")).containsEntry("estimatedCostCredits", "140000.00")
                .containsEntry("actualCostCredits", "155000.00").containsEntry("outcome", "Illustrative outcome text.")
                .containsEntry("lastUpdated", "2366-10-14T19:42:31.472Z");
        assertThat(mission.get("location")).isEqualTo(Map.of("type", "SECTOR", "name", "Example sector", "coordinates", "opaque-coordinates",
                "travelVector", "opaque-vector"));
    }

    @Test
    void theMaintenanceFixtureOfContract11ReadsAsAMissionType() {
        assertThat(MissionXml.mission(StubMissions.fixture("v1.1/maintenance-response.xml"))).containsEntry("type", "MAINTENANCE");
    }

    @Test
    void theListFixturesReadWithOptionalElementsAbsentAndEmptyCollections() {
        MissionXml.Page page = MissionXml.page(StubMissions.fixture("valid/mission-list.xml"));
        assertThat(page.page()).isEqualTo(1);
        assertThat(page.pageSize()).isEqualTo(20);
        assertThat(page.totalCount()).isEqualTo(1);
        assertThat(page.totalPages()).isEqualTo(1);
        Map<String, Object> mission = page.missions().get(0);
        assertThat(mission).containsEntry("commandingOfficerId", null).containsEntry("estimatedCostCredits", null).containsEntry("actualCostCredits", null)
                .containsEntry("outcome", null).containsEntry("assignedCrewIds", List.of()).containsEntry("assignedAssetIds", List.of());
        assertThat(((Map<?, ?>) mission.get("location")).get("coordinates")).isNull();
        MissionXml.Page empty = MissionXml.page(StubMissions.fixture("valid/mission-list-empty.xml"));
        assertThat(empty.missions()).isEmpty();
        assertThat(empty.totalPages()).isZero();
    }

    @Test
    void aReleasedPageReadsAs50MissionsOfTheListOf300AndAnEmptyElementWithASpaceIsAnEmptyCollection() {
        MissionXml.Page page = MissionXml.page(StubMissions.releasePage(1));
        assertThat(page.missions()).hasSize(50);
        assertThat(page.pageSize()).isEqualTo(50);
        assertThat(page.totalCount()).isEqualTo(300);
        assertThat(page.missions()).anyMatch(mission -> ((List<?>) mission.get("assignedCrewIds")).isEmpty());
    }

    @Test
    void theErrorFixtureAndNonErrorsGiveTheCodeOrNull() {
        assertThat(MissionXml.errorCode(HttpResult.answer(422, StubMissions.fixture("valid/error.xml")))).isEqualTo("DOMAIN_VALIDATION_FAILED");
        assertThat(MissionXml.errorCode(HttpResult.answer(404, ""))).isNull();
        assertThat(MissionXml.errorCode(HttpResult.answer(404, null))).isNull();
        assertThat(MissionXml.errorCode(HttpResult.answer(404, "<html>no</html>"))).isNull();
        assertThat(MissionXml.errorCode(HttpResult.answer(404, "{\"code\":\"MISSION_NOT_FOUND\"}"))).isNull();
        assertThat(MissionXml.errorCode(HttpResult.failed(new IOException("down")))).isNull();
        assertThat(MissionXml.errorCode(HttpResult.answer(404, "<error xmlns=\"other\"><code>MISSION_NOT_FOUND</code></error>"))).isNull();
    }

    // ---- bodies that do not read as the contract says ---------------------------------------------------------------

    private static String mission(String replacement, String original) {
        return StubMissions.fixture("valid/mission-response.xml").replace(original, replacement);
    }

    @Test
    void aBodyThatIsNotTheContractIsRefused() {
        List<String> bad = List.of(
                mission("<status>UNKNOWN</status>", "<status>COMPLETED</status>"),
                mission("<type>MAINTENANCE_X</type>", "<type>EXPLORATION</type>"),
                mission("<priority>0</priority>", "<priority>3</priority>"),
                mission("<priority>03</priority>", "<priority>3</priority>"),
                mission("<priority>x</priority>", "<priority>3</priority>"),
                mission("<durationHours>8761</durationHours>", "<durationHours>72</durationHours>"),
                mission("", "<lastUpdated>2366-10-14T19:42:31.472Z</lastUpdated>"),
                mission("", "<missionId>ST-0000000A1</missionId>"),
                StubMissions.fixture("valid/mission-response.xml").replaceAll("(?s)<assignedAssetIds>.*?</assignedAssetIds>", ""),
                mission("</assignedAssetIds><assignedAssetIds><assetId>SH-18</assetId></assignedAssetIds>", "</assignedAssetIds>"),
                mission("<crewId></crewId>", "<crewId>C-10</crewId>"),
                mission("<mission xmlns=\"urn:other\">", "<mission xmlns=\"" + NS + "\">"),
                mission("<missionList xmlns=\"" + NS + "\">", "<mission xmlns=\"" + NS + "\">").replace("</mission>", "</missionList>"),
                "", "not xml", "<mission xmlns=\"" + NS + "\"><title>x</title>");
        for (String body : bad) {
            assertThatThrownBy(() -> MissionXml.mission(body)).as(body).isInstanceOf(IllegalArgumentException.class);
        }
        assertThatThrownBy(() -> MissionXml.mission(null)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void aListThatIsNotTheContractIsRefused() {
        String list = StubMissions.fixture("valid/mission-list.xml");
        for (String body : List.of(
                list.replace("<pageSize>20</pageSize>", "<pageSize>51</pageSize>"),
                list.replace("<page>1</page>", "<page>0</page>"),
                list.replace("<totalCount>1</totalCount>", "<totalCount>-1</totalCount>"),
                list.replaceAll("(?s)<page>1</page>\\s*<pageSize>20</pageSize>", "<pageSize>20</pageSize><page>1</page>"),
                list.replace("<mission>", "<change>").replace("</mission>", "</change>"),
                StubMissions.fixture("valid/mission-response.xml"))) {
            assertThatThrownBy(() -> MissionXml.page(body)).as(body).isInstanceOf(IllegalArgumentException.class);
        }
    }

    // ---- hostile bodies ---------------------------------------------------------------------------------------------

    /** Counts requests made by anything that would follow an external entity or an include. */
    private static final class Tripwire implements AutoCloseable {
        final AtomicInteger hits = new AtomicInteger();
        final HttpServer server;

        Tripwire() throws IOException {
            server = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
            server.createContext("/", exchange -> {
                hits.incrementAndGet();
                byte[] bytes = "<!ENTITY more \"x\">".getBytes();
                exchange.sendResponseHeaders(200, bytes.length);
                exchange.getResponseBody().write(bytes);
                exchange.close();
            });
            server.start();
        }

        String url() {
            return "http://127.0.0.1:" + server.getAddress().getPort() + "/leak";
        }

        @Override
        public void close() {
            server.stop(0);
        }
    }

    @Test
    void aDoctypeIsRefusedWhateverItDeclaresAndNothingIsFetched() throws IOException {
        try (Tripwire tripwire = new Tripwire()) {
            String mission = StubMissions.fixture("valid/mission-response.xml");
            String body = mission.substring(mission.indexOf("<mission"));
            List<String> hostile = List.of(
                    "<!DOCTYPE mission [<!ENTITY secret SYSTEM \"" + tripwire.url() + "\">]>" + body.replace("Example sector", "&secret;"),
                    "<!DOCTYPE mission [<!ENTITY % p SYSTEM \"" + tripwire.url() + "\"> %p;]>" + body,
                    "<!DOCTYPE mission SYSTEM \"" + tripwire.url() + "\">" + body,
                    "<!DOCTYPE mission [<!ENTITY a \"aaaaaaaaaa\"><!ENTITY b \"&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;\">]>" + body.replace("Example sector", "&b;"),
                    "<!DOCTYPE mission []>" + body);
            for (String xml : hostile) {
                assertThatThrownBy(() -> MissionXml.mission(xml)).as(xml).isInstanceOf(IllegalArgumentException.class);
                assertThat(MissionXml.errorCode(HttpResult.answer(404, xml))).isNull();
                assertThatThrownBy(() -> MissionXml.page(xml)).isInstanceOf(IllegalArgumentException.class);
            }
            String include = body.replace("<title>", "<xi:include xmlns:xi=\"http://www.w3.org/2001/XInclude\" href=\"" + tripwire.url() + "\"/><title>");
            assertThatThrownBy(() -> MissionXml.mission(include)).isInstanceOf(IllegalArgumentException.class);
            assertThat(tripwire.hits.get()).as("no external entity, DTD or include was fetched").isZero();
        }
    }

    @Test
    void characterReferencesAndUnicodeReadAsText() {
        String body = mission("<title>Caf&#233; \uD83D\uDE80 &amp; co</title>", "<title>Contract example: survey of a border sector</title>");
        assertThat(MissionXml.mission(body)).containsEntry("title", "Caf\u00E9 \uD83D\uDE80 & co");
    }
}
