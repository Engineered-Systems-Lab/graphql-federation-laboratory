package lab.federation.adapters.personnel;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.StringReader;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.validation.Schema;
import javax.xml.validation.SchemaFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;

/**
 * A stub of the Personnel v2 service on loopback. Its real answers come from the files of the repository: the two registered
 * snapshots (personnel-v2-small-001 and personnel-v2-small-002, seven members each, the Wesley case) serve GetPersonnelMember and
 * ListPersonnelMembers with the contract's filters, sorting and paging. Every request the adapter sends is validated against the
 * real XSD (uss-enterprise/personnel-v2/contracts/personnel-v2.xsd) and recorded; one that does not conform is answered with the
 * InvalidRequest fault and counted in {@link #invalid()}, so a test can assert that the adapter only ever sends conforming requests.
 *
 * A route is an exact call key ("get/PRS-0001" or "list?department=X&amp;dutyStatus=Y&amp;offset=0&amp;limit=20", absent filters left
 * out) and wins over the snapshot, so a test can make any call fail. {@link #routeAll} answers every call.
 */
final class StubPersonnel implements AutoCloseable {
    record Reply(int status, String body, long delayMs) {
    }

    static final String NS = "urn:graphql-federation-lab:personnel:v2";
    static final String SOAP = "http://schemas.xmlsoap.org/soap/envelope/";
    static final String SMALL_001 = "personnel-v2-small-001";
    static final String SMALL_002 = "personnel-v2-small-002";

    /** The repository root, found from the working directory of the test (the module folder, in Docker or on a checkout). */
    static Path root() {
        Path path = Path.of("").toAbsolutePath();
        while (path != null && !Files.isDirectory(path.resolve("uss-enterprise/personnel-v2/datasets"))) {
            path = path.getParent();
        }
        if (path == null) {
            throw new IllegalStateException("The Personnel v2 datasets were not found above " + Path.of("").toAbsolutePath());
        }
        return path;
    }

    static String snapshot(String name) {
        return read(root().resolve("uss-enterprise/personnel-v2/datasets").resolve(name + ".xml"));
    }

    private static String read(Path path) {
        try {
            return Files.readString(path, StandardCharsets.UTF_8);
        } catch (IOException error) {
            throw new IllegalStateException(error);
        }
    }

    /** The blocks of the snapshot, in the service's order. */
    static List<String> blocks(String listXml) {
        List<String> blocks = new ArrayList<>();
        Matcher matcher = Pattern.compile("(?s)<personnelMember>.*?</personnelMember>").matcher(listXml);
        while (matcher.find()) {
            blocks.add(matcher.group());
        }
        return blocks;
    }

    static String field(String block, String name) {
        Matcher matcher = Pattern.compile("(?s)<" + name + ">(.*?)</" + name + ">").matcher(block);
        return matcher.find() ? matcher.group(1) : null;
    }

    static String envelope(String payload) {
        return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><soap:Envelope xmlns:soap=\"" + SOAP + "\"><soap:Body>" + payload + "</soap:Body></soap:Envelope>";
    }

    /** A declared fault as the service sends it: SOAP 1.1 Fault, faultcode Client for InvalidRequest and PersonnelNotFound, Server otherwise. */
    static String fault(String code, String field) {
        String faultCode = code.equals("InvalidRequest") || code.equals("PersonnelNotFound") ? "soap:Client" : "soap:Server";
        String message = switch (code) {
            case "InvalidRequest" -> "Request does not conform to Personnel v2.";
            case "PersonnelNotFound" -> "No personnel member has this personnelId in the selected dataset.";
            case "ServiceUnavailable" -> "Personnel is unavailable in the selected failure profile.";
            default -> "Personnel encountered an internal error.";
        };
        return envelope("<soap:Fault><faultcode>" + faultCode + "</faultcode><faultstring>" + message + "</faultstring><detail>"
                + "<PersonnelServiceFault xmlns=\"" + NS + "\"><code>" + code + "</code><message>" + message + "</message>"
                + (field == null ? "" : "<field>" + field + "</field>") + "</PersonnelServiceFault></detail></soap:Fault>");
    }

    private static final Schema SCHEMA = schema();

