package lab.federation.adapters.personnel;

import java.io.StringReader;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NamedNodeMap;
import org.w3c.dom.Node;
import org.xml.sax.ErrorHandler;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;
import org.xml.sax.SAXParseException;

/**
 * Reads the SOAP 1.1 answers of the Personnel v2 service (namespace urn:graphql-federation-lab:personnel:v2) into plain maps whose keys
 * are the contract's element names, which are the GraphQL field names.
 *
 * The parser is safe by construction, the same way the Missions adapter's is: a document that carries a DOCTYPE is refused outright
 * (the service never sends one), which removes external entities, external DTDs and entity expansion in one rule; secure processing
 * is on, external general and parameter entities, external DTD loading and XInclude are off, and the DTD and schema access properties
 * are empty. Anything that does not read as the contract says (wrong root or namespace, an element out of order, a missing required
 * element, an attribute, an unknown enum token, an id or a number out of range, a civilian with details, a page that contradicts
 * itself) is an IllegalArgumentException, which the caller reports as UPSTREAM_BAD_RESPONSE.
 */
final class PersonnelXml {
    static final String NAMESPACE = "urn:graphql-federation-lab:personnel:v2";
    static final String SOAP = "http://schemas.xmlsoap.org/soap/envelope/";

    private static final Pattern PERSONNEL_ID = Pattern.compile("PRS-(?!0000)[0-9]{4}");
    private static final Pattern DATASET_VERSION = Pattern.compile("[a-z0-9]+(-[a-z0-9]+)*");
    private static final Set<String> RANKS = Set.of("CAPTAIN", "COMMANDER", "LIEUTENANT_COMMANDER", "LIEUTENANT", "ENSIGN",
            "CHIEF_PETTY_OFFICER", "CREWMAN");
    private static final Set<String> DEPARTMENTS = Set.of("COMMAND", "OPERATIONS", "ENGINEERING", "SCIENCE", "MEDICAL", "SECURITY",
            "FLIGHT_OPERATIONS");
    private static final Set<String> CLEARANCES = Set.of("NONE", "SECRET", "TOP_SECRET");
    private static final Set<String> STATUSES = Set.of("ACTIVE", "ON_LEAVE", "INACTIVE", "DECEASED");

    private PersonnelXml() {
    }

    /** True when the text is an id the contract can hold (PRS-0001 to PRS-9999). */
    static boolean isPersonnelId(String text) {
        return PERSONNEL_ID.matcher(text).matches();
    }

    /** The answer of GetPersonnelMember: the snapshot that answered and the member. */
    record Single(String datasetVersion, Map<String, Object> member) {
    }

    /** The answer of ListPersonnelMembers: the snapshot, the members in the service's order and the echoed paging facts. */
    record Page(String datasetVersion, List<Map<String, Object>> members, int totalCount, int offset, int limit, boolean hasMore) {
    }

    /** The PersonnelServiceFault of a SOAP fault: its code and the optional field. */
    record Fault(String code, String field) {
    }

    /** The answer of GetPersonnelMember: Envelope, Body, GetPersonnelMemberResponse. */
    static Single single(String body) {
        Element response = response(body, "GetPersonnelMemberResponse");
        List<Element> children = children(response);
        if (children.size() != 2) {
            throw new IllegalArgumentException("GetPersonnelMemberResponse must hold datasetVersion and personnelMember");
        }
        String version = datasetVersion(children.get(0));
        return new Single(version, member(named(children.get(1), "personnelMember")));
    }

    /** The answer of ListPersonnelMembers: datasetVersion, 0..100 personnelMember, totalCount, offset, limit, hasMore, in that order. */
    static Page page(String body) {
        Element response = response(body, "ListPersonnelMembersResponse");
        List<Element> children = children(response);
        if (children.size() < 5) {
            throw new IllegalArgumentException("ListPersonnelMembersResponse lacks its metadata");
        }
        String version = datasetVersion(children.get(0));
        int last = children.size() - 4;
        List<Map<String, Object>> members = new ArrayList<>();
        String previous = null;
        for (Element child : children.subList(1, last)) {
            Map<String, Object> member = member(named(child, "personnelMember"));
            String id = (String) member.get("personnelId");
            if (previous != null && previous.compareTo(id) >= 0) {
                throw new IllegalArgumentException("members are not in ascending personnelId order");
            }
            previous = id;
            members.add(member);
        }
        if (members.size() > 100) {
            throw new IllegalArgumentException("more than 100 members in a page");
        }
        int totalCount = integer(leaf(named(children.get(last), "totalCount")), 0, Integer.MAX_VALUE, "totalCount");
        int offset = integer(leaf(named(children.get(last + 1), "offset")), 0, Integer.MAX_VALUE, "offset");
        int limit = integer(leaf(named(children.get(last + 2), "limit")), 1, 100, "limit");
        boolean hasMore = bool(leaf(named(children.get(last + 3), "hasMore")));
        if (members.size() > limit || hasMore != ((long) offset + members.size() < totalCount)) {
            throw new IllegalArgumentException("the page contradicts its own metadata");
        }
        return new Page(version, members, totalCount, offset, limit, hasMore);
    }

