package lab.federation.adapters.missions;

import java.io.StringReader;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import lab.federation.common.HttpResult;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.ErrorHandler;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;
import org.xml.sax.SAXParseException;

/**
 * Reads the XML of the Missions service (contract 1.1, namespace urn:starfleet:missions:v1) into plain maps whose keys are the
 * contract's element names, which are the GraphQL field names.
 *
 * The parser is safe by construction: a document that carries a DOCTYPE is refused outright (the service never sends one), which
 * removes external entities, external DTDs and entity expansion in one rule; secure processing is on, external general and
 * parameter entities, external DTD loading and XInclude are off, and the DTD and schema access properties are empty. Anything
 * that does not read as the contract says (wrong root or namespace, a missing required element, an unknown enum token, a number out
 * of range) is an IllegalArgumentException, which the caller reports as UPSTREAM_BAD_RESPONSE.
 */
final class MissionXml {
    static final String NAMESPACE = "urn:starfleet:missions:v1";

    private static final Set<String> TYPES = Set.of("DIPLOMATIC", "EXPLORATION", "SCIENTIFIC", "FIRST_CONTACT", "MEDICAL", "RESCUE",
            "HUMANITARIAN", "SECURITY", "TACTICAL", "TRANSPORT", "MAINTENANCE");
    private static final Set<String> CLASSIFICATIONS = Set.of("UNCLASSIFIED", "SECRET", "TOP_SECRET");
    private static final Set<String> STATUSES = Set.of("PLANNED", "AUTHORIZED", "ACTIVE", "POSTPONED", "COMPLETED", "FAILED", "CANCELLED");
    private static final Set<String> LOCATION_TYPES = Set.of("PLANET", "STARBASE", "VESSEL", "SECTOR", "DEEP_SPACE", "ENTERPRISE", "OTHER");
    private static final Set<String> AUTHORITIES = Set.of("STARFLEET_COMMAND", "ENTERPRISE_COMMAND", "STARFLEET_MEDICAL",
            "STARFLEET_SCIENCE", "STARFLEET_SECURITY", "FEDERATION_COUNCIL");

    private MissionXml() {
    }

    /** One page of the list: the metadata the service echoed and the missions in the service's order. */
    record Page(long page, int pageSize, long totalCount, long totalPages, List<Map<String, Object>> missions) {
    }

    /** The mission of a GET /missions/{id} answer: root element mission. */
    static Map<String, Object> mission(String body) {
        Element root = root(body, "mission");
        return missionOf(root);
    }

    /** The page of a GET /missions answer: root element missionList, four metadata children, then the missions. */
    static Page page(String body) {
        Element root = root(body, "missionList");
        List<Element> children = children(root);
        if (children.size() < 4) {
            throw new IllegalArgumentException("missionList lacks its metadata");
        }
        long page = number(meta(children, 0, "page"), "page");
        if (page < 1) {
            throw new IllegalArgumentException("page is out of range");
        }
        int pageSize = integer(meta(children, 1, "pageSize"), 1, 50, "pageSize");
        long totalCount = number(meta(children, 2, "totalCount"), "totalCount");
        long totalPages = number(meta(children, 3, "totalPages"), "totalPages");
        List<Map<String, Object>> missions = new ArrayList<>();
        for (Element child : children.subList(4, children.size())) {
            if (!"mission".equals(child.getLocalName())) {
                throw new IllegalArgumentException("unexpected element in missionList");
            }
            missions.add(missionOf(child));
        }
        return new Page(page, pageSize, totalCount, totalPages, missions);
    }

    private static String meta(List<Element> children, int index, String name) {
        Element element = children.get(index);
        if (!name.equals(element.getLocalName())) {
            throw new IllegalArgumentException("missionList: expected " + name);
        }
        return requireText(element, name);
    }

    /** The {@code code} of the service's XML error body, or null when the body is not such an error. */
    static String errorCode(HttpResult result) {
        if (result.failed() || result.body() == null) {
            return null;
        }
        try {
            List<Element> children = children(root(result.body(), "error"));
            return children.isEmpty() || !"code".equals(children.get(0).getLocalName()) ? null : children.get(0).getTextContent();
        } catch (IllegalArgumentException error) {
            return null;
        }
    }

    // ---- the mission ------------------------------------------------------------------------------------------------

