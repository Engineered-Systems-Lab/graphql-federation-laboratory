package lab.enterprise.missions.api;

import java.io.IOException;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletRequestWrapper;
import javax.servlet.http.HttpServletResponse;
import javax.ws.rs.core.MediaType;
import lab.enterprise.missions.xml.Codec;
import org.glassfish.jersey.server.ResourceConfig;
import org.glassfish.jersey.servlet.ServletContainer;

/**
 * The Jersey servlet, guarded against one thing Jersey does before any filter can run: it parses the request Content-Type
 * while it reads the request, and answers a bare 400 for a value it cannot parse or for a repeated header. The contract says
 * a body of POST or PUT with such a media type is 415 UNSUPPORTED_MEDIA_TYPE with the common XML error body. Any other
 * request simply loses the unusable header, so that routing (404, 405, 406) decides as it would without it.
 */
public final class MissionsServlet extends ServletContainer {
    public MissionsServlet(ResourceConfig config) { super(config); }

    @Override
    protected void service(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException {
        List<String> lines = Collections.list(request.getHeaders("Content-Type"));
        if (!lines.isEmpty() && !parseable(lines)) {
            if (carriesBody(request.getMethod(), request.getRequestURI())) {
                unsupported(response);
                return;
            }
            request = new WithoutContentType(request);
        }
        super.service(request, response);
    }

    /** True when Jersey can read the header: exactly one line that is a media type. */
    static boolean parseable(List<String> lines) {
        if (lines.size() != 1) return false;
        try {
            MediaType.valueOf(lines.get(0));
            return true;
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    /** POST or PUT to a path that supports it: the requests whose body media type the contract decides. */
    static boolean carriesBody(String method, String requestUri) {
        if (!method.equals("POST") && !method.equals("PUT")) return false;
        String path = requestUri.startsWith("/") ? requestUri.substring(1) : requestUri;
        return RouteFilter.knownPath(path) && RouteFilter.methods(path).contains(method);
    }

    private static void unsupported(HttpServletResponse response) throws IOException {
        byte[] body = Codec.error("UNSUPPORTED_MEDIA_TYPE", "The Content-Type is not usable; application/xml is required");
        response.setStatus(415);
        response.setHeader("Content-Type", Codec.CONTENT_TYPE);
        response.setContentLength(body.length);
        response.getOutputStream().write(body);
    }

    /** The same request without its Content-Type header. */
    private static final class WithoutContentType extends HttpServletRequestWrapper {
        WithoutContentType(HttpServletRequest request) { super(request); }

        @Override public String getContentType() { return null; }

        @Override public String getHeader(String name) { return contentType(name) ? null : super.getHeader(name); }

        @Override public Enumeration<String> getHeaders(String name) {
            return contentType(name) ? Collections.emptyEnumeration() : super.getHeaders(name);
        }

        @Override public Enumeration<String> getHeaderNames() {
            return Collections.enumeration(Collections.list(super.getHeaderNames()).stream().filter(n -> !contentType(n)).toList());
        }

        private static boolean contentType(String name) { return name.equalsIgnoreCase("Content-Type"); }
    }
}
