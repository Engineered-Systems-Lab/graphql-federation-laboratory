package lab.federation.adapters.personnel;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

/** The XML reading: the registered snapshots, then every way a body can be wrong or hostile. */
@SuppressWarnings("unchecked")
class PersonnelXmlTest {
    private static final String NS = StubPersonnel.NS;

    /** The payload inside a SOAP envelope, with no XML declaration (so that a test can put a DOCTYPE first). */
    private static String wrap(String payload) {
        return "<soap:Envelope xmlns:soap=\"" + StubPersonnel.SOAP + "\"><soap:Body>" + payload + "</soap:Body></soap:Envelope>";
    }

    /** A snapshot file as the body of a list answer. */
    private static String list(String snapshot) {
        return wrap(StubPersonnel.snapshot(snapshot).replaceFirst("^<\\?xml[^>]*\\?>\\s*", ""));
    }

    private static String block(String snapshot, String id) {
        return StubPersonnel.blocks(StubPersonnel.snapshot(snapshot)).stream().filter(b -> id.equals(StubPersonnel.field(b, "personnelId")))
                .findFirst().orElseThrow();
    }

    private static String get(String snapshot, String id) {
        return wrap("<GetPersonnelMemberResponse xmlns=\"" + NS + "\"><datasetVersion>" + snapshot + "</datasetVersion>" + block(snapshot, id)
                + "</GetPersonnelMemberResponse>");
    }

    private static final String DATA = get(StubPersonnel.SMALL_002, "PRS-0002");
    private static final String GUINAN = get(StubPersonnel.SMALL_002, "PRS-0003");

    // ---- the registered snapshots ----------------------------------------------------------------------------------

    @Test
    void bothSnapshotsReadWithEveryMemberAsTheServiceSentIt() {
        for (String name : List.of(StubPersonnel.SMALL_001, StubPersonnel.SMALL_002)) {
            PersonnelXml.Page page = PersonnelXml.page(list(name));
            assertThat(page.datasetVersion()).isEqualTo(name);
            assertThat(page.totalCount()).isEqualTo(7);
            assertThat(page.offset()).isZero();
            assertThat(page.limit()).isEqualTo(20);
            assertThat(page.hasMore()).isFalse();
            List<String> blocks = StubPersonnel.blocks(StubPersonnel.snapshot(name));
            assertThat(page.members()).hasSize(blocks.size());
            for (int index = 0; index < blocks.size(); index++) {
                String block = blocks.get(index);
                Map<String, Object> member = page.members().get(index);
                assertThat(member).containsEntry("personnelId", StubPersonnel.field(block, "personnelId"))
                        .containsEntry("displayName", StubPersonnel.field(block, "displayName"))
                        .containsEntry("positionTitle", StubPersonnel.field(block, "positionTitle"))
                        .containsEntry("dutyStatus", StubPersonnel.field(block, "dutyStatus"));
                Map<String, Object> details = (Map<String, Object>) member.get("details");
                if (block.contains("<civilianDetails/>")) {
                    assertThat(details).isEmpty();
                } else {
                    assertThat(details).containsEntry("rank", StubPersonnel.field(block, "rank"))
                            .containsEntry("department", StubPersonnel.field(block, "department"))
                            .containsEntry("securityClearance", StubPersonnel.field(block, "securityClearance"))
                            .containsEntry("supervisorPersonnelId", StubPersonnel.field(block, "supervisorPersonnelId"));
                }
            }
        }
    }