    private static Schema schema() {
        try {
            SchemaFactory factory = SchemaFactory.newDefaultInstance();
            factory.setProperty(XMLConstants.ACCESS_EXTERNAL_DTD, "");
            factory.setProperty(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
            return factory.newSchema(root().resolve("uss-enterprise/personnel-v2/contracts/personnel-v2.xsd").toFile());
        } catch (Exception error) {
            throw new IllegalStateException(error);
        }
    }

    private final HttpServer server;
    private final Map<String, Reply> routes = new HashMap<>();
    private final Map<String, Reply> once = new HashMap<>();
    private final List<String> calls = Collections.synchronizedList(new ArrayList<>());
    private final List<String> invalid = Collections.synchronizedList(new ArrayList<>());
    private final List<String> actions = Collections.synchronizedList(new ArrayList<>());
    private Reply all;
    private String version = SMALL_002;
    private List<String> blocks = blocks(snapshot(SMALL_002));

    StubPersonnel() throws IOException {
        server = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        server.setExecutor(Executors.newCachedThreadPool());
        server.createContext("/", exchange -> {
            Reply reply;
            try {
                String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
                reply = answer(exchange, body);
                if (reply.delayMs() > 0) {
                    Thread.sleep(reply.delayMs());
                }
                byte[] bytes = reply.body().getBytes(StandardCharsets.UTF_8);
                if (reply.body().isEmpty()) {
                    exchange.sendResponseHeaders(reply.status(), -1);
                } else {
                    exchange.getResponseHeaders().add("Content-Type", "text/xml;charset=UTF-8");
                    exchange.sendResponseHeaders(reply.status(), bytes.length);
                    exchange.getResponseBody().write(bytes);
                }
            } catch (InterruptedException | IOException ignored) {
                // the client gave up (a timeout test)
            } finally {
                exchange.close();
            }
        });
        server.start();
    }

    // ---- the service, from the registered snapshots -----------------------------------------------------------------

    private Reply answer(HttpExchange exchange, String body) {
        if (!exchange.getRequestMethod().equals("POST") || !exchange.getRequestURI().getRawPath().equals("/soap/personnel-v2")) {
            calls.add("other " + exchange.getRequestMethod() + " " + exchange.getRequestURI().getRawPath());
            return new Reply(404, "", 0);
        }
        actions.add(String.valueOf(exchange.getRequestHeaders().getFirst("SOAPAction")));
        String key;
        Element payload;
        try {
            payload = payload(body);
            SCHEMA.newValidator().validate(new DOMSource(payload));
            key = key(payload);
        } catch (Exception error) {
            invalid.add(body);
            calls.add("invalid");
            return new Reply(500, fault("InvalidRequest", null), 0);
        }
        calls.add(key);
        synchronized (routes) {
            if (once.containsKey(key)) {
                return once.remove(key);
            }
            if (routes.containsKey(key)) {
                return routes.get(key);
            }
            if (all != null) {
                return all;
            }
        }
        return key.startsWith("get/") ? get(key.substring(4)) : list(payload);
    }

    private static Element payload(String body) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Document document = factory.newDocumentBuilder().parse(new InputSource(new StringReader(body)));
        Element envelope = document.getDocumentElement();
        if (!SOAP.equals(envelope.getNamespaceURI()) || !"Envelope".equals(envelope.getLocalName())) {
            throw new IllegalArgumentException("not an envelope");
        }
        for (Node bodyNode = envelope.getFirstChild(); bodyNode != null; bodyNode = bodyNode.getNextSibling()) {
            if (bodyNode instanceof Element soapBody && "Body".equals(soapBody.getLocalName())) {
                for (Node node = soapBody.getFirstChild(); node != null; node = node.getNextSibling()) {
                    if (node instanceof Element element) {
                        return element;
                    }
                }
            }
        }
        throw new IllegalArgumentException("no payload");
    }

