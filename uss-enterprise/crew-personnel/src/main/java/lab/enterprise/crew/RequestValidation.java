package lab.enterprise.crew;

import java.io.*;
import org.apache.cxf.binding.soap.SoapFault;
import org.apache.cxf.message.Message;
import org.apache.cxf.phase.AbstractPhaseInterceptor;
import org.apache.cxf.phase.Phase;
import org.w3c.dom.*;

/** Validate raw payload before CXF dispatch/JAXB can discard unknown or duplicate fields. */
final class RequestValidation extends AbstractPhaseInterceptor<Message> {
    RequestValidation() { super(Phase.RECEIVE); }
    @Override public void handleMessage(Message message) {
        if ("GET".equals(message.get(Message.HTTP_REQUEST_METHOD))) return; // CXF WSDL retrieval
        final byte[] bytes;
        final Document document;
        try {
            var input = message.getContent(InputStream.class);
            if (input == null) throw new IOException("No body");
            bytes = input.readAllBytes();
            document = Xml.parse(bytes);
        } catch (Exception e) {
            // Protocol errors deliberately do not promise a declared business detail.
            throw new SoapFault("Malformed or prohibited XML.", SoapFault.FAULT_CODE_CLIENT);
        }
        var envelope = document.getDocumentElement();
        if (!Xml.SOAP.equals(envelope.getNamespaceURI()) || !"Envelope".equals(envelope.getLocalName()))
            throw new SoapFault("Only SOAP 1.1 is supported.", new javax.xml.namespace.QName(Xml.SOAP, "VersionMismatch"));
        var bodies = envelope.getElementsByTagNameNS(Xml.SOAP, "Body");
        if (bodies.getLength() != 1 || bodies.item(0).getParentNode() != envelope)
            throw Faults.soap("InvalidRequest", null);
        Element payload = null;
        for (Node node = bodies.item(0).getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element element) {
                if (payload != null) throw Faults.soap("InvalidRequest", null);
                payload = element;
            } else if (node.getNodeType() == Node.TEXT_NODE && !node.getTextContent().isBlank()) {
                throw Faults.soap("InvalidRequest", null);
            }
        }
        if (payload == null || !Xml.NS.equals(payload.getNamespaceURI()) ||
            !("GetCrewMemberRequest".equals(payload.getLocalName()) || "ListCrewMembersRequest".equals(payload.getLocalName())))
            throw Faults.soap("InvalidRequest", null);
        if ("GetCrewMemberRequest".equals(payload.getLocalName()) && payload.getElementsByTagName("*").getLength() == 0 && payload.getTextContent().isBlank())
            throw Faults.soap("InvalidRequest", "crewId");
        try { Xml.validate(payload); }
        catch (Xml.InvalidPayload e) { throw Faults.soap("InvalidRequest", e.field); }
        catch (Exception e) { throw Faults.soap("InternalError", null); }
        message.setContent(InputStream.class, new ByteArrayInputStream(bytes));
    }
}
