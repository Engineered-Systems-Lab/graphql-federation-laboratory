package lab.enterprise.personnel;

import static org.junit.jupiter.api.Assertions.*;
import java.net.*;
import java.net.http.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import org.apache.cxf.Bus;
import org.apache.cxf.BusFactory;
import org.apache.cxf.endpoint.Server;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.w3c.dom.*;

/** Real HTTP on loopback; schema-check every success and declared fault detail. */
class SoapHttpTest {
    private Bus bus;
    private Server server;
    private String address;
    private final HttpClient client = HttpClient.newHttpClient();
    @BeforeEach void start() throws Exception { start("personnel-v2-small-001", PersonnelService.Profile.normal, null); }
    @AfterEach void stop() { if (server != null) server.destroy(); if (bus != null) bus.shutdown(true); }
    private void start(String version, PersonnelService.Profile profile, PersonnelService.Delay delay) throws Exception {
        int port;
        try (var socket = new java.net.ServerSocket(0, 0, InetAddress.getLoopbackAddress())) { port = socket.getLocalPort(); }
        address = "http://127.0.0.1:" + port + "/soap/personnel-v2";
        bus = BusFactory.newInstance().createBus();
        var dataset = Dataset.load(version);
        server = Main.publish(bus, address, delay == null ? new PersonnelService(dataset, profile) : new PersonnelService(dataset, profile, delay));
    }
    private void restart(String version, PersonnelService.Profile profile) throws Exception { stop(); start(version, profile, null); }
    private String wrapper(String name, String children) { return "<" + name + " xmlns='" + Xml.NS + "'>" + children + "</" + name + ">"; }
    private String envelope(String payload) { return "<s:Envelope xmlns:s='" + Xml.SOAP + "'><s:Body>" + payload + "</s:Body></s:Envelope>"; }
    private HttpResponse<byte[]> send(String xml, Duration timeout) throws Exception {
        return client.send(HttpRequest.newBuilder(URI.create(address)).timeout(timeout)
            .header("Content-Type", "text/xml; charset=utf-8")
            .header("SOAPAction", "\"" + Xml.NS + (xml.contains("GetPersonnelMemberRequest") ? ":GetPersonnelMember" : ":ListPersonnelMembers") + "\"").POST(HttpRequest.BodyPublishers.ofString(xml)).build(), HttpResponse.BodyHandlers.ofByteArray());
    }
    private Element call(String payload, int status) throws Exception {
        var response = send(envelope(payload), Duration.ofSeconds(10)); assertEquals(status, response.statusCode());
        var document = Xml.parse(response.body());
        var body = document.getElementsByTagNameNS(Xml.SOAP, "Body").item(0);
        var elements = new ArrayList<Element>();
        for (Node n = body.getFirstChild(); n != null; n = n.getNextSibling()) if (n instanceof Element e) elements.add(e);
        assertEquals(1, elements.size()); var result = elements.get(0);
        if (status == 200) {
            Xml.validate(result);
            assertTrue(result.getElementsByTagNameNS(Xml.NS, "personnelMember").getLength() <= 100);
        }
        else {
            assertEquals("Fault", result.getLocalName()); assertEquals(Xml.SOAP, result.getNamespaceURI());
            var details = result.getElementsByTagNameNS(Xml.NS, "PersonnelServiceFault"); assertEquals(1, details.getLength());
            Xml.validate((Element) details.item(0));
        }
        return result;
    }
    private static String semantic(Element root) {
        var result = new StringBuilder("{" + root.getNamespaceURI() + "}" + root.getLocalName() + "[");
        boolean hasElements = false;
        for (Node n = root.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element child) { hasElements = true; result.append(semantic(child)); }
        }
        if (!hasElements) result.append(root.getTextContent());
        return result.append("]").toString();
    }
    private static String text(Element root, String name) { return root.getElementsByTagNameNS(Xml.NS, name).item(0).getTextContent(); }
    private void fault(String payload, String code, String field) throws Exception {
        var result = call(payload, 500); assertEquals(code, text(result, "code"));
        var fields = result.getElementsByTagNameNS(Xml.NS, "field");
        if (field == null) assertEquals(0, fields.getLength()); else { assertEquals(1, fields.getLength()); assertEquals(field, fields.item(0).getTextContent()); }
        var faultcode = (Element) result.getElementsByTagName("faultcode").item(0);
        String[] qname = faultcode.getTextContent().split(":", 2);
        assertEquals(Xml.SOAP, faultcode.lookupNamespaceURI(qname.length == 2 ? qname[0] : null));
        assertEquals(Set.of("InvalidRequest", "PersonnelNotFound").contains(code) ? "Client" : "Server", qname[qname.length - 1]);
    }
    @Test void getIncludesInactiveAndOmitsAbsentSupervisor() throws Exception {
        var picard = call(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-0001</personnelId>"), 200);
        assertEquals("Jean-Luc Picard", text(picard, "displayName")); assertEquals(0, picard.getElementsByTagNameNS(Xml.NS, "supervisorPersonnelId").getLength());
        var inactive = call(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-0005</personnelId>"), 200);
        assertEquals("INACTIVE", text(inactive, "dutyStatus")); assertEquals("PRS-0002", text(inactive, "supervisorPersonnelId"));
        fault(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-9999</personnelId>"), "PersonnelNotFound", "personnelId");
    }
    @Test void listDefaultsFiltersAndPagination() throws Exception {
        var all = call(wrapper("ListPersonnelMembersRequest", ""), 200);
        assertEquals(semantic(Xml.parse(Files.readAllBytes(Path.of("datasets/personnel-v2-small-001.xml"))).getDocumentElement()), semantic(all));
        assertEquals("7", text(all, "totalCount")); assertEquals("20", text(all, "limit")); assertEquals("0", text(all, "offset"));
        assertEquals(7, all.getElementsByTagNameNS(Xml.NS, "personnelMember").getLength()); assertEquals("false", text(all, "hasMore"));
        var page = call(wrapper("ListPersonnelMembersRequest", "<offset> +02 </offset><limit>002</limit>"), 200);
        assertEquals("PRS-0003", text(page, "personnelId")); assertEquals("true", text(page, "hasMore")); assertEquals("2", text(page, "offset"));
        for (int offset : new int[]{7, 8, Integer.MAX_VALUE}) {
            var beyond = call(wrapper("ListPersonnelMembersRequest", "<offset>" + offset + "</offset>"), 200);
            assertEquals(0, beyond.getElementsByTagNameNS(Xml.NS, "personnelMember").getLength()); assertEquals("false", text(beyond, "hasMore"));
        }
        var filtered = call(wrapper("ListPersonnelMembersRequest", "<department>OPERATIONS</department><dutyStatus>ACTIVE</dutyStatus>"), 200);
        assertEquals("1", text(filtered, "totalCount")); assertEquals("PRS-0002", text(filtered, "personnelId"));
        var leave = call(wrapper("ListPersonnelMembersRequest", "<dutyStatus>ON_LEAVE</dutyStatus>"), 200); assertEquals("PRS-0004", text(leave, "personnelId"));
        var empty = call(wrapper("ListPersonnelMembersRequest", "<department>MEDICAL</department>"), 200); assertEquals("0", text(empty, "totalCount"));
        for (int limit : new int[]{1, 100}) assertEquals(Integer.toString(limit), text(call(wrapper("ListPersonnelMembersRequest", "<limit>" + limit + "</limit>"), 200), "limit"));
    }
    @Test void largeSnapshotPagesAcrossTenResponses() throws Exception {
        restart("personnel-v2-large-004", PersonnelService.Profile.normal);
        var everyone = new ArrayList<String>();
        for (int offset = 0; offset < 1000; offset += 100) {
            var page = call(wrapper("ListPersonnelMembersRequest", "<offset>" + offset + "</offset><limit>100</limit>"), 200);
            assertEquals("personnel-v2-large-004", text(page, "datasetVersion"));
            assertEquals("1000", text(page, "totalCount")); assertEquals(Integer.toString(offset), text(page, "offset"));
            assertEquals(offset < 900 ? "true" : "false", text(page, "hasMore"));
            var ids = page.getElementsByTagNameNS(Xml.NS, "personnelId");
            assertEquals(100, ids.getLength());
            for (int i = 0; i < ids.getLength(); i++) everyone.add(ids.item(i).getTextContent());
        }
        assertEquals(1000, new HashSet<>(everyone).size());
        assertEquals(everyone.stream().sorted().toList(), everyone);
        assertEquals("PRS-0001", everyone.get(0)); assertEquals("PRS-3199", everyone.get(999));
        var defaults = call(wrapper("ListPersonnelMembersRequest", ""), 200);
        assertEquals(20, defaults.getElementsByTagNameNS(Xml.NS, "personnelMember").getLength());
        assertEquals("20", text(defaults, "limit")); assertEquals("true", text(defaults, "hasMore"));
        var tail = call(wrapper("ListPersonnelMembersRequest", "<offset>995</offset>"), 200);
        assertEquals(5, tail.getElementsByTagNameNS(Xml.NS, "personnelMember").getLength()); assertEquals("false", text(tail, "hasMore"));
        for (int offset : new int[]{1000, 1001, Integer.MAX_VALUE}) {
            var beyond = call(wrapper("ListPersonnelMembersRequest", "<offset>" + offset + "</offset>"), 200);
            assertEquals(0, beyond.getElementsByTagNameNS(Xml.NS, "personnelMember").getLength());
            assertEquals("1000", text(beyond, "totalCount")); assertEquals("false", text(beyond, "hasMore"));
        }
    }
    @Test void largeSnapshotFiltersAndGet() throws Exception {
        restart("personnel-v2-large-004", PersonnelService.Profile.normal);
        var all = Dataset.load("personnel-v2-large-004").records();
        long crew = all.stream().filter(m -> m.getCrewDetails() != null).count();
        long summed = 0;
        for (var department : lab.enterprise.personnel.contract.Department.values()) {
            long expected = all.stream().filter(m -> m.getCrewDetails() != null && m.getCrewDetails().getDepartment() == department).count();
            var page = call(wrapper("ListPersonnelMembersRequest", "<department>" + department.name() + "</department><limit>100</limit>"), 200);
            assertEquals(Long.toString(expected), text(page, "totalCount"), department.name());
            assertEquals(expected > 100 ? "true" : "false", text(page, "hasMore"), department.name());
            summed += expected;
        }
        assertEquals(crew, summed); // a department filter never matches a civilian
        long inactive = all.stream().filter(m -> m.getDutyStatus() == lab.enterprise.personnel.contract.DutyStatus.INACTIVE).count();
        assertEquals(Long.toString(inactive), text(call(wrapper("ListPersonnelMembersRequest", "<dutyStatus>INACTIVE</dutyStatus>"), 200), "totalCount"));
        var alexander = call(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-3001</personnelId>"), 200);
        assertEquals("Alexander Rozhenko", text(alexander, "displayName")); assertEquals(1, alexander.getElementsByTagNameNS(Xml.NS, "civilianDetails").getLength());
        var migrated = call(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-1101</personnelId>"), 200);
        assertEquals("Sonya Gomez", text(migrated, "displayName")); assertEquals("PRS-1049", text(migrated, "supervisorPersonnelId"));
        var oldCivilian = call(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-2785</personnelId>"), 200);
        assertEquals(1, oldCivilian.getElementsByTagNameNS(Xml.NS, "civilianDetails").getLength());
        assertEquals(0, oldCivilian.getElementsByTagNameNS(Xml.NS, "supervisorPersonnelId").getLength());
        fault(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-3200</personnelId>"), "PersonnelNotFound", "personnelId");
    }
    @ParameterizedTest @ValueSource(strings = {"", " ", "0", "101", "2147483648", "2.0", "2e1", "2 0"})
    void invalidLimitsHaveDeclaredField(String limit) throws Exception { fault(wrapper("ListPersonnelMembersRequest", "<limit>" + limit + "</limit>"), "InvalidRequest", "limit"); }
    @ParameterizedTest @ValueSource(strings = {"true", "1", "false", "0"})
    void nilIsNeverOmission(String nil) throws Exception {
        fault(wrapper("ListPersonnelMembersRequest", "<limit xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xsi:nil='" + nil + "'>2</limit>"), "InvalidRequest", "limit");
    }
    @Test void structuralInvalidRequestsCannotDisappearDuringBinding() throws Exception {
        fault(wrapper("ListPersonnelMembersRequest", "<limit>2</limit><limit>3</limit>"), "InvalidRequest", "limit");
        fault(wrapper("ListPersonnelMembersRequest", "<limit>2</limit><offset>0</offset>"), "InvalidRequest", "offset");
        fault(wrapper("ListPersonnelMembersRequest", "<unknown/>"), "InvalidRequest", null);
        fault("<ListPersonnelMembersRequest xmlns='wrong'/>", "InvalidRequest", null);
        fault(wrapper("ListPersonnelMembersRequest", "") + wrapper("ListPersonnelMembersRequest", ""), "InvalidRequest", null);
        fault(wrapper("GetPersonnelMemberRequest", "<personnelId> PRS-0001</personnelId>"), "InvalidRequest", "personnelId");
        fault(wrapper("GetPersonnelMemberRequest", ""), "InvalidRequest", "personnelId");
        fault(wrapper("ListPersonnelMembersRequest", "<department>engineering</department>"), "InvalidRequest", "department");
    }
    @Test void unavailableHonorsValidationBeforeLookupAndResets() throws Exception {
        restart(Dataset.DEFAULT_VERSION, PersonnelService.Profile.unavailable);
        fault(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-0000</personnelId>"), "InvalidRequest", "personnelId");
        fault(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-9999</personnelId>"), "ServiceUnavailable", null);
        fault(wrapper("ListPersonnelMembersRequest", ""), "ServiceUnavailable", null);
        restart(Dataset.DEFAULT_VERSION, PersonnelService.Profile.normal);
        assertEquals("7", text(call(wrapper("ListPersonnelMembersRequest", ""), 200), "totalCount"));
    }
    @Test void realSlowDelayIncludesNotFoundAndClientDeadline() throws Exception {
        restart(Dataset.DEFAULT_VERSION, PersonnelService.Profile.slow);
        long begin = System.nanoTime();
        fault(wrapper("ListPersonnelMembersRequest", "<limit>0</limit>"), "InvalidRequest", "limit");
        assertTrue(Duration.ofNanos(System.nanoTime() - begin).toMillis() < 1500, "Invalid requests should bypass the injected delay");
        begin = System.nanoTime();
        fault(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-9999</personnelId>"), "PersonnelNotFound", "personnelId");
        assertTrue(Duration.ofNanos(System.nanoTime() - begin).toMillis() >= 2000);
        assertThrows(HttpTimeoutException.class, () -> send(envelope(wrapper("ListPersonnelMembersRequest", "")), Duration.ofMillis(500)));
    }
    @Test void unexpectedServiceFailureHasDeclaredServerFault() throws Exception {
        stop(); start(Dataset.DEFAULT_VERSION, PersonnelService.Profile.slow, ignored -> { throw new IllegalStateException("secret"); });
        fault(wrapper("ListPersonnelMembersRequest", ""), "InternalError", null);
    }
    @Test void protocolInputsAreRejectedWithoutRequiringBusinessDetails() throws Exception {
        String valid = envelope(wrapper("ListPersonnelMembersRequest", ""));
        for (String xml : List.of("<broken", "<!DOCTYPE s:Envelope>" + valid,
                "<!DOCTYPE s:Envelope [<!ENTITY leak SYSTEM 'file:///etc/passwd'>]>" + valid.replace("<ListPersonnelMembersRequest", "&leak;<ListPersonnelMembersRequest"),
                valid.replace(Xml.SOAP, "http://www.w3.org/2003/05/soap-envelope"))) {
            var response = send(xml, Duration.ofSeconds(10));
            assertTrue(response.statusCode() >= 400);
            assertFalse(new String(response.body(), java.nio.charset.StandardCharsets.UTF_8).contains("root:x:"));
        }
    }
    @Test void wsdlPublishesBindingThroughDeploymentImport() throws Exception {
        var response = client.send(HttpRequest.newBuilder(URI.create(address + "?wsdl")).GET().build(), HttpResponse.BodyHandlers.ofByteArray());
        assertEquals(200, response.statusCode());
        var document = Xml.parse(response.body());
        for (String forbidden : List.of("types", "message", "portType", "binding"))
            assertEquals(0, document.getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/", forbidden).getLength(),
                "Deployment must not redeclare v2 " + forbidden);
        var metadata = document.getDocumentElement().getElementsByTagName("*");
        for (int i = 0; i < metadata.getLength(); i++) {
            var element = (Element) metadata.item(i);
            assertTrue(("http://schemas.xmlsoap.org/wsdl/".equals(element.getNamespaceURI()) &&
                Set.of("import", "service", "port").contains(element.getLocalName())) ||
                ("http://schemas.xmlsoap.org/wsdl/soap/".equals(element.getNamespaceURI()) &&
                "address".equals(element.getLocalName())), "Unexpected deployment declaration: " + element.getTagName());
        }
        var imported = (Element) document.getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/", "import").item(0);
        assertNotNull(imported);
        var contract = client.send(HttpRequest.newBuilder(URI.create(address).resolve(imported.getAttribute("location"))).GET().build(), HttpResponse.BodyHandlers.ofByteArray());
        assertEquals(200, contract.statusCode());
        var binding = Xml.parse(contract.body());
        assertEquals(5, binding.getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/", "message").getLength());
        var operations = ((Element) binding.getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/", "portType").item(0)).getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/", "operation");
        assertEquals(2, operations.getLength());
        var include = (Element) binding.getElementsByTagNameNS("http://www.w3.org/2001/XMLSchema", "include").item(0);
        var xsd = client.send(HttpRequest.newBuilder(URI.create(address).resolve(include.getAttribute("schemaLocation"))).GET().build(), HttpResponse.BodyHandlers.ofByteArray());
        assertEquals(200, xsd.statusCode()); assertEquals(Xml.NS, Xml.parse(xsd.body()).getDocumentElement().getAttribute("targetNamespace"));
    }
    @Test void restartAndDatasetReplacementRemainDeterministic() throws Exception {
        String query = wrapper("ListPersonnelMembersRequest", "<limit>2</limit>");
        var first = call(query, 200); var before = semantic(first);
        restart("personnel-v2-small-001", PersonnelService.Profile.normal);
        var same = call(query, 200); assertEquals(before, semantic(same));
        restart(Dataset.DEFAULT_VERSION, PersonnelService.Profile.normal);
        var replaced = call(query, 200); assertNotEquals(text(first, "datasetVersion"), text(replaced, "datasetVersion"));
        assertEquals("7", text(replaced, "totalCount")); assertEquals("PRS-0001", text(replaced, "personnelId"));
    }
    private List<String> ids(Element result) {
        var nodes = result.getElementsByTagNameNS(Xml.NS, "personnelId");
        var ids = new ArrayList<String>();
        for (int i = 0; i < nodes.getLength(); i++) ids.add(nodes.item(i).getTextContent());
        return ids;
    }
    @Test void stableWesleyIdentitySurvivesSubtypeChangeAndPaginationRestart() throws Exception {
        var civilian = call(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-0714</personnelId>"), 200);
        assertEquals("Wesley Crusher", text(civilian, "displayName"));
        assertEquals(1, civilian.getElementsByTagNameNS(Xml.NS, "civilianDetails").getLength());
        assertEquals(0, civilian.getElementsByTagNameNS(Xml.NS, "crewDetails").getLength());
        var first = call(wrapper("ListPersonnelMembersRequest", "<limit>2</limit>"), 200);
        var accumulated = new ArrayList<>(ids(first));
        restart(Dataset.DEFAULT_VERSION, PersonnelService.Profile.normal);
        var next = call(wrapper("ListPersonnelMembersRequest", "<offset>2</offset><limit>2</limit>"), 200);
        assertNotEquals(text(first, "datasetVersion"), text(next, "datasetVersion"));
        accumulated.clear();
        accumulated.addAll(ids(call(wrapper("ListPersonnelMembersRequest", "<limit>2</limit>"), 200)));
        assertEquals(List.of("PRS-0001", "PRS-0002"), accumulated);
        var crew = call(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-0714</personnelId>"), 200);
        assertEquals(text(civilian, "personnelId"), text(crew, "personnelId"));
        assertEquals(0, crew.getElementsByTagNameNS(Xml.NS, "civilianDetails").getLength());
        assertEquals("ENSIGN", text(crew, "rank"));
        assertEquals("NONE", text(crew, "securityClearance"));
        restart("personnel-v2-small-001", PersonnelService.Profile.normal);
        assertEquals(semantic(civilian), semantic(call(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-0714</personnelId>"), 200)));
    }
    @Test void allFiltersAndPageTraversalsIncludeCivilianAndDeceased() throws Exception {
        for (int limit : new int[]{1, 2, 20, 100}) {
            var collected = new ArrayList<String>();
            for (int offset = 0; offset < 7; offset += limit) {
                var page = call(wrapper("ListPersonnelMembersRequest", "<offset>" + offset + "</offset><limit>" + limit + "</limit>"), 200);
                assertEquals("7", text(page, "totalCount"));
                assertEquals(Boolean.toString(offset + ids(page).size() < 7), text(page, "hasMore"));
                collected.addAll(ids(page));
            }
            assertEquals(List.of("PRS-0001", "PRS-0002", "PRS-0003", "PRS-0004", "PRS-0005", "PRS-0006", "PRS-0714"), collected);
        }
        var departments = new ArrayList<lab.enterprise.personnel.contract.Department>(List.of(lab.enterprise.personnel.contract.Department.values())); departments.add(null);
        var statuses = new ArrayList<lab.enterprise.personnel.contract.DutyStatus>(List.of(lab.enterprise.personnel.contract.DutyStatus.values())); statuses.add(null);
        var records = Dataset.load("personnel-v2-small-001").records();
        for (var department : departments) for (var status : statuses) {
            String filter = (department == null ? "" : "<department>" + department.value() + "</department>") +
                (status == null ? "" : "<dutyStatus>" + status.value() + "</dutyStatus>");
            var expected = records.stream().filter(m -> department == null || (m.getCrewDetails() != null && m.getCrewDetails().getDepartment() == department))
                .filter(m -> status == null || m.getDutyStatus() == status).map(lab.enterprise.personnel.contract.PersonnelMember::getPersonnelId).toList();
            var page = call(wrapper("ListPersonnelMembersRequest", filter), 200);
            assertEquals(expected, ids(page)); assertEquals(Integer.toString(expected.size()), text(page, "totalCount"));
        }
        assertEquals(List.of("PRS-0006"), ids(call(wrapper("ListPersonnelMembersRequest", "<dutyStatus>DECEASED</dutyStatus>"), 200)));
        assertEquals("DECEASED", text(call(wrapper("GetPersonnelMemberRequest", "<personnelId>PRS-0006</personnelId>"), 200), "dutyStatus"));
        fault(wrapper("GetPersonnelMemberRequest", "<personnelId>P-0714</personnelId>"), "InvalidRequest", "personnelId");
        fault("<GetCrewMemberRequest xmlns='urn:graphql-federation-lab:crew-personnel:v1'><crewId>CRW-1047</crewId></GetCrewMemberRequest>", "InvalidRequest", null);
    }
}
