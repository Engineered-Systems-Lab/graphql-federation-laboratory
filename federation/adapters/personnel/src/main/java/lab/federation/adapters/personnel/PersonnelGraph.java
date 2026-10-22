package lab.federation.adapters.personnel;

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
import lab.federation.common.MappingOutcome;
import lab.federation.common.HttpResult;
import lab.federation.common.Outcome;
import lab.federation.common.Resolution;
import org.springframework.boot.autoconfigure.graphql.GraphQlSourceBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.graphql.execution.DataFetcherExceptionResolverAdapter;
import org.springframework.graphql.execution.RuntimeWiringConfigurer;

/** The Federation wiring and the fetchers of the Personnel subgraph. Federation features used: @key, @requires and @external only. */
@Configuration
public class PersonnelGraph {
    static final int MAX_LIMIT = 100;

    private final PersonnelClient client;
    private final PersonnelSnapshots snapshots;

    public PersonnelGraph(PersonnelClient client, PersonnelSnapshots snapshots) {
        this.client = client;
        this.snapshots = snapshots;
    }

    @Bean
    GraphQlSourceBuilderCustomizer federation() {
        return builder -> builder.schemaFactory((registry, wiring) -> Federation.transform(registry, wiring)
                .fetchEntities(entities())
                .resolveEntityType(entityType())
                .build());
    }

