package lab.enterprise.missions.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.InetAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.apache.catalina.Context;
import org.apache.catalina.startup.Tomcat;
import org.junit.jupiter.api.Test;

/** Runs a real embedded Tomcat: the container's own refusal of a control character in a header must carry the XML error. */
class XmlErrorReportValveTest {
    private static String exchange(Tomcat tomcat, byte[] headerValue) throws IOException {
        int port = tomcat.getConnector().getLocalPort();
        try (Socket socket = new Socket(InetAddress.getLoopbackAddress(), port)) {
            var out = new ByteArrayOutputStream();
            out.write("POST /missions HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\nContent-Length: 0\r\nX-Starfleet-Audit-Summary: ".getBytes(StandardCharsets.ISO_8859_1));
            out.write(headerValue);
            out.write("\r\n\r\n".getBytes(StandardCharsets.ISO_8859_1));
            socket.getOutputStream().write(out.toByteArray());
            socket.getOutputStream().flush();
            return new String(socket.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    @Test void aContainerLevelRefusalAnswersTheContractsXmlBody() throws Exception {
        Path base = Files.createTempDirectory("valve-test");
        var tomcat = new Tomcat();
        tomcat.setBaseDir(base.toString());
        tomcat.getConnector().setPort(0);
        XmlErrorReportValve.install(tomcat);
        Context context = tomcat.addContext("", base.toString());
        Tomcat.addServlet(context, "ok", new HttpServlet() {
            @Override protected void doPost(HttpServletRequest req, HttpServletResponse resp) { resp.setStatus(201); }
        });
        context.addServletMappingDecoded("/*", "ok");
        tomcat.start();
        try {
            for (byte control : new byte[] {0x0b, 0x0c, 0x1c, 0x1d, 0x1e, 0x1f, 0x7f}) {
                String reply = exchange(tomcat, new byte[] {'a', control, 'b'});
                assertTrue(reply.startsWith("HTTP/1.1 400"), "0x" + Integer.toHexString(control) + " " + reply);
                assertTrue(reply.toLowerCase().contains("content-type: application/xml"), reply);
                assertTrue(reply.contains("<code>INVALID_REQUEST</code>"), reply);
                assertTrue(!reply.contains("<html"), reply);
            }
            assertTrue(exchange(tomcat, "fine".getBytes(StandardCharsets.ISO_8859_1)).startsWith("HTTP/1.1 201"));
        } finally {
            tomcat.stop();
            tomcat.destroy();
        }
    }
}
