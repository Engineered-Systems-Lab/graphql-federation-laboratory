package lab.enterprise.personnel;

import lab.enterprise.personnel.contract.PersonnelServiceFaultMessage;
import org.apache.cxf.binding.soap.SoapFault;
import org.apache.cxf.message.Message;
import org.apache.cxf.phase.AbstractPhaseInterceptor;
import org.apache.cxf.phase.Phase;

/** Map generated declared exceptions before CXF serializes SOAP faults; never leak exception text. */
final class FaultMapping extends AbstractPhaseInterceptor<Message> {
    FaultMapping() { super(Phase.PRE_PROTOCOL); }
    @Override public void handleMessage(Message message) {
        Throwable failure = message.getContent(Exception.class);
        for (Throwable cause = failure; cause != null; cause = cause.getCause()) {
            if (cause instanceof PersonnelServiceFaultMessage declared) {
                var info = declared.getFaultInfo();
                message.setContent(Exception.class, Faults.soap(info.getCode().value(),
                    info.getField() == null ? null : info.getField().value()));
                return;
            }
        }
        // Preserve ingress business and protocol faults. Other unexpected failures get a sanitized declared fault.
        if (!(failure instanceof SoapFault)) message.setContent(Exception.class, Faults.soap("InternalError", null));
    }
}