    @Bean
    RuntimeWiringConfigurer personnelWiring() {
        return wiring -> wiring
                .type("Query", type -> type.dataFetcher("personnel", this::personnel).dataFetcher("personnelMembers", this::personnelMembers))
                .type("PersonnelDetails", type -> type.typeResolver(detailsType()))
                .type("PersonnelReference", type -> type
                        .dataFetcher("resolution", environment -> reference(environment, (entity, outcome) -> outcome.resolution().name()))
                        .dataFetcher("personnel", environment -> reference(environment, (entity, outcome) -> outcome.value())));
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
            // One lookup for the whole batch: it asks the service once, and only when a lookup is needed, whatever the batch holds.
            PersonnelLookup lookup = new PersonnelLookup(client, snapshots);
            for (Map<String, Object> representation : representations) {
                String type = (String) representation.get("__typename");
                if ("PersonnelReference".equals(type)) {
                    found.add(new PersonnelReferenceEntity(required(representation, "localRef"), required(representation, "release"),
                            optional(representation, "personnelId"), mappingOutcome(representation), lookup));
                } else if ("Personnel".equals(type)) {
                    String id = required(representation, "personnelId");
                    Outcome<Map<String, Object>> outcome = PersonnelClient.sendable(id)
                            ? lookup.member(id)
                            : Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "The personnelId cannot be used");
                    found.add(outcome.value());
                    if (outcome.resolution() == Resolution.UNAVAILABLE) {
                        errors.add(unavailable(outcome, environment));
                    }
                } else {
                    throw new IllegalArgumentException("unknown entity type");
                }
            }
            return DataFetcherResult.newResult().data(found).errors(errors).build();
        };
    }

    private static String required(Map<String, Object> representation, String name) {
        Object value = representation.get(name);
        if (!(value instanceof String text)) {
            throw new IllegalArgumentException("representation lacks " + name);
        }
        return text;
    }

    /** A key field that may be absent or null (the id the mapping subgraph did not supply). */
    private static String optional(Map<String, Object> representation, String name) {
        Object value = representation.get(name);
        if (value != null && !(value instanceof String)) {
            throw new IllegalArgumentException("representation has a non-text " + name);
        }
        return (String) value;
    }

    /** The outcome the mapping subgraph stated. It is required: the adapter never infers it from a null personnelId. */
    private static MappingOutcome mappingOutcome(Map<String, Object> representation) {
        try {
            return MappingOutcome.valueOf(required(representation, "mappingOutcome"));
        } catch (IllegalArgumentException error) {
            throw new IllegalArgumentException("representation has no valid mappingOutcome");
        }
    }

    private static TypeResolver entityType() {
        return environment -> environment.getObject() instanceof PersonnelReferenceEntity
                ? environment.getSchema().getObjectType("PersonnelReference")
                : environment.getSchema().getObjectType("Personnel");
    }

    /** The union of the contract's choice: crew details always hold a rank; civilian details hold nothing. */
    private static TypeResolver detailsType() {
        return environment -> {
            Map<?, ?> details = (Map<?, ?>) environment.getObject();
            return environment.getSchema().getObjectType(details.containsKey("rank") ? "CrewDetails" : "CivilianDetails");
        };
    }

    // ---- PersonnelReference ----------------------------------------------------------------------------------------

    private interface Pick {
        Object from(PersonnelReferenceEntity entity, Outcome<Map<String, Object>> outcome);
    }

    private DataFetcherResult<Object> reference(DataFetchingEnvironment environment, Pick pick) {
        PersonnelReferenceEntity entity = environment.getSource();
        Outcome<Map<String, Object>> outcome = entity.outcome();
        DataFetcherResult.Builder<Object> result = DataFetcherResult.newResult().data(pick.from(entity, outcome));
        if (outcome.resolution() == Resolution.UNAVAILABLE && entity.claimError()) {
            result.error(unavailable(outcome, environment));
        }
        return result.build();
    }

    // ---- Query -----------------------------------------------------------------------------------------------------

    private DataFetcherResult<Object> personnel(DataFetchingEnvironment environment) {
        String id = environment.getArgument("personnelId");
        if (!PersonnelClient.sendable(id)) {
            return DataFetcherResult.newResult().error(FederationErrors.of(ErrorCode.BAD_USER_INPUT, "Malformed personnelId", environment)).build();
        }
        HttpResult result = client.get(id);
        if (PersonnelCalls.invalidRequest(result)) {
            return DataFetcherResult.newResult().error(FederationErrors.of(ErrorCode.BAD_USER_INPUT, "Malformed personnelId", environment)).build();
        }
        Outcome<Map<String, Object>> outcome = PersonnelCalls.member(result, id);
        DataFetcherResult.Builder<Object> answer = DataFetcherResult.newResult().data(outcome.value());
        if (outcome.resolution() == Resolution.UNAVAILABLE) {
            answer.error(unavailable(outcome, environment));
        }
        return answer.build();
    }

    private DataFetcherResult<Object> personnelMembers(DataFetchingEnvironment environment) {
        // A client may send null for either (the schema defaults apply to an absent argument, not to a null one): null means the default.
        Integer askedOffset = environment.getArgument("offset");
        Integer askedLimit = environment.getArgument("limit");
        int offset = askedOffset == null ? 0 : askedOffset;
        int limit = askedLimit == null ? 20 : askedLimit;
        if (offset < 0 || limit < 1 || limit > MAX_LIMIT) {
            return DataFetcherResult.newResult().error(FederationErrors.of(ErrorCode.BAD_USER_INPUT,
                    "offset must be 0 or more and limit from 1 to " + MAX_LIMIT, environment)).build();
        }
        Object department = environment.getArgument("department");
        Object dutyStatus = environment.getArgument("dutyStatus");
        // The service allows 100 per call, so a page is ONE call. All or nothing: a failed call makes the whole result null, with one entry.
        Outcome<Map<String, Object>> outcome = PersonnelCalls.outcome(
                client.list(department == null ? null : department.toString(), dutyStatus == null ? null : dutyStatus.toString(), offset, limit),
                body -> page(PersonnelXml.page(body), offset, limit));
        if (outcome.resolution() == Resolution.RESOLVED) {
            return DataFetcherResult.newResult().data(outcome.value()).build();
        }
        // A list has no "not found": that fault on a list call is something the adapter cannot use.
        ErrorCode code = outcome.errorCode() == null ? ErrorCode.UPSTREAM_BAD_RESPONSE : outcome.errorCode();
        return DataFetcherResult.newResult().error(unavailable(Outcome.unavailable(code, outcome.message()), environment)).build();
    }

    /** The page as the GraphQL type; it must echo the offset and the limit that were asked for, or the answer is not this call's. */
    private static Map<String, Object> page(PersonnelXml.Page page, int offset, int limit) {
        if (page.offset() != offset || page.limit() != limit) {
            throw new IllegalArgumentException("the service answered another page");
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("datasetVersion", page.datasetVersion());
        result.put("items", page.members());
        result.put("totalCount", page.totalCount());
        result.put("offset", page.offset());
        result.put("limit", page.limit());
        result.put("hasMore", page.hasMore());
        return result;
    }

    private static GraphQLError unavailable(Outcome<?> outcome, DataFetchingEnvironment environment) {
        String message = outcome.errorCode() == ErrorCode.SERVICE_UNAVAILABLE
                ? "Personnel service unavailable" : "Personnel service answered something the adapter cannot use";
        return FederationErrors.of(outcome.errorCode(), message, environment);
    }
}