    private static String child(Element payload, String name) {
        for (Node node = payload.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element element && name.equals(element.getLocalName())) {
                return element.getTextContent();
            }
        }
        return null;
    }

    /** The call key of a valid request payload. */
    private static String key(Element payload) {
        if ("GetPersonnelMemberRequest".equals(payload.getLocalName())) {
            return "get/" + child(payload, "personnelId");
        }
        StringBuilder key = new StringBuilder("list");
        String separator = "?";
        for (String name : List.of("department", "dutyStatus", "offset", "limit")) {
            String value = child(payload, name);
            if (value != null) {
                key.append(separator).append(name).append('=').append(value.trim());
                separator = "&";
            }
        }
        return key.toString();
    }

    private Reply get(String id) {
        List<String> snapshot;
        String currentVersion;
        synchronized (routes) {
            snapshot = blocks;
            currentVersion = version;
        }
        for (String block : snapshot) {
            if (id.equals(field(block, "personnelId"))) {
                return new Reply(200, envelope("<GetPersonnelMemberResponse xmlns=\"" + NS + "\"><datasetVersion>" + currentVersion + "</datasetVersion>"
                        + block + "</GetPersonnelMemberResponse>"), 0);
            }
        }
        return new Reply(500, fault("PersonnelNotFound", "personnelId"), 0);
    }

    private Reply list(Element payload) {
        List<String> snapshot;
        String currentVersion;
        synchronized (routes) {
            snapshot = blocks;
            currentVersion = version;
        }
        String department = child(payload, "department");
        String dutyStatus = child(payload, "dutyStatus");
        int offset = child(payload, "offset") == null ? 0 : Integer.parseInt(child(payload, "offset").trim());
        int limit = child(payload, "limit") == null ? 20 : Integer.parseInt(child(payload, "limit").trim());
        List<String> matching = new ArrayList<>();
        for (String block : snapshot) {
            boolean ok = (department == null || department.equals(field(block, "department")))
                    && (dutyStatus == null || dutyStatus.equals(field(block, "dutyStatus")));
            if (ok) {
                matching.add(block);
            }
        }
        List<String> window = offset >= matching.size() ? List.of() : matching.subList(offset, Math.min(matching.size(), offset + limit));
        boolean hasMore = (long) offset + window.size() < matching.size();
        return new Reply(200, envelope("<ListPersonnelMembersResponse xmlns=\"" + NS + "\"><datasetVersion>" + currentVersion + "</datasetVersion>"
                + String.join("", window) + "<totalCount>" + matching.size() + "</totalCount><offset>" + offset + "</offset><limit>" + limit
                + "</limit><hasMore>" + hasMore + "</hasMore></ListPersonnelMembersResponse>"), 0);
    }

    // ---- control ----------------------------------------------------------------------------------------------------

    String url() {
        return "http://127.0.0.1:" + server.getAddress().getPort() + "/soap/personnel-v2";
    }

    int port() {
        return server.getAddress().getPort();
    }

    /** Serves the named registered snapshot from now on (the Wesley case: a civilian in 001, crew in 002). */
    void use(String name) {
        synchronized (routes) {
            version = name;
            blocks = blocks(snapshot(name));
        }
    }

    /** Serves the named generated snapshot from now on: count members PRS-0001 to PRS-count, all active civilians. */
    void useGenerated(String name, int count) {
        synchronized (routes) {
            version = name;
            blocks = generatedBlocks(1, count);
        }
    }

    /** The blocks of the generated members PRS-from to PRS-to. */
    static List<String> generatedBlocks(int from, int to) {
        List<String> generated = new ArrayList<>();
        for (int number = from; number <= to; number++) {
            generated.add(String.format("<personnelMember><personnelId>PRS-%04d</personnelId><displayName>Cadet %d</displayName>"
                    + "<positionTitle>Cadet</positionTitle><dutyStatus>ACTIVE</dutyStatus><civilianDetails/></personnelMember>", number, number));
        }
        return generated;
    }

    /** A list answer made by hand, for a test that needs a page the stub would not serve. */
    static String page(String datasetVersion, List<String> members, int totalCount, int offset, int limit, boolean hasMore) {
        return envelope("<ListPersonnelMembersResponse xmlns=\"" + NS + "\"><datasetVersion>" + datasetVersion + "</datasetVersion>" + String.join("", members)
                + "<totalCount>" + totalCount + "</totalCount><offset>" + offset + "</offset><limit>" + limit + "</limit><hasMore>" + hasMore
                + "</hasMore></ListPersonnelMembersResponse>");
    }

    void route(String key, int status, String body) {
        route(key, status, body, 0);
    }

    /** Like {@link #route}, but for the first call of the key only. */
    void routeOnce(String key, int status, String body) {
        synchronized (routes) {
            once.put(key, new Reply(status, body, 0));
        }
    }

    void route(String key, int status, String body, long delayMs) {
        synchronized (routes) {
            routes.put(key, new Reply(status, body, delayMs));
        }
    }

    void routeAll(int status, String body) {
        synchronized (routes) {
            all = new Reply(status, body, 0);
        }
    }

    List<String> calls() {
        synchronized (calls) {
            return new ArrayList<>(calls);
        }
    }

    /** The bodies of the requests that did not conform to the XSD. */
    List<String> invalid() {
        synchronized (invalid) {
            return new ArrayList<>(invalid);
        }
    }

    List<String> actions() {
        synchronized (actions) {
            return new ArrayList<>(actions);
        }
    }

    void reset() {
        synchronized (routes) {
            routes.clear();
            once.clear();
            all = null;
            version = SMALL_002;
            blocks = blocks(snapshot(SMALL_002));
        }
        calls.clear();
        invalid.clear();
        actions.clear();
    }

    @Override
    public void close() {
        server.stop(0);
    }
}
