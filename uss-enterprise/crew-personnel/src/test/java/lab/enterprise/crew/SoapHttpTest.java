package lab.enterprise.crew;

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
    @BeforeEach void start() throws Exception { start("crew-v1-small-001", CrewService.Profile.normal, null); }
    @AfterEach void stop() { if (server != null) server.destroy(); if (bus != null) bus.shutdown(true); }
    private void start(String version, CrewService.Profile profile, CrewService.Delay delay) throws Exception {
        int port;
        try (var socket = new java.net.ServerSocket(0, 0, InetAddress.getLoopbackAddress())) { port = socket.getLocalPort(); }
        address = "http://127.0.0.1:" + port + "/soap/crew-personnel";
        bus = BusFactory.newInstance().createBus();
        var dataset = Dataset.load(version);
        server = Main.publish(bus, address, delay == null ? new CrewService(dataset, profile) : new CrewService(dataset, profile, delay));
    }
    private void restart(String version, CrewService.Profile profile) throws Exception { stop(); start(version, profile, null); }
    private String wrapper(String name, String children) { return "<" + name + " xmlns='" + Xml.NS + "'>" + children + "</" + name + ">"; }
    private String envelope(String payload) { return "<s:Envelope xmlns:s='" + Xml.SOAP + "'><s:Body>" + payload + "</s:Body></s:Envelope>"; }
    private HttpResponse<byte[]> send(String xml, Duration timeout) throws Exception {
        return client.send(HttpRequest.newBuilder(URI.create(address)).timeout(timeout)
            .header("Content-Type", "text/xml; charset=utf-8")
            .header("SOAPAction", "\"" + Xml.NS + (xml.contains("GetCrewMemberRequest") ? ":GetCrewMember" : ":ListCrewMembers") + "\"").POST(HttpRequest.BodyPublishers.ofString(xml)).build(), HttpResponse.BodyHandlers.ofByteArray());
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
            assertTrue(result.getElementsByTagNameNS(Xml.NS, "crewMember").getLength() <= 100);
        }
        else {
            assertEquals("Fault", result.getLocalName()); assertEquals(Xml.SOAP, result.getNamespaceURI());
            var details = result.getElementsByTagNameNS(Xml.NS, "CrewServiceFault"); assertEquals(1, details.getLength());
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
        assertEquals(Set.of("InvalidRequest", "CrewNotFound").contains(code) ? "Client" : "Server", qname[qname.length - 1]);
    }
    @Test void getIncludesInactiveAndOmitsAbsentSupervisor() throws Exception {
        var picard = call(wrapper("GetCrewMemberRequest", "<crewId>CRW-1047</crewId>"), 200);
        assertEquals("Jean-Luc Picard", text(picard, "displayName")); assertEquals(0, picard.getElementsByTagNameNS(Xml.NS, "supervisorCrewId").getLength());
        var inactive = call(wrapper("GetCrewMemberRequest", "<crewId>CRW-1052</crewId>"), 200);
        assertEquals("INACTIVE", text(inactive, "dutyStatus")); assertEquals("CRW-1049", text(inactive, "supervisorCrewId"));
        fault(wrapper("GetCrewMemberRequest", "<crewId>CRW-9999</crewId>"), "CrewNotFound", "crewId");
    }
    @Test void listDefaultsFiltersAndPagination() throws Exception {
        var all = call(wrapper("ListCrewMembersRequest", ""), 200);
        assertEquals(semantic(Xml.parse(Files.readAllBytes(Path.of("fixtures/canonical/crew-v1-small-001.xml"))).getDocumentElement()), semantic(all));
        assertEquals("6", text(all, "totalCount")); assertEquals("20", text(all, "limit")); assertEquals("0", text(all, "offset"));
        assertEquals(6, all.getElementsByTagNameNS(Xml.NS, "crewMember").getLength()); assertEquals("false", text(all, "hasMore"));
        var page = call(wrapper("ListCrewMembersRequest", "<offset> +02 </offset><limit>002</limit>"), 200);
        assertEquals("CRW-1049", text(page, "crewId")); assertEquals("true", text(page, "hasMore")); assertEquals("2", text(page, "offset"));
        for (int offset : new int[]{6, 7, Integer.MAX_VALUE}) {
            var beyond = call(wrapper("ListCrewMembersRequest", "<offset>" + offset + "</offset>"), 200);
            assertEquals(0, beyond.getElementsByTagNameNS(Xml.NS, "crewMember").getLength()); assertEquals("false", text(beyond, "hasMore"));
        }
        var filtered = call(wrapper("ListCrewMembersRequest", "<department>ENGINEERING</department><dutyStatus>ACTIVE</dutyStatus>"), 200);
        assertEquals("1", text(filtered, "totalCount")); assertEquals("CRW-1049", text(filtered, "crewId"));
        var leave = call(wrapper("ListCrewMembersRequest", "<dutyStatus>ON_LEAVE</dutyStatus>"), 200); assertEquals("CRW-1051", text(leave, "crewId"));
        var empty = call(wrapper("ListCrewMembersRequest", "<department>MEDICAL</department>"), 200); assertEquals("0", text(empty, "totalCount"));
        for (int limit : new int[]{1, 100}) assertEquals(Integer.toString(limit), text(call(wrapper("ListCrewMembersRequest", "<limit>" + limit + "</limit>"), 200), "limit"));
    }
    @ParameterizedTest @ValueSource(strings = {"", " ", "0", "101", "2147483648", "2.0", "2e1", "2 0"})
    void invalidLimitsHaveDeclaredField(String limit) throws Exception { fault(wrapper("ListCrewMembersRequest", "<limit>" + limit + "</limit>"), "InvalidRequest", "limit"); }
    @ParameterizedTest @ValueSource(strings = {"true", "1", "false", "0"})
    void nilIsNeverOmission(String nil) throws Exception {
        fault(wrapper("ListCrewMembersRequest", "<limit xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xsi:nil='" + nil + "'>2</limit>"), "InvalidRequest", "limit");
    }
    @Test void structuralInvalidRequestsCannotDisappearDuringBinding() throws Exception {
        fault(wrapper("ListCrewMembersRequest", "<limit>2</limit><limit>3</limit>"), "InvalidRequest", "limit");
        fault(wrapper("ListCrewMembersRequest", "<limit>2</limit><offset>0</offset>"), "InvalidRequest", "offset");
        fault(wrapper("ListCrewMembersRequest", "<unknown/>"), "InvalidRequest", null);
        fault("<ListCrewMembersRequest xmlns='wrong'/>", "InvalidRequest", null);
        fault(wrapper("ListCrewMembersRequest", "") + wrapper("ListCrewMembersRequest", ""), "InvalidRequest", null);
        fault(wrapper("GetCrewMemberRequest", "<crewId> CRW-1047</crewId>"), "InvalidRequest", "crewId");
        fault(wrapper("GetCrewMemberRequest", ""), "InvalidRequest", "crewId");
        fault(wrapper("ListCrewMembersRequest", "<department>engineering</department>"), "InvalidRequest", "department");
    }
    @Test void unavailableHonorsValidationBeforeLookupAndResets() throws Exception {
        restart(Dataset.DEFAULT_VERSION, CrewService.Profile.unavailable);
        fault(wrapper("GetCrewMemberRequest", "<crewId>CRW-0000</crewId>"), "InvalidRequest", "crewId");
        fault(wrapper("GetCrewMemberRequest", "<crewId>CRW-9999</crewId>"), "ServiceUnavailable", null);
        fault(wrapper("ListCrewMembersRequest", ""), "ServiceUnavailable", null);
        restart(Dataset.DEFAULT_VERSION, CrewService.Profile.normal);
        assertEquals("12", text(call(wrapper("ListCrewMembersRequest", ""), 200), "totalCount"));
    }
    @Test void realSlowDelayIncludesNotFoundAndClientDeadline() throws Exception {
        restart(Dataset.DEFAULT_VERSION, CrewService.Profile.slow);
        long begin = System.nanoTime();
        fault(wrapper("ListCrewMembersRequest", "<limit>0</limit>"), "InvalidRequest", "limit");
        assertTrue(Duration.ofNanos(System.nanoTime() - begin).toMillis() < 1500, "Invalid requests should bypass the injected delay");
        begin = System.nanoTime();
        fault(wrapper("GetCrewMemberRequest", "<crewId>CRW-9999</crewId>"), "CrewNotFound", "crewId");
        assertTrue(Duration.ofNanos(System.nanoTime() - begin).toMillis() >= 2000);
        assertThrows(HttpTimeoutException.class, () -> send(envelope(wrapper("ListCrewMembersRequest", "")), Duration.ofMillis(500)));
    }
    @Test void unexpectedServiceFailureHasDeclaredServerFault() throws Exception {
        stop(); start(Dataset.DEFAULT_VERSION, CrewService.Profile.slow, ignored -> { throw new IllegalStateException("secret"); });
        fault(wrapper("ListCrewMembersRequest", ""), "InternalError", null);
    }
    @Test void protocolInputsAreRejectedWithoutRequiringBusinessDetails() throws Exception {
        for (String name : List.of("malformed", "dtd", "external-entity", "soap12")) {
            var response = send(Files.readString(Path.of("fixtures/protocol/" + name + ".xml")), Duration.ofSeconds(10));
            assertTrue(response.statusCode() >= 400, name);
            assertFalse(new String(response.body(), java.nio.charset.StandardCharsets.UTF_8).contains("root:x:"));
        }
    }
    @Test void wsdlPublishesFrozenBindingThroughDeploymentImport() throws Exception {
        var response = client.send(HttpRequest.newBuilder(URI.create(address + "?wsdl")).GET().build(), HttpResponse.BodyHandlers.ofByteArray());
        assertEquals(200, response.statusCode());
        var document = Xml.parse(response.body());
        for (String forbidden : List.of("types", "message", "portType", "binding"))
            assertEquals(0, document.getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/", forbidden).getLength(),
                "Deployment must not redeclare frozen " + forbidden);
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
        var frozen = Xml.parse(contract.body());
        assertEquals(5, frozen.getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/", "message").getLength());
        var operations = ((Element) frozen.getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/", "portType").item(0)).getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/", "operation");
        assertEquals(2, operations.getLength());
        var include = (Element) frozen.getElementsByTagNameNS("http://www.w3.org/2001/XMLSchema", "include").item(0);
        var xsd = client.send(HttpRequest.newBuilder(URI.create(address).resolve(include.getAttribute("schemaLocation"))).GET().build(), HttpResponse.BodyHandlers.ofByteArray());
        assertEquals(200, xsd.statusCode()); assertEquals(Xml.NS, Xml.parse(xsd.body()).getDocumentElement().getAttribute("targetNamespace"));
    }
    @Test void restartAndDatasetReplacementRemainDeterministic() throws Exception {
        String query = wrapper("ListCrewMembersRequest", "<limit>2</limit>");
        var first = call(query, 200); var before = semantic(first);
        restart("crew-v1-small-001", CrewService.Profile.normal);
        var same = call(query, 200); assertEquals(before, semantic(same));
        restart(Dataset.DEFAULT_VERSION, CrewService.Profile.normal);
        var replaced = call(query, 200); assertNotEquals(text(first, "datasetVersion"), text(replaced, "datasetVersion"));
        assertEquals("12", text(replaced, "totalCount")); assertEquals("CRW-1047", text(replaced, "crewId"));
    }
    private List<String> ids(Element result) {
        var nodes = result.getElementsByTagNameNS(Xml.NS, "crewId");
        var ids = new ArrayList<String>();
        for (int i = 0; i < nodes.getLength(); i++) ids.add(nodes.item(i).getTextContent());
        return ids;
    }
    @Test void largeDatasetTraversesEveryPageAndFilterOverHttp() throws Exception {
        restart("crew-v1-large-003", CrewService.Profile.normal);
        var records = Dataset.load("crew-v1-large-003").records();
        var expected = records.stream().map(lab.enterprise.crew.contract.CrewMember::getCrewId).toList();
        var defaults = call(wrapper("ListCrewMembersRequest", ""), 200);
        assertEquals("800", text(defaults, "totalCount")); assertEquals(20, ids(defaults).size());
        for (int limit : new int[]{1, 20, 100}) {
            var collected = new ArrayList<String>();
            for (int offset = 0; offset < 800; offset += limit) {
                var result = call(wrapper("ListCrewMembersRequest", "<offset>" + offset + "</offset><limit>" + limit + "</limit>"), 200);
                assertEquals("crew-v1-large-003", text(result, "datasetVersion"));
                assertEquals("800", text(result, "totalCount"));
                assertEquals(Integer.toString(offset), text(result, "offset"));
                assertEquals(Integer.toString(limit), text(result, "limit"));
                assertEquals(Boolean.toString(offset + ids(result).size() < 800), text(result, "hasMore"));
                collected.addAll(ids(result));
            }
            assertEquals(expected, collected);
        }
        for (int offset : new int[]{95, 199, 695, 799, 800, 801, Integer.MAX_VALUE}) {
            var result = call(wrapper("ListCrewMembersRequest", "<offset>" + offset + "</offset><limit>20</limit>"), 200);
            assertEquals(expected.stream().skip(offset).limit(20).toList(), ids(result));
        }
        var departments = new ArrayList<lab.enterprise.crew.contract.Department>(List.of(lab.enterprise.crew.contract.Department.values())); departments.add(null);
        var statuses = new ArrayList<lab.enterprise.crew.contract.DutyStatus>(List.of(lab.enterprise.crew.contract.DutyStatus.values())); statuses.add(null);
        for (var department : departments) for (var status : statuses) {
            var matches = records.stream().filter(m -> department == null || m.getDepartment() == department)
                .filter(m -> status == null || m.getDutyStatus() == status).map(lab.enterprise.crew.contract.CrewMember::getCrewId).toList();
            String filter = (department == null ? "" : "<department>" + department.value() + "</department>") +
                (status == null ? "" : "<dutyStatus>" + status.value() + "</dutyStatus>");
            var result = call(wrapper("ListCrewMembersRequest", filter + "<offset>5</offset><limit>100</limit>"), 200);
            assertEquals(Integer.toString(matches.size()), text(result, "totalCount"));
            assertEquals(matches.stream().skip(5).limit(100).toList(), ids(result));
        }
        for (String id : List.of("CRW-1047", "CRW-1050", "CRW-1052", "CRW-1055", "CRW-1056", "CRW-1100", "CRW-1101", "CRW-2000", "CRW-2186", "CRW-2785")) {
            var result = call(wrapper("GetCrewMemberRequest", "<crewId>" + id + "</crewId>"), 200);
            var member = records.stream().filter(m -> m.getCrewId().equals(id)).findFirst().orElseThrow();
            assertEquals(member.getDisplayName(), text(result, "displayName"));
            assertEquals(member.getDepartment().value(), text(result, "department"));
            assertEquals(member.getPositionTitle(), text(result, "positionTitle"));
            if (member.getSupervisorCrewId() == null) assertEquals(0, result.getElementsByTagNameNS(Xml.NS, "supervisorCrewId").getLength());
            else {
                assertEquals(member.getSupervisorCrewId(), text(result, "supervisorCrewId"));
                assertEquals(List.of(member.getSupervisorCrewId()), ids(call(wrapper("GetCrewMemberRequest", "<crewId>" + member.getSupervisorCrewId() + "</crewId>"), 200)));
            }
        }
        fault(wrapper("GetCrewMemberRequest", "<crewId>CRW-9999</crewId>"), "CrewNotFound", "crewId");
        fault(wrapper("ListCrewMembersRequest", "<limit>101</limit>"), "InvalidRequest", "limit");
    }
    @Test void largeVersionRestartResetsClientAccumulatorAndProfiles() throws Exception {
        restart(Dataset.DEFAULT_VERSION, CrewService.Profile.normal);
        var first = call(wrapper("ListCrewMembersRequest", "<limit>2</limit>"), 200);
        var accumulated = new ArrayList<>(ids(first));
        restart("crew-v1-large-003", CrewService.Profile.normal);
        var next = call(wrapper("ListCrewMembersRequest", "<offset>2</offset><limit>2</limit>"), 200);
        assertNotEquals(text(first, "datasetVersion"), text(next, "datasetVersion"));
        accumulated.clear();
        accumulated.addAll(ids(call(wrapper("ListCrewMembersRequest", "<limit>2</limit>"), 200)));
        assertEquals(List.of("CRW-1047", "CRW-1048"), accumulated);
        restart("crew-v1-large-003", CrewService.Profile.unavailable);
        fault(wrapper("GetCrewMemberRequest", "<crewId>CRW-0000</crewId>"), "InvalidRequest", "crewId");
        fault(wrapper("GetCrewMemberRequest", "<crewId>CRW-9999</crewId>"), "ServiceUnavailable", null);
        fault(wrapper("ListCrewMembersRequest", ""), "ServiceUnavailable", null);
        restart("crew-v1-large-003", CrewService.Profile.slow);
        long begin = System.nanoTime();
        assertEquals("800", text(call(wrapper("ListCrewMembersRequest", ""), 200), "totalCount"));
        assertTrue(Duration.ofNanos(System.nanoTime() - begin).toMillis() >= 2000);
    }
}