    @Test
    void theWesleyCaseIsACivilianInOneSnapshotAndCrewInTheOther() {
        Map<String, Object> civilian = PersonnelXml.single(get(StubPersonnel.SMALL_001, "PRS-0714")).member();
        assertThat(civilian).containsEntry("displayName", "Wesley Crusher").containsEntry("positionTitle", "Student");
        assertThat((Map<String, Object>) civilian.get("details")).isEmpty();
        PersonnelXml.Single crew = PersonnelXml.single(get(StubPersonnel.SMALL_002, "PRS-0714"));
        assertThat(crew.datasetVersion()).isEqualTo(StubPersonnel.SMALL_002);
        assertThat(crew.member()).containsEntry("personnelId", "PRS-0714").containsEntry("positionTitle", "Acting Ensign");
        assertThat((Map<String, Object>) crew.member().get("details")).containsEntry("rank", "ENSIGN").containsEntry("department", "OPERATIONS")
                .containsEntry("securityClearance", "NONE").containsEntry("supervisorPersonnelId", "PRS-0002");
    }

    @Test
    void aMemberWithNoSupervisorHasANullOne() {
        PersonnelXml.Single picard = PersonnelXml.single(get(StubPersonnel.SMALL_002, "PRS-0001"));
        assertThat((Map<String, Object>) picard.member().get("details")).containsEntry("rank", "CAPTAIN").containsEntry("supervisorPersonnelId", null);
    }

    // ---- a body that does not read as the contract -----------------------------------------------------------------