    /**
     * The PersonnelServiceFault of a SOAP fault envelope. Null when the body is not a SOAP fault envelope at all (including a body that
     * is not well-formed). A fault without the contract's detail has a null code.
     */
    static Fault fault(String body) {
        try {
            Element payload = payload(body);
            if (!SOAP.equals(payload.getNamespaceURI()) || !"Fault".equals(payload.getLocalName())) {
                return null;
            }
            Element detail = null;
            for (Node node = payload.getFirstChild(); node != null; node = node.getNextSibling()) {
                if (node instanceof Element element && "detail".equals(element.getLocalName())) {
                    detail = element;
                }
            }
            if (detail == null) {
                return new Fault(null, null);
            }
            for (Node node = detail.getFirstChild(); node != null; node = node.getNextSibling()) {
                if (node instanceof Element element && NAMESPACE.equals(element.getNamespaceURI())
                        && "PersonnelServiceFault".equals(element.getLocalName())) {
                    String code = null;
                    String field = null;
                    for (Element child : children(element)) {
                        if ("code".equals(child.getLocalName())) {
                            code = leaf(child);
                        } else if ("field".equals(child.getLocalName())) {
                            field = leaf(child);
                        }
                    }
                    return new Fault(code, field);
                }
            }
            return new Fault(null, null);
        } catch (IllegalArgumentException error) {
            return null;
        }
    }

    // ---- the member -------------------------------------------------------------------------------------------------

    private static Map<String, Object> member(Element element) {
        List<Element> children = children(element);
        if (children.size() != 5) {
            throw new IllegalArgumentException("personnelMember must hold five elements");
        }
        Map<String, Object> member = new LinkedHashMap<>();
        String id = leaf(named(children.get(0), "personnelId"));
        if (!PERSONNEL_ID.matcher(id).matches()) {
            throw new IllegalArgumentException("personnelId is not PRS-0001 to PRS-9999");
        }
        member.put("personnelId", id);
        member.put("displayName", text100(leaf(named(children.get(1), "displayName")), "displayName"));
        member.put("positionTitle", text100(leaf(named(children.get(2), "positionTitle")), "positionTitle"));
        member.put("dutyStatus", token(leaf(named(children.get(3), "dutyStatus")), STATUSES, "dutyStatus"));
        Element details = children.get(4);
        if ("crewDetails".equals(details.getLocalName())) {
            member.put("details", crew(details));
        } else if ("civilianDetails".equals(details.getLocalName())) {
            if (!children(details).isEmpty() || !details.getTextContent().isBlank()) {
                throw new IllegalArgumentException("civilianDetails must be empty");
            }
            member.put("details", Map.of());
        } else {
            throw new IllegalArgumentException("a member holds crewDetails or civilianDetails");
        }
        return member;
    }

    private static Map<String, Object> crew(Element element) {
        List<Element> children = children(element);
        if (children.size() < 3 || children.size() > 4) {
            throw new IllegalArgumentException("crewDetails must hold rank, department, securityClearance and an optional supervisor");
        }
        Map<String, Object> crew = new LinkedHashMap<>();
        crew.put("rank", token(leaf(named(children.get(0), "rank")), RANKS, "rank"));
        crew.put("department", token(leaf(named(children.get(1), "department")), DEPARTMENTS, "department"));
        crew.put("securityClearance", token(leaf(named(children.get(2), "securityClearance")), CLEARANCES, "securityClearance"));
        String supervisor = null;
        if (children.size() == 4) {
            supervisor = leaf(named(children.get(3), "supervisorPersonnelId"));
            if (!PERSONNEL_ID.matcher(supervisor).matches()) {
                throw new IllegalArgumentException("supervisorPersonnelId is not PRS-0001 to PRS-9999");
            }
        }
        crew.put("supervisorPersonnelId", supervisor);
        return crew;
    }

    // ---- values -----------------------------------------------------------------------------------------------------

    private static String datasetVersion(Element element) {
        String version = leaf(named(element, "datasetVersion"));
        if (version.length() > 64 || !DATASET_VERSION.matcher(version).matches()) {
            throw new IllegalArgumentException("datasetVersion is not an identifier of the contract");
        }
        return version;
    }

    /** 1 to 100 XML characters (code points), not all whitespace; the text is kept exactly as sent. */
    private static String text100(String text, String name) {
        if (text.codePointCount(0, text.length()) > 100 || text.chars().allMatch(c -> c == ' ' || c == '\t' || c == '\r' || c == '\n')) {
            throw new IllegalArgumentException(name + " is blank or longer than 100 characters");
        }
        return text;
    }

