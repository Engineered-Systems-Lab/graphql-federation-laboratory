package lab.federation.adapters.missions;

import com.apollographql.federation.graphqljava.Federation;
import com.apollographql.federation.graphqljava._Entity;
import graphql.GraphQLError;
import graphql.execution.DataFetcherResult;
import graphql.schema.DataFetcher;
import graphql.schema.DataFetchingEnvironment;
import graphql.schema.TypeResolver;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import lab.federation.common.ErrorCode;
import lab.federation.common.FederationErrors;
import lab.federation.common.HttpResult;
import lab.federation.common.Outcome;
import lab.federation.common.Outcomes;
import lab.federation.common.Resolution;
import org.springframework.boot.autoconfigure.graphql.GraphQlSourceBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.graphql.execution.DataFetcherExceptionResolverAdapter;
import org.springframework.graphql.execution.RuntimeWiringConfigurer;

/** The Federation wiring and the fetchers of the Missions subgraph. Federation feature used: @key only (with resolvable: false). */
@Configuration
public class MissionsGraph {
    static final int MAX_LIMIT = 100;
    static final String NOT_FOUND_CODE = "MISSION_NOT_FOUND";
    static final String BAD_ID_CODE = "INVALID_MISSION_ID";
    static final String BAD_REQUEST_CODE = "INVALID_REQUEST";
    static final List<String> FILTERS = List.of("type", "classification", "status", "priority", "issuingAuthority", "commandingOfficerId",
            "assignedCrewId", "assignedAssetId", "locationType");

    private final MissionsClient client;

    public MissionsGraph(MissionsClient client) {
        this.client = client;
    }

    @Bean
    GraphQlSourceBuilderCustomizer federation() {
        return builder -> builder.schemaFactory((registry, wiring) -> Federation.transform(registry, wiring)
                .fetchEntities(entities())
                .resolveEntityType(entityType())
                .build());
    }

    @Bean
    RuntimeWiringConfigurer missionsWiring() {
        return wiring -> wiring
                .type("Query", type -> type.dataFetcher("mission", this::mission).dataFetcher("missions", this::missions))
                .type("Mission", type -> type.dataFetcher("assets", MissionsGraph::assets).dataFetcher("crew", MissionsGraph::crew)
                        .dataFetcher("commandingOfficer", MissionsGraph::commandingOfficer));
    }

    /** An adapter fault is INTERNAL_SERVER_ERROR, not the framework's default text. */
    @Bean
    DataFetcherExceptionResolverAdapter internalErrors() {
        return new DataFetcherExceptionResolverAdapter() {
            @Override
            protected GraphQLError resolveToSingleError(Throwable error, DataFetchingEnvironment environment) {
                return FederationErrors.of(ErrorCode.INTERNAL_SERVER_ERROR, "Internal adapter error", environment);
            }
        };
    }

    // ---- entities --------------------------------------------------------------------------------------------------

    private DataFetcher<Object> entities() {
        return environment -> {
            List<Map<String, Object>> representations = environment.getArgument(_Entity.argumentName);
            List<Object> found = new ArrayList<>();
            List<GraphQLError> errors = new ArrayList<>();
            for (Map<String, Object> representation : representations) {
                if (!"Mission".equals(representation.get("__typename"))) {
                    throw new IllegalArgumentException("unknown entity type");
                }
                Object id = representation.get("missionId");
                if (!(id instanceof String missionId)) {
                    throw new IllegalArgumentException("representation lacks missionId");
                }
                // Not found is null with no entry, as the router expects of an unknown key; any failure adds one entry.
                Outcome<Map<String, Object>> outcome = fetchMission(missionId);
                found.add(outcome.value());
                if (outcome.resolution() == Resolution.UNAVAILABLE) {
                    errors.add(failure(outcome, environment));
                }
            }
            return DataFetcherResult.newResult().data(found).errors(errors).build();
        };
    }

    private static TypeResolver entityType() {
        return environment -> environment.getSchema().getObjectType("Mission");
    }

    // ---- Query -----------------------------------------------------------------------------------------------------

    private DataFetcherResult<Object> mission(DataFetchingEnvironment environment) {
        Outcome<Map<String, Object>> outcome = fetchMission(environment.getArgument("missionId"));
        DataFetcherResult.Builder<Object> answer = DataFetcherResult.newResult().data(outcome.value());
        if (outcome.resolution() == Resolution.UNAVAILABLE) {
            answer.error(failure(outcome, environment));
        }
        return answer.build();
    }

