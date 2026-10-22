package lab.enterprise.personnel;

import lab.enterprise.personnel.contract.*;
import org.apache.cxf.binding.soap.SoapFault;
import org.w3c.dom.Element;

final class Faults {
    private Faults() { }
    static PersonnelServiceFaultMessage declared(String code, String field) {
        var detail = new PersonnelServiceFaultType();
        detail.setCode(FaultCode.fromValue(code));
        detail.setMessage(message(code));
        if (field != null) detail.setField(RequestField.fromValue(field));
        return new PersonnelServiceFaultMessage(detail.getMessage(), detail);
    }
    static SoapFault soap(String code, String field) {
        var fault = new SoapFault(message(code),
            code.equals("InvalidRequest") || code.equals("PersonnelNotFound") ? SoapFault.FAULT_CODE_CLIENT : SoapFault.FAULT_CODE_SERVER);
        Element detail = fault.getOrCreateDetail();
        var document = detail.getOwnerDocument();
        var wrapper = document.createElementNS(Xml.NS, "PersonnelServiceFault");
        detail.appendChild(wrapper);
        for (String[] entry : new String[][] {{"code", code}, {"message", message(code)}, {"field", field}}) {
            if (entry[1] == null) continue;
            var child = document.createElementNS(Xml.NS, entry[0]);
            child.setTextContent(entry[1]); wrapper.appendChild(child);
        }
        return fault;
    }
    private static String message(String code) {
        return switch (code) {
            case "InvalidRequest" -> "Request does not conform to Personnel v2.";
            case "PersonnelNotFound" -> "No personnel member has this personnelId in the selected dataset.";
            case "ServiceUnavailable" -> "Personnel is unavailable in the selected failure profile.";
            default -> "Personnel encountered an internal error.";
        };
    }
}
