package lab.enterprise.missions.api;

import javax.ws.rs.core.Response;
import lab.enterprise.missions.xml.Codec;

/** One place builds every response, so the media type and error shape cannot drift between code paths. */
final class Responses {
    private Responses() { }

    static Response xml(byte[] body) {
        return Response.ok(body).header("Content-Type", Codec.CONTENT_TYPE).build();
    }

    /** A mission with the strong ETag of its current change id. */
    static Response mission(byte[] body, String changeId) {
        return Response.ok(body).header("Content-Type", Codec.CONTENT_TYPE).header("ETag", etag(changeId)).build();
    }

    /** 201 with the relative Location the design specifies, the new strong ETag and the created mission. */
    static Response created(byte[] body, String missionId, String changeId) {
        return Response.status(201).header("Location", "/missions/" + missionId).header("ETag", etag(changeId))
                .header("Content-Type", Codec.CONTENT_TYPE).entity(body).build();
    }

    static Response error(int status, String code, String message) {
        return Response.status(status).header("Content-Type", Codec.CONTENT_TYPE).entity(Codec.error(code, message)).build();
    }

    /** @param allow the methods the path supports, in the form of an Allow header value */
    static Response methodNotAllowed(String allow) {
        return Response.status(405).header("Allow", allow).header("Content-Type", Codec.CONTENT_TYPE)
                .entity(Codec.error("METHOD_NOT_ALLOWED", "Method not allowed; supported: " + allow)).build();
    }

    /** Bodyless: the frozen contract defines no body for 406, and none for an unknown path. */
    static Response bodyless(int status) {
        return Response.status(status).build();
    }

    private static String etag(String changeId) { return "\"" + changeId + "\""; }
}