    /**
     * ONE call. 200 gives the mission; a 404 with the code MISSION_NOT_FOUND is UNRESOLVED, which the graph shows as null with no entry;
     * a 400 with INVALID_MISSION_ID is the client's malformed id (BAD_USER_INPUT); a 5xx or no answer is SERVICE_UNAVAILABLE; anything
     * else, a 404 without that code included (an unknown path answers a bodyless 404), is UPSTREAM_BAD_RESPONSE.
     */
    private Outcome<Map<String, Object>> fetchMission(String missionId) {
        if (!isOneSegment(missionId)) {
            return Outcome.unavailable(ErrorCode.BAD_USER_INPUT, "Malformed mission id");
        }
        HttpResult result = client.mission(missionId);
        if (isBadRequest(result, BAD_ID_CODE)) {
            return Outcome.unavailable(ErrorCode.BAD_USER_INPUT, "Malformed mission id");
        }
        Outcome<Map<String, Object>> outcome = Outcomes.fromCall(result, NOT_FOUND_CODE, MissionXml::mission, MissionXml::errorCode);
        if (outcome.resolution() == Resolution.RESOLVED && !missionId.equals(outcome.value().get("missionId"))) {
            return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "The service answered another mission than the one asked");
        }
        return outcome;
    }

    /**
     * An id that cannot be one path segment (it holds a slash or a backslash, or is empty, "." or "..") is the client's malformed id and
     * is never sent: the service's container would answer it with something that is not the contract's INVALID_MISSION_ID. The
     * grammar of a mission id itself stays the service's to judge.
     */
    static boolean isOneSegment(String id) {
        return !id.isEmpty() && !id.equals(".") && !id.equals("..") && id.indexOf('/') < 0 && id.indexOf('\\') < 0;
    }

    private static boolean isBadRequest(HttpResult result, String code) {
        return !result.failed() && result.status() == 400 && code.equals(MissionXml.errorCode(result));
    }

    private DataFetcherResult<Object> missions(DataFetchingEnvironment environment) {
        int offset = environment.getArgument("offset");
        int limit = environment.getArgument("limit");
        if (offset < 0 || limit < 1 || limit > MAX_LIMIT) {
            return DataFetcherResult.newResult().error(FederationErrors.of(ErrorCode.BAD_USER_INPUT,
                    "offset must be 0 or more and limit from 1 to " + MAX_LIMIT, environment)).build();
        }
        Map<String, String> filters = new LinkedHashMap<>();
        for (String name : FILTERS) {
            Object value = environment.getArgument(name);
            filters.put(name, value == null ? null : value.toString());
        }
        MissionPaging.Result result = MissionPaging.fetch(offset, limit, (page, pageSize) -> pageOf(client.list(filters, page, pageSize)));
        if (result.failed()) {
            // All or nothing: the whole list is null, with one entry for the call that failed.
            return DataFetcherResult.newResult().error(failure(result.failure(), environment)).build();
        }
        return DataFetcherResult.newResult().data(new ArrayList<Object>(result.missions())).build();
    }

    /** A 400 with INVALID_REQUEST can only come from a filter value, because the adapter's own page and pageSize are valid. */
    private static Outcome<MissionXml.Page> pageOf(HttpResult result) {
        if (isBadRequest(result, BAD_REQUEST_CODE)) {
            return Outcome.unavailable(ErrorCode.BAD_USER_INPUT, "A filter value is not valid");
        }
        return Outcomes.fromCall(result, null, MissionXml::page, MissionXml::errorCode);
    }

    // ---- Mission.assets --------------------------------------------------------------------------------------------

    /** One AssetReference stub per assigned asset: the reference as stored and the release the client named. No call is made. */
    private static List<Map<String, Object>> assets(DataFetchingEnvironment environment) {
        return references(environment, "assignedAssetIds");
    }

    /** One PersonnelReference stub per assigned crew member (assignedCrewIds only), built the same way. No call is made. */
    private static List<Map<String, Object>> crew(DataFetchingEnvironment environment) {
        return references(environment, "assignedCrewIds");
    }

    /** The commanding officer as one PersonnelReference stub built the same way, or null when the mission has none. No call is made. */
    private static Map<String, Object> commandingOfficer(DataFetchingEnvironment environment) {
        Map<String, Object> mission = environment.getSource();
        Object localRef = mission.get("commandingOfficerId");
        if (localRef == null) {
            return null;
        }
        Map<String, Object> reference = new LinkedHashMap<>();
        reference.put("localRef", localRef);
        reference.put("release", environment.getArgument("release"));
        return reference;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> references(DataFetchingEnvironment environment, String field) {
        Map<String, Object> mission = environment.getSource();
        String release = environment.getArgument("release");
        List<Map<String, Object>> references = new ArrayList<>();
        for (String localRef : (List<String>) mission.get(field)) {
            Map<String, Object> reference = new LinkedHashMap<>();
            reference.put("localRef", localRef);
            reference.put("release", release);
            references.add(reference);
        }
        return references;
    }

    private static GraphQLError failure(Outcome<?> outcome, DataFetchingEnvironment environment) {
        String message = switch (outcome.errorCode()) {
            case SERVICE_UNAVAILABLE -> "Missions service unavailable";
            case BAD_USER_INPUT -> outcome.message();
            default -> "Missions service answered something the adapter cannot use";
        };
        return FederationErrors.of(outcome.errorCode(), message, environment);
    }
}
