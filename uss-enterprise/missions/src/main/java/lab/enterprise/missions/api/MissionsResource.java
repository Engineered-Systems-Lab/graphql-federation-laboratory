package lab.enterprise.missions.api;

import java.io.IOException;
import java.io.InputStream;
import java.sql.SQLException;
import javax.inject.Inject;
import javax.ws.rs.GET;
import javax.ws.rs.POST;
import javax.ws.rs.PUT;
import javax.ws.rs.Path;
import javax.ws.rs.PathParam;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.HttpHeaders;
import javax.ws.rs.core.Response;
import javax.ws.rs.core.UriInfo;
import lab.enterprise.missions.ApiException;
import lab.enterprise.missions.domain.MissionRules;
import lab.enterprise.missions.repository.MissionRepository;
import lab.enterprise.missions.xml.ChangeList;
import lab.enterprise.missions.xml.Codec;
import lab.enterprise.missions.xml.MissionList;

/**
 * The Missions resource: list, get and change log, then create and replace. Processing is fail-fast in a natural
 * pipeline, the first failure answers and nothing is aggregated: path and method, Accept and body media type (both in
 * {@link RouteFilter}), mission id, mutation headers, If-Match, body, domain rules, then the database transaction
 * (404, 412, provenance, write).
 */
@Path("missions")
public final class MissionsResource {
    /** A mission is a few kilobytes; a body far beyond any valid one is refused before it is parsed. */
    private static final int BODY_LIMIT = 8 * 1024 * 1024;

    private final MissionRepository repository;

    @Inject
    public MissionsResource(MissionRepository repository) { this.repository = repository; }

    @GET
    public Response list(@Context UriInfo uri) throws SQLException {
        Query.MissionQuery query = Query.missions(uri.getQueryParameters());
        var result = repository.list(query);
        var list = new MissionList();
        fill(list, query.paging(), result.totalCount());
        list.getMission().addAll(result.items());
        return Responses.xml(Codec.missionList(list));
    }

    @POST
    public Response create(@Context HttpHeaders headers, InputStream body) throws SQLException, IOException {
        MutationHeaders audit = MutationHeaders.parse(headers::getRequestHeader);
        var mission = Codec.parseMission(read(body));
        MissionRules.validate(mission, MissionRules.Role.CREATE, null);
        var created = repository.create(mission, audit);
        return Responses.created(Codec.mission(created.mission()), created.mission().getMissionId(), created.changeId());
    }

    @GET
    @Path("{id}")
    public Response get(@PathParam("id") String id) throws SQLException {
        requireValidId(id);
        var found = repository.get(id);
        if (found == null) throw notFound(id);
        return Responses.mission(Codec.mission(found.mission()), found.changeId());
    }

    @PUT
    @Path("{id}")
    public Response replace(@PathParam("id") String id, @Context HttpHeaders headers, InputStream body) throws SQLException, IOException {
        requireValidId(id);
        MutationHeaders audit = MutationHeaders.parse(headers::getRequestHeader);
        String expectedChangeId = IfMatch.changeId(headers.getRequestHeader("If-Match"));
        var mission = Codec.parseMission(read(body));
        MissionRules.validate(mission, MissionRules.Role.REPLACE, id);
        var replaced = repository.replace(id, expectedChangeId, mission, audit);
        return Responses.mission(Codec.mission(replaced.mission()), replaced.changeId());
    }

    @GET
    @Path("{id}/changes")
    public Response changes(@PathParam("id") String id, @Context UriInfo uri) throws SQLException {
        requireValidId(id);
        Query.Paging paging = Query.changes(uri.getQueryParameters());
        var result = repository.changes(id, paging);
        if (result == null) throw notFound(id);
        var list = new ChangeList();
        fill(list, paging, result.totalCount());
        list.getChange().addAll(result.items());
        return Responses.xml(Codec.changeList(list));
    }

    private static byte[] read(InputStream body) throws IOException {
        if (body == null) return new byte[0];
        byte[] bytes = body.readNBytes(BODY_LIMIT + 1);
        if (bytes.length > BODY_LIMIT) throw ApiException.invalidRequest("The request body is too large");
        return bytes;
    }

    private static void requireValidId(String id) {
        if (!Query.validMissionId(id)) throw new ApiException(400, "INVALID_MISSION_ID", "Malformed mission ID");
    }

    private static ApiException notFound(String id) {
        return new ApiException(404, "MISSION_NOT_FOUND", "No mission " + id);
    }

    private static long totalPages(long total, int size) { return (total + size - 1) / size; }

    private static void fill(MissionList list, Query.Paging paging, long total) {
        list.setPage(paging.pageText());
        list.setPageSize(Integer.toString(paging.pageSize()));
        list.setTotalCount(Long.toString(total));
        list.setTotalPages(Long.toString(totalPages(total, paging.pageSize())));
    }

    private static void fill(ChangeList list, Query.Paging paging, long total) {
        list.setPage(paging.pageText());
        list.setPageSize(Integer.toString(paging.pageSize()));
        list.setTotalCount(Long.toString(total));
        list.setTotalPages(Long.toString(totalPages(total, paging.pageSize())));
    }
}
