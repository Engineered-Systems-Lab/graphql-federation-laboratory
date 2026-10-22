package lab.enterprise.missions.api;

import java.io.IOException;
import java.util.List;
import javax.annotation.Priority;
import javax.ws.rs.container.ContainerRequestContext;
import javax.ws.rs.container.ContainerRequestFilter;
import javax.ws.rs.container.PreMatching;
import javax.ws.rs.ext.Provider;
import lab.enterprise.missions.ApiException;
import lab.enterprise.missions.negotiation.Accept;
import lab.enterprise.missions.negotiation.ContentType;

/**
 * Decides, before Jersey routes, what Jersey must not decide: unknown paths, Accept negotiation, unsupported methods and
 * the media type of a request body.
 * Running ahead of matching also stops the framework from answering HEAD and OPTIONS on its own, so neither can be
 * answered or appear in an Allow header.
 */
@Provider
@PreMatching
@Priority(100)
public final class RouteFilter implements ContainerRequestFilter {
    @Override
    public void filter(ContainerRequestContext request) throws IOException {
        String path = request.getUriInfo().getPath(false);
        if (!knownPath(path)) {
            request.abortWith(Responses.bodyless(404));
            return;
        }
        try {
            if (!Accept.acceptsXml(request.getHeaders().get("Accept"))) {
                request.abortWith(Responses.bodyless(406));
                return;
            }
        } catch (ApiException e) {
            request.abortWith(Responses.error(e.status, e.code, e.getMessage()));
            return;
        }
        if (!methods(path).contains(request.getMethod())) {
            request.abortWith(Responses.methodNotAllowed(allow(path)));
            return;
        }
        // A body's media type is decided here, ahead of routing: Jersey parses Content-Type itself while matching and
        // answers a bare 400 for a value it cannot parse or a repeated header, where the contract says 415.
        if (request.getMethod().equals("POST") || request.getMethod().equals("PUT")) {
            try {
                ContentType.requireXml(request.getHeaders().get("Content-Type"));
            } catch (ApiException e) {
                request.abortWith(Responses.error(e.status, e.code, e.getMessage()));
            }
        }
    }

    /** missions, missions/{id} and missions/{id}/changes; anything else, including a trailing slash, is unknown. */
    static boolean knownPath(String path) {
        String[] parts = path.split("/", -1);
        if (parts.length == 0 || !parts[0].equals("missions")) return false;
        for (String part : parts) if (part.isEmpty()) return false;
        return parts.length == 1 || parts.length == 2 || parts.length == 3 && parts[2].equals("changes");
    }

    /** The methods a known path supports; HEAD and OPTIONS are on no path. */
    static List<String> methods(String path) {
        int segments = path.split("/", -1).length;
        return segments == 1 ? List.of("GET", "POST") : segments == 2 ? List.of("GET", "PUT") : List.of("GET");
    }

    /** The Allow header value of a known path. */
    static String allow(String path) { return String.join(", ", methods(path)); }
}