    private static void rejected(String body) {
        assertThatThrownBy(() -> PersonnelXml.single(body)).as(body).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void aBodyThatIsNotTheContractIsRefused() {
        assertThat(PersonnelXml.single(DATA).member()).containsEntry("displayName", "Data");
        rejected(DATA.replace("xmlns=\"" + NS + "\"", "xmlns=\"urn:other\""));
        rejected(DATA.replace("GetPersonnelMemberResponse", "ListPersonnelMembersResponse"));
        rejected(DATA.replace("<personnelId>PRS-0002", "<personnelId>PRS-0000"));
        rejected(DATA.replace("<personnelId>PRS-0002", "<personnelId>prs-0002"));
        rejected(DATA.replace("<personnelId>PRS-0002", "<personnelId>PRS-00021"));
        rejected(DATA.replace("<dutyStatus>ACTIVE", "<dutyStatus>RETIRED"));
        rejected(DATA.replace("<rank>LIEUTENANT_COMMANDER", "<rank>ADMIRAL"));
        rejected(DATA.replace("<department>OPERATIONS", "<department>operations"));
        rejected(DATA.replace("<securityClearance>SECRET", "<securityClearance>COSMIC"));
        rejected(DATA.replace("<supervisorPersonnelId>PRS-0001", "<supervisorPersonnelId>PRS-0000"));
        rejected(DATA.replace("</crewDetails>", "</crewDetails><civilianDetails/>"));
        rejected(DATA.replaceAll("<crewDetails>.*</crewDetails>", ""));
        rejected(DATA.replace("<rank>LIEUTENANT_COMMANDER</rank><department>OPERATIONS</department>",
                "<department>OPERATIONS</department><rank>LIEUTENANT_COMMANDER</rank>"));
        rejected(DATA.replace("<displayName>Data</displayName><positionTitle>Operations Officer</positionTitle>",
                "<positionTitle>Operations Officer</positionTitle><displayName>Data</displayName>"));
        rejected(DATA.replace("<displayName>", "<displayName xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:nil=\"false\">"));
        rejected(DATA.replace("<displayName>Data", "<displayName>"));
        rejected(DATA.replace("<displayName>Data", "<displayName>   "));
        rejected(DATA.replace("</crewDetails>", "<extra/></crewDetails>"));
        rejected(DATA.replace("</personnelMember>", "<extra/></personnelMember>"));
        rejected(DATA.replace("<datasetVersion>personnel-v2-small-002</datasetVersion>", ""));
        rejected(DATA.replace("personnel-v2-small-002", "Personnel_V2"));
        rejected(DATA.replace("personnel-v2-small-002", "x".repeat(65)));
        rejected(GUINAN.replace("<civilianDetails/>", "<civilianDetails><rank>ENSIGN</rank></civilianDetails>"));
        rejected(GUINAN.replace("<civilianDetails/>", "<civilianDetails>text</civilianDetails>"));
        rejected(GUINAN.replace("<civilianDetails/>", "<civilianDetails attribute=\"x\"/>"));
        rejected(DATA.replace("</GetPersonnelMemberResponse>", "</GetPersonnelMemberResponse><Other/>"));
        rejected("");
        rejected("not xml");
        rejected("<soap:Envelope xmlns:soap=\"urn:other\"><soap:Body/></soap:Envelope>");
        rejected("<soap:Envelope xmlns:soap=\"" + StubPersonnel.SOAP + "\"/>");
        rejected("<soap:Envelope xmlns:soap=\"" + StubPersonnel.SOAP + "\"><soap:Body/></soap:Envelope>");
        rejected(wrap("<a xmlns=\"" + NS + "\"/><b xmlns=\"" + NS + "\"/>"));
        assertThatThrownBy(() -> PersonnelXml.single(null)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void aNameIsOneToOneHundredCharactersCountedAsCodePointsAndKeptExactly() {
        String hundred = "Q".repeat(100);
        assertThat(PersonnelXml.single(DATA.replace("<displayName>Data", "<displayName>" + hundred)).member()).containsEntry("displayName", hundred + "");
        rejected(DATA.replace("<displayName>Data", "<displayName>" + "Q".repeat(101)));
        // 100 supplementary characters are 200 UTF-16 units and still 100 characters of the contract.
        String emoji = "🚀".repeat(100);
        assertThat(PersonnelXml.single(DATA.replace("<displayName>Data", "<displayName>" + emoji)).member()).containsEntry("displayName", emoji + "");
        rejected(DATA.replace("<displayName>Data", "<displayName>" + "🚀".repeat(101)));
        // The whitespace around the text is part of the value.
        assertThat(PersonnelXml.single(DATA.replace("<displayName>Data", "<displayName> Data ")).member().get("displayName")).isEqualTo(" Data ");
    }

    // ---- a list that contradicts itself ----------------------------------------------------------------------------

    @Test
    void aPageThatContradictsItselfIsRefused() {
        String good = list(StubPersonnel.SMALL_002);
        assertThat(PersonnelXml.page(good).members()).hasSize(7);
        for (String bad : List.of(
                good.replace("<hasMore>false</hasMore>", "<hasMore>true</hasMore>"),
                good.replace("<totalCount>7</totalCount>", "<totalCount>9</totalCount>"),
                good.replace("<totalCount>7</totalCount>", "<totalCount>07</totalCount>"),
                good.replace("<limit>20</limit>", "<limit>101</limit>"),
                good.replace("<limit>20</limit>", "<limit>0</limit>"),
                good.replace("<limit>20</limit>", "<limit>5</limit>"),
                good.replace("<offset>0</offset>", "<offset>-1</offset>"),
                good.replace("<hasMore>false</hasMore>", "<hasMore>1</hasMore>"),
                good.replace("<hasMore>false</hasMore>", ""),
                good.replace("<datasetVersion>personnel-v2-small-002</datasetVersion>", ""),
                good.replace("PRS-0003", "PRS-0001"),
                good.replace("<totalCount>7</totalCount>", "<totalCount>x</totalCount>"))) {
            assertThatThrownBy(() -> PersonnelXml.page(bad)).as(bad).isInstanceOf(IllegalArgumentException.class);
        }
        StringBuilder many = new StringBuilder();
        for (int index = 1; index <= 101; index++) {
            many.append(block(StubPersonnel.SMALL_002, "PRS-0001").replace("PRS-0001", String.format("PRS-%04d", index)));
        }
        String over = wrap("<ListPersonnelMembersResponse xmlns=\"" + NS + "\"><datasetVersion>personnel-v2-small-002</datasetVersion>" + many
                + "<totalCount>101</totalCount><offset>0</offset><limit>100</limit><hasMore>true</hasMore></ListPersonnelMembersResponse>");
        assertThatThrownBy(() -> PersonnelXml.page(over)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void anEmptyPagePastTheEndReads() {
        String empty = wrap("<ListPersonnelMembersResponse xmlns=\"" + NS + "\"><datasetVersion>personnel-v2-small-002</datasetVersion>"
                + "<totalCount>7</totalCount><offset>9</offset><limit>20</limit><hasMore>false</hasMore></ListPersonnelMembersResponse>");
        PersonnelXml.Page page = PersonnelXml.page(empty);
        assertThat(page.members()).isEmpty();
        assertThat(page.offset()).isEqualTo(9);
        assertThat(page.hasMore()).isFalse();
    }

    // ---- the fault -------------------------------------------------------------------------------------------------

    @Test
    void aDeclaredFaultReadsWithItsCodeAndField() {
        assertThat(PersonnelXml.fault(StubPersonnel.fault("PersonnelNotFound", "personnelId"))).isEqualTo(new PersonnelXml.Fault("PersonnelNotFound", "personnelId"));
        assertThat(PersonnelXml.fault(StubPersonnel.fault("InvalidRequest", null))).isEqualTo(new PersonnelXml.Fault("InvalidRequest", null));
        assertThat(PersonnelXml.fault(StubPersonnel.fault("ServiceUnavailable", null))).isEqualTo(new PersonnelXml.Fault("ServiceUnavailable", null));
        assertThat(PersonnelXml.fault(StubPersonnel.fault("InternalError", null))).isEqualTo(new PersonnelXml.Fault("InternalError", null));
    }

    @Test
    void aFaultWithoutTheContractsDetailHasNoCodeAndAnythingElseIsNotAFault() {
        String plain = wrap("<soap:Fault><faultcode>soap:Server</faultcode><faultstring>boom</faultstring></soap:Fault>");
        assertThat(PersonnelXml.fault(plain)).isEqualTo(new PersonnelXml.Fault(null, null));
        assertThat(PersonnelXml.fault(DATA)).isNull();
        assertThat(PersonnelXml.fault("not xml")).isNull();
        assertThat(PersonnelXml.fault("")).isNull();
        assertThat(PersonnelXml.fault(null)).isNull();
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
    void aDoctypeIsRefusedAndNothingOutsideTheDocumentIsFetched() throws IOException {
        try (Tripwire tripwire = new Tripwire()) {
            String body = DATA;
            List<String> hostile = List.of(
                    "<!DOCTYPE soap:Envelope [<!ENTITY secret SYSTEM \"" + tripwire.url() + "\">]>" + body.replace("Operations Officer", "&secret;"),
                    "<!DOCTYPE soap:Envelope [<!ENTITY % p SYSTEM \"" + tripwire.url() + "\"> %p;]>" + body,
                    "<!DOCTYPE soap:Envelope SYSTEM \"" + tripwire.url() + "\">" + body,
                    "<!DOCTYPE soap:Envelope [<!ENTITY a \"aaaaaaaaaa\"><!ENTITY b \"&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;\">]>" + body.replace("Operations Officer", "&b;"),
                    "<!DOCTYPE soap:Envelope []>" + body);
            for (String xml : hostile) {
                assertThatThrownBy(() -> PersonnelXml.single(xml)).as(xml).isInstanceOf(IllegalArgumentException.class);
                assertThatThrownBy(() -> PersonnelXml.page(xml)).isInstanceOf(IllegalArgumentException.class);
                assertThat(PersonnelXml.fault(xml)).isNull();
            }
            String include = body.replace("<displayName>", "<xi:include xmlns:xi=\"http://www.w3.org/2001/XInclude\" href=\"" + tripwire.url() + "\"/><displayName>");
            assertThatThrownBy(() -> PersonnelXml.single(include)).isInstanceOf(IllegalArgumentException.class);
            assertThat(tripwire.hits.get()).as("no external entity, DTD or include was fetched").isZero();
        }
    }
}