    private static Map<String, Object> missionOf(Element element) {
        Map<String, Element> field = new LinkedHashMap<>();
        for (Element child : children(element)) {
            if (field.put(child.getLocalName(), child) != null) {
                throw new IllegalArgumentException("duplicate element " + child.getLocalName());
            }
        }
        Map<String, Object> mission = new LinkedHashMap<>();
        mission.put("missionId", requireText(field.get("missionId"), "missionId"));
        mission.put("title", requireText(field.get("title"), "title"));
        mission.put("type", token(field.get("type"), TYPES, "type"));
        mission.put("classification", token(field.get("classification"), CLASSIFICATIONS, "classification"));
        mission.put("status", token(field.get("status"), STATUSES, "status"));
        mission.put("priority", integer(requireText(field.get("priority"), "priority"), 1, 5, "priority"));
        mission.put("stardate", requireText(field.get("stardate"), "stardate"));
        mission.put("durationHours", integer(requireText(field.get("durationHours"), "durationHours"), 1, 8760, "durationHours"));
        mission.put("objective", requireText(field.get("objective"), "objective"));
        mission.put("location", location(field.get("location")));
        mission.put("issuingAuthority", token(field.get("issuingAuthority"), AUTHORITIES, "issuingAuthority"));
        mission.put("commandingOfficerId", optionalText(field.get("commandingOfficerId")));
        mission.put("assignedCrewIds", members(field.get("assignedCrewIds"), "crewId"));
        mission.put("participantIds", members(field.get("participantIds"), "participantId"));
        mission.put("assignedAssetIds", members(field.get("assignedAssetIds"), "assetId"));
        mission.put("estimatedCostCredits", optionalText(field.get("estimatedCostCredits")));
        mission.put("actualCostCredits", optionalText(field.get("actualCostCredits")));
        mission.put("outcome", optionalText(field.get("outcome")));
        mission.put("lastUpdated", requireText(field.get("lastUpdated"), "lastUpdated"));
        return mission;
    }

    private static Map<String, Object> location(Element element) {
        if (element == null) {
            throw new IllegalArgumentException("location is missing");
        }
        Map<String, Element> field = new LinkedHashMap<>();
        for (Element child : children(element)) {
            field.put(child.getLocalName(), child);
        }
        Map<String, Object> location = new LinkedHashMap<>();
        location.put("type", token(field.get("type"), LOCATION_TYPES, "location.type"));
        location.put("name", requireText(field.get("name"), "location.name"));
        location.put("coordinates", optionalText(field.get("coordinates")));
        location.put("travelVector", optionalText(field.get("travelVector")));
        return location;
    }

    private static List<String> members(Element container, String name) {
        if (container == null) {
            throw new IllegalArgumentException("collection is missing");
        }
        List<String> members = new ArrayList<>();
        for (Element child : children(container)) {
            if (!name.equals(child.getLocalName())) {
                throw new IllegalArgumentException("unexpected element in a collection");
            }
            members.add(requireText(child, name));
        }
        return members;
    }

    // ---- values -----------------------------------------------------------------------------------------------------

    private static String token(Element element, Set<String> allowed, String name) {
        String value = requireText(element, name);
        if (!allowed.contains(value)) {
            throw new IllegalArgumentException("unknown " + name + " token");
        }
        return value;
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

    private static long number(String text, String name) {
        try {
            long value = Long.parseLong(text);
            if (value < 0 || !text.equals(Long.toString(value))) {
                throw new IllegalArgumentException(name + " is out of range");
            }
            return value;
        } catch (NumberFormatException error) {
            throw new IllegalArgumentException(name + " is not a number", error);
        }
    }

    private static String requireText(Element element, String name) {
        if (element == null) {
            throw new IllegalArgumentException(name + " is missing");
        }
        String text = element.getTextContent();
        if (text == null || text.isEmpty()) {
            throw new IllegalArgumentException(name + " is empty");
        }
        return text;
    }

    private static String optionalText(Element element) {
        return element == null ? null : requireText(element, element.getLocalName());
    }

    // ---- the parser -------------------------------------------------------------------------------------------------

    private static Element root(String body, String name) {
        if (body == null) {
            throw new IllegalArgumentException("empty body");
        }
        Element root = parse(body).getDocumentElement();
        if (!NAMESPACE.equals(root.getNamespaceURI()) || !name.equals(root.getLocalName())) {
            throw new IllegalArgumentException("not a " + name + " of the Missions namespace");
        }
        return root;
    }

    private static List<Element> children(Element parent) {
        List<Element> elements = new ArrayList<>();
        for (Node node = parent.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element element) {
                if (!NAMESPACE.equals(element.getNamespaceURI())) {
                    throw new IllegalArgumentException("element outside the Missions namespace");
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

    /** A new factory per parse: the configuration is five lines, and a shared factory is not guaranteed thread-safe. */
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
