package lab.enterprise.crew;

import java.io.ByteArrayInputStream;
import java.util.Set;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.sax.SAXResult;
import javax.xml.validation.Schema;
import javax.xml.validation.SchemaFactory;
import org.w3c.dom.*;
import org.xml.sax.*;
import org.xml.sax.helpers.XMLFilterImpl;

/** One offline schema; fresh parsers/validators per request (these are not thread-safe). */
final class Xml {
    static final String NS = "urn:graphql-federation-lab:crew-personnel:v1";
    static final String SOAP = "http://schemas.xmlsoap.org/soap/envelope/";
    static final Set<String> FIELDS = Set.of("crewId", "department", "dutyStatus", "offset", "limit");
    static final Schema SCHEMA = schema();

    private static Schema schema() {
        try {
            // The Java 17 Xerces default counts UTF-16 units. The frozen contract counts XML characters.
            System.setProperty("com.sun.org.apache.xerces.internal.impl.dv.xs.useCodePointCountForStringLength", "true");
            var factory = SchemaFactory.newDefaultInstance();
            factory.setProperty(XMLConstants.ACCESS_EXTERNAL_DTD, "");
            factory.setProperty(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
            return factory.newSchema(Xml.class.getResource("/contracts/crew-personnel-v1.xsd"));
        } catch (Exception e) { throw new ExceptionInInitializerError(e); }
    }

    static Document parse(byte[] bytes) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
        factory.setXIncludeAware(false);
        factory.setExpandEntityReferences(false);
        var builder = factory.newDocumentBuilder();
        builder.setErrorHandler(new org.xml.sax.helpers.DefaultHandler() {
            @Override public void error(SAXParseException e) throws SAXException { throw e; }
            @Override public void fatalError(SAXParseException e) throws SAXException { throw e; }
        });
        return builder.parse(new ByteArrayInputStream(bytes));
    }

    static void validate(Element payload) throws Exception {
        rejectAttributes(payload);
        var validator = SCHEMA.newValidatorHandler();
        // Track the offending element independently of vendor-specific diagnostic prose.
        var tracker = new XMLFilterImpl() {
            String field;
            @Override public void startElement(String uri, String local, String q, Attributes a) throws SAXException {
                field = FIELDS.contains(local) ? local : null;
                super.startElement(uri, local, q, a);
            }
            @Override public void endElement(String uri, String local, String q) throws SAXException {
                field = FIELDS.contains(local) ? local : null;
                super.endElement(uri, local, q);
            }
        };
        validator.setErrorHandler(new org.xml.sax.helpers.DefaultHandler() {
            @Override public void error(SAXParseException e) throws SAXException { throw new InvalidPayload(tracker.field); }
            @Override public void fatalError(SAXParseException e) throws SAXException { throw new InvalidPayload(tracker.field); }
        });
        tracker.setContentHandler(validator);
        var tf = TransformerFactory.newInstance();
        tf.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
        tf.setAttribute(XMLConstants.ACCESS_EXTERNAL_STYLESHEET, "");
        try { tf.newTransformer().transform(new DOMSource(payload), new SAXResult(tracker)); }
        catch (javax.xml.transform.TransformerException e) {
            for (Throwable t = e; t != null; t = t.getCause()) {
                if (t instanceof InvalidPayload invalid) throw invalid;
            }
            throw e;
        }
    }

    private static void rejectAttributes(Element element) throws InvalidPayload {
        var attrs = element.getAttributes();
        for (int i = 0; i < attrs.getLength(); i++) {
            if (!XMLConstants.XMLNS_ATTRIBUTE_NS_URI.equals(attrs.item(i).getNamespaceURI()))
                throw new InvalidPayload(FIELDS.contains(element.getLocalName()) ? element.getLocalName() : null);
        }
        for (Node n = element.getFirstChild(); n != null; n = n.getNextSibling())
            if (n instanceof Element child) rejectAttributes(child);
    }

    static final class InvalidPayload extends SAXException {
        final String field;
        InvalidPayload(String field) { super("Request does not conform to the frozen contract"); this.field = field; }
    }
}
