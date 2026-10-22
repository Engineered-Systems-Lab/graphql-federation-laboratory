package lab.enterprise.missions.api;

import javax.ws.rs.WebApplicationException;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.Response;
import javax.ws.rs.core.UriInfo;
import javax.ws.rs.ext.ExceptionMapper;
import javax.ws.rs.ext.Provider;
import lab.enterprise.missions.ApiException;

/** Maps every failure to the contract: nothing about Java, Jersey or Oracle ever reaches a response body. */
@Provider
public final class ErrorMapper implements ExceptionMapper<Throwable> {
    @Context
    private UriInfo uriInfo;

    @Override
    public Response toResponse(Throwable failure) {
        if (failure instanceof ApiException e) return Responses.error(e.status, e.code, e.getMessage());
        if (failure instanceof WebApplicationException e) {
            int status = e.getResponse().getStatus();
            if (status == 404) return Responses.bodyless(404);
            if (status == 405) return Responses.methodNotAllowed(allow());
            if (status == 400) return Responses.error(400, "INVALID_REQUEST", "Malformed request");
        }
        // The cause stays in the server log only.
        System.err.println("Missions internal failure: " + failure);
        failure.printStackTrace();
        return Responses.error(500, "INTERNAL_ERROR", "Internal server error");
    }

    private String allow() {
        try {
            String path = uriInfo.getPath(false);
            if (RouteFilter.knownPath(path)) return RouteFilter.allow(path);
        } catch (RuntimeException ignored) {
            // No request context: fall back to the one method every path supports.
        }
        return "GET";
    }
}
