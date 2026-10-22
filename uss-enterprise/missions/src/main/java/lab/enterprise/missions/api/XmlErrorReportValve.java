package lab.enterprise.missions.api;

import java.io.IOException;
import org.apache.catalina.connector.Request;
import org.apache.catalina.core.StandardHost;
import org.apache.catalina.connector.Response;
import org.apache.catalina.startup.Tomcat;
import org.apache.catalina.valves.ErrorReportValve;
import lab.enterprise.missions.xml.Codec;

/**
 * Tomcat refuses some requests itself, before the application runs (a control character in a header value: U+000B, U+000C,
 * U+001C to U+001F and DEL), and answers with its own HTML 400. The contract says every error carries the common XML body,
 * so this valve, installed on the host, writes 400 INVALID_REQUEST in that form. Any other status keeps Tomcat's page.
 */
public final class XmlErrorReportValve extends ErrorReportValve {
    /** Makes the host of an embedded Tomcat use this valve; call before the server starts. */
    public static void install(Tomcat tomcat) {
        ((StandardHost) tomcat.getHost()).setErrorReportValveClass(XmlErrorReportValve.class.getName());
    }

    @Override
    protected void report(Request request, Response response, Throwable throwable) {
        if (response.getStatus() != 400 || response.isCommitted() || response.getContentWritten() > 0) {
            super.report(request, response, throwable);
            return;
        }
        byte[] body = Codec.error("INVALID_REQUEST", "Malformed request");
        try {
            response.setContentType(Codec.CONTENT_TYPE);
            response.setContentLength(body.length);
            response.getOutputStream().write(body);
            response.finishResponse();
        } catch (IOException | IllegalStateException e) {
            // The connection is already unusable; nothing more can be reported on it.
        }
    }
}
