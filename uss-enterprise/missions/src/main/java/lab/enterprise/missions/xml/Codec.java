package lab.enterprise.missions.xml;

import com.sun.xml.bind.marshaller.NamespacePrefixMapper;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.xml.XMLConstants;
import javax.xml.bind.JAXBContext;
import javax.xml.bind.JAXBElement;
import javax.xml.bind.JAXBException;
import javax.xml.bind.Marshaller;
import javax.xml.bind.Unmarshaller;
import javax.xml.bind.ValidationEvent;
import javax.xml.namespace.QName;
import javax.xml.parsers.ParserConfigurationException;
import javax.xml.parsers.SAXParserFactory;
import javax.xml.transform.sax.SAXSource;
import javax.xml.validation.Schema;
import javax.xml.validation.SchemaFactory;
import lab.enterprise.missions.ApiException;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;
import org.xml.sax.XMLReader;

/**
 * Marshals the generated contract types to UTF-8 bytes, validating every response against the frozen 1.1 schema,
 * and reads a request body with the same schema: secure parsing, first problem stops, a failure is 400 INVALID_REQUEST.
 */
public final class Codec {
    public static final String NS = "urn:starfleet:missions:v1";
    public static final String CONTENT_TYPE = "application/xml; charset=UTF-8";
    private static final int MESSAGE_LIMIT = 1000;
    private static final JAXBContext CONTEXT;
    private static final Schema SCHEMA;
    private static final ObjectFactory FACTORY = new ObjectFactory();
    private static final QName MISSION_ELEMENT = new QName(NS, "mission");
    private static final Pattern DECLARED_ENCODING = Pattern.compile("^<\\?xml[^>]*?\\sencoding\\s*=\\s*([\"'])([^\"']*)\\1");

    static {
        try {
            // The Java 17 Xerces default counts UTF-16 units; the Missions contract counts code points (D034).
            System.setProperty("com.sun.org.apache.xerces.internal.impl.dv.xs.useCodePointCountForStringLength", "true");
            var factory = SchemaFactory.newDefaultInstance();
            factory.setProperty(XMLConstants.ACCESS_EXTERNAL_DTD, "");
            factory.setProperty(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
            SCHEMA = factory.newSchema(Codec.class.getResource("/contracts/missions-v1.1.xsd"));
            CONTEXT = JAXBContext.newInstance("lab.enterprise.missions.xml");
        } catch (Exception e) { throw new ExceptionInInitializerError(e); }
    }

    private Codec() { }

    public static ObjectFactory factory() { return FACTORY; }

    public static byte[] mission(Mission mission) { return marshal(FACTORY.createMission(mission)); }

    public static byte[] missionList(MissionList list) { return marshal(FACTORY.createMissionList(list)); }

    public static byte[] changeList(ChangeList list) { return marshal(FACTORY.createChangeList(list)); }

    /** The common error body; a message over the bound is shortened rather than emitted invalid. */
    public static byte[] error(String code, String message) {
        var error = new lab.enterprise.missions.xml.Error();
        error.setCode(ErrorCode.fromValue(code));
        String text = message == null || message.isEmpty() ? "Request failed" : message;
        if (text.codePointCount(0, text.length()) > MESSAGE_LIMIT) text = text.substring(0, text.offsetByCodePoints(0, MESSAGE_LIMIT));
        error.setMessage(text);
        return marshal(FACTORY.createError(error));
    }

    private static byte[] marshal(JAXBElement<?> element) {
        try {
            Marshaller marshaller = CONTEXT.createMarshaller();
            marshaller.setSchema(SCHEMA);
            marshaller.setProperty(Marshaller.JAXB_ENCODING, "UTF-8");
            marshaller.setProperty("com.sun.xml.bind.namespacePrefixMapper", new NamespacePrefixMapper() {
                @Override public String getPreferredPrefix(String namespace, String suggestion, boolean required) { return ""; }
            });
            var out = new ByteArrayOutputStream();
            marshaller.marshal(element, out);
            return out.toByteArray();
        } catch (JAXBException e) {
            throw new IllegalStateException("Response is not valid under the Missions contract", e);
        }
    }

    /**
     * Reads a POST or PUT body. The bytes must be UTF-8 (a BOM is tolerated; an XML declaration naming another encoding is
     * not), the document is parsed without DTDs or external entities and validated against the schema, and its root must be
     * a mission. Presence rules that depend on the request's role are domain validation, not decided here.
     *
     * @throws ApiException 400 INVALID_REQUEST for anything that is not one schema-valid mission document
     */
    public static Mission parseMission(byte[] bytes) {
        requireUtf8(bytes);
        ValidationEvent[] first = new ValidationEvent[1];
        try {
            Unmarshaller unmarshaller = CONTEXT.createUnmarshaller();
            unmarshaller.setSchema(SCHEMA);
            unmarshaller.setEventHandler(event -> { if (first[0] == null) first[0] = event; return false; });
            Object root = unmarshaller.unmarshal(new SAXSource(secureReader(), new InputSource(new ByteArrayInputStream(bytes))));
            if (root instanceof JAXBElement<?> element && MISSION_ELEMENT.equals(element.getName()) && element.getValue() instanceof Mission mission)
                return mission;
            throw ApiException.invalidRequest("The request body must be a mission document");
        } catch (JAXBException e) {
            ValidationEvent event = first[0];
            var locator = event == null ? null : event.getLocator();
            String where = locator == null || locator.getLineNumber() < 0 ? ""
                    : " (line " + locator.getLineNumber() + ", column " + locator.getColumnNumber() + ")";
            // The parser's own wording is framework detail and stays out of the response.
            throw ApiException.invalidRequest("The request body is not a valid mission document" + where);
        }
    }

    private static XMLReader secureReader() {
        try {
            SAXParserFactory factory = SAXParserFactory.newInstance();
            factory.setNamespaceAware(true);
            factory.setXIncludeAware(false);
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
            factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
            return factory.newSAXParser().getXMLReader();
        } catch (ParserConfigurationException | SAXException e) {
            throw new IllegalStateException("XML parser cannot be configured securely", e);
        }
    }

    /** UTF-8 only: reject a UTF-16 or UTF-32 byte layout, and a declaration that names any other encoding. */
    static void requireUtf8(byte[] bytes) {
        int start = 0;
        if (bytes.length >= 3 && (bytes[0] & 0xFF) == 0xEF && (bytes[1] & 0xFF) == 0xBB && (bytes[2] & 0xFF) == 0xBF) start = 3;
        else if (bytes.length >= 2 && ((bytes[0] & 0xFF) == 0xFE && (bytes[1] & 0xFF) == 0xFF
                || (bytes[0] & 0xFF) == 0xFF && (bytes[1] & 0xFF) == 0xFE))
            throw ApiException.invalidRequest("The request body must be UTF-8");
        for (int i = start; i < Math.min(bytes.length, start + 4); i++)
            if (bytes[i] == 0) throw ApiException.invalidRequest("The request body must be UTF-8");
        String head = new String(bytes, start, Math.min(bytes.length - start, 300), StandardCharsets.ISO_8859_1);
        Matcher declared = DECLARED_ENCODING.matcher(head);
        if (declared.find() && !declared.group(2).toUpperCase(Locale.ROOT).equals("UTF-8"))
            throw ApiException.invalidRequest("The XML declaration must name UTF-8");
    }
}