    private static String token(String text, Set<String> allowed, String name) {
        if (!allowed.contains(text)) {
            throw new IllegalArgumentException("unknown " + name + " token");
        }
        return text;
    }

    private static int integer(String text, int min, int max, String name) {
        try {
            long value = Long.parseLong(text);
            if (value < min || value > max || !text.equals(Long.toString(value))) {
                throw new IllegalArgumentException(name + " is out of range");
            }
            return (int) value;
        } catch (NumberFormatException error) {
            throw new IllegalArgumentException(name + " is not a number", error);
        }
    }

    private static boolean bool(String text) {
        if (text.equals("true")) {
            return true;
        }
        if (text.equals("false")) {
            return false;
        }
        throw new IllegalArgumentException("hasMore is not a boolean");
    }

    private static Element named(Element element, String name) {
        if (!name.equals(element.getLocalName())) {
            throw new IllegalArgumentException("expected " + name + " but found " + element.getLocalName());
        }
        return element;
    }

    /** The text of an element that holds no element, non-empty. */
    private static String leaf(Element element) {
        if (!children(element).isEmpty()) {
            throw new IllegalArgumentException(element.getLocalName() + " must not hold elements");
        }
        String text = element.getTextContent();
        if (text == null || text.isEmpty()) {
            throw new IllegalArgumentException(element.getLocalName() + " is empty");
        }
        return text;
    }

    // ---- the envelope and the parser --------------------------------------------------------------------------------

    private static Element response(String body, String name) {
        Element payload = payload(body);
        if (!NAMESPACE.equals(payload.getNamespaceURI()) || !name.equals(payload.getLocalName())) {
            throw new IllegalArgumentException("not a " + name + " of the Personnel v2 namespace");
        }
        return payload;
    }

    /** The one element of the SOAP body. */
    private static Element payload(String body) {
        if (body == null) {
            throw new IllegalArgumentException("empty body");
        }
        Element envelope = parse(body).getDocumentElement();
        if (!SOAP.equals(envelope.getNamespaceURI()) || !"Envelope".equals(envelope.getLocalName())) {
            throw new IllegalArgumentException("not a SOAP 1.1 envelope");
        }
        Element soapBody = null;
        for (Node node = envelope.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element element) {
                if (soapBody != null || !SOAP.equals(element.getNamespaceURI()) || !"Body".equals(element.getLocalName())) {
                    throw new IllegalArgumentException("a SOAP 1.1 envelope here holds only a Body");
                }
                soapBody = element;
            }
        }
        if (soapBody == null) {
            throw new IllegalArgumentException("the envelope has no Body");
        }
        Element payload = null;
        for (Node node = soapBody.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element element) {
                if (payload != null) {
                    throw new IllegalArgumentException("the Body holds more than one element");
                }
                payload = element;
            }
        }
        if (payload == null) {
            throw new IllegalArgumentException("the Body is empty");
        }
        return payload;
    }

    /** The child elements, which must be in the Personnel namespace and carry no attribute (no xsi:nil, no default). */
    private static List<Element> children(Element parent) {
        NamedNodeMap attributes = parent.getAttributes();
        for (int index = 0; index < attributes.getLength(); index++) {
            if (!XMLConstants.XMLNS_ATTRIBUTE_NS_URI.equals(attributes.item(index).getNamespaceURI())) {
                throw new IllegalArgumentException("attributes are not part of the contract");
            }
        }
        List<Element> elements = new ArrayList<>();
        for (Node node = parent.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element element) {
                if (!NAMESPACE.equals(element.getNamespaceURI()) && !SOAP.equals(element.getNamespaceURI())) {
                    throw new IllegalArgumentException("element outside the Personnel v2 namespace");
                }
                elements.add(element);
            }
        }
        return elements;
    }

    private static Document parse(String body) {
        try {
            DocumentBuilder builder = factory().newDocumentBuilder();
            builder.setErrorHandler(new ErrorHandler() {
                @Override
                public void warning(SAXParseException error) {
                }

                @Override
                public void error(SAXParseException error) throws SAXException {
                    throw error;
                }

                @Override
                public void fatalError(SAXParseException error) throws SAXException {
                    throw error;
                }
            });
            return builder.parse(new InputSource(new StringReader(body)));
        } catch (SAXException | java.io.IOException | ParserConfigurationException error) {
            throw new IllegalArgumentException("not well-formed XML of the contract", error);
        }
    }

    /** A new factory per parse: the configuration is a few lines, and a shared factory is not guaranteed thread-safe. */
    private static DocumentBuilderFactory factory() throws ParserConfigurationException {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        factory.setXIncludeAware(false);
        factory.setExpandEntityReferences(false);
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
        return factory;
    }
}
