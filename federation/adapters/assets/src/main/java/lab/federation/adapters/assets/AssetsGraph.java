package lab.federation.adapters.assets;

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
import lab.federation.common.Json;
import lab.federation.common.MappingOutcome;
import lab.federation.common.Outcome;
import lab.federation.common.Outcomes;
import lab.federation.common.Resolution;
import org.springframework.boot.autoconfigure.graphql.GraphQlSourceBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.graphql.execution.DataFetcherExceptionResolverAdapter;
import org.springframework.graphql.execution.RuntimeWiringConfigurer;

/** The Federation wiring and the fetchers of the Assets subgraph. Federation features used: @key, @requires and @external only. */
@Configuration
public class AssetsGraph {
    static final int SERVICE_PAGE_LIMIT = 50;
    static final int MAX_LIMIT = 100;
    static final String NOT_FOUND_CODE = AssetReferenceEntity.NOT_FOUND_CODE;

    private final AssetsClient client;

    public AssetsGraph(AssetsClient client) {
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
    RuntimeWiringConfigurer assetsWiring() {
        return wiring -> wiring
                .type("Query", type -> type.dataFetcher("asset", this::asset).dataFetcher("assets", this::assets))
                .type("AssetReference", type -> type
                        .dataFetcher("resolution", environment -> reference(environment, (entity, outcome) -> outcome.resolution().name()))
                        .dataFetcher("asset", environment -> reference(environment, (entity, outcome) -> outcome.value())))
                .type("Asset", type -> type.dataFetcher("parent", this::parent));
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
                String type = (String) representation.get("__typename");
                if ("AssetReference".equals(type)) {
                    found.add(new AssetReferenceEntity(required(representation, "localRef"), required(representation, "release"),
                            optional(representation, "assetId"), mappingOutcome(representation)));
                } else if ("Asset".equals(type)) {
                    HttpResult result = client.asset(required(representation, "assetId"));
                    Outcome<Map<String, Object>> outcome = Outcomes.fromCall(result, NOT_FOUND_CODE, Json::object);
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

    /** A key field that may be absent or null (the identifier the mapping did not supply). */
    private static String optional(Map<String, Object> representation, String name) {
        Object value = representation.get(name);
        if (value != null && !(value instanceof String)) {
            throw new IllegalArgumentException("representation has a non-text " + name);
        }
        return (String) value;
    }

    /** The outcome the mapping subgraph stated. It is required: the adapter never infers it from a null assetId. */
    private static MappingOutcome mappingOutcome(Map<String, Object> representation) {
        try {
            return MappingOutcome.valueOf(required(representation, "mappingOutcome"));
        } catch (IllegalArgumentException error) {
            throw new IllegalArgumentException("representation has no valid mappingOutcome");
        }
    }

    private static TypeResolver entityType() {
        return environment -> environment.getObject() instanceof AssetReferenceEntity
                ? environment.getSchema().getObjectType("AssetReference")
                : environment.getSchema().getObjectType("Asset");
    }

    // ---- AssetReference --------------------------------------------------------------------------------------------

    private interface Pick {
        Object from(AssetReferenceEntity entity, Outcome<Map<String, Object>> outcome);
    }

    private DataFetcherResult<Object> reference(DataFetchingEnvironment environment, Pick pick) {
        AssetReferenceEntity entity = environment.getSource();
        Outcome<Map<String, Object>> outcome = entity.outcome(client);
        DataFetcherResult.Builder<Object> result = DataFetcherResult.newResult().data(pick.from(entity, outcome));
        if (outcome.resolution() == Resolution.UNAVAILABLE && entity.claimError()) {
            result.error(unavailable(outcome, environment));
        }
        return result.build();
    }

    // ---- Asset.parent ----------------------------------------------------------------------------------------------

    /**
     * The parent of an asset: ONE call to the service, made only when the client selects the field. No parent id gives null with no
     * call; a parent that does not exist gives null with no errors entry (not-found is data); a failed call gives null with one entry.
     * There is no caching and no batching: each level of a chain is one call.
     */
    private DataFetcherResult<Object> parent(DataFetchingEnvironment environment) {
        Map<String, Object> source = environment.getSource();
        Object parentId = source.get("parentAssetId");
        if (!(parentId instanceof String id)) {
            return DataFetcherResult.newResult().data(null).build();
        }
        Outcome<Map<String, Object>> outcome = Outcomes.fromCall(client.asset(id), NOT_FOUND_CODE, Json::object);
        DataFetcherResult.Builder<Object> answer = DataFetcherResult.newResult().data(outcome.value());
        if (outcome.resolution() == Resolution.UNAVAILABLE) {
            answer.error(unavailable(outcome, environment));
        }
        return answer.build();
    }

    // ---- Query -----------------------------------------------------------------------------------------------------

    private DataFetcherResult<Object> asset(DataFetchingEnvironment environment) {
        HttpResult result = client.asset(environment.getArgument("assetId"));
        if (result.status() == 400 && "INVALID_ASSET_ID".equals(Outcomes.serviceCode(result))) {
            return DataFetcherResult.newResult().error(FederationErrors.of(ErrorCode.BAD_USER_INPUT, "Malformed asset id", environment)).build();
        }
        Outcome<Map<String, Object>> outcome = Outcomes.fromCall(result, NOT_FOUND_CODE, Json::object);
        DataFetcherResult.Builder<Object> answer = DataFetcherResult.newResult().data(outcome.value());
        if (outcome.resolution() == Resolution.UNAVAILABLE) {
            answer.error(unavailable(outcome, environment));
        }
        return answer.build();
    }

    private DataFetcherResult<Object> assets(DataFetchingEnvironment environment) {
        int offset = environment.getArgument("offset");
        int limit = environment.getArgument("limit");
        if (offset < 0 || limit < 1 || limit > MAX_LIMIT) {
            return DataFetcherResult.newResult().error(FederationErrors.of(ErrorCode.BAD_USER_INPUT,
                    "offset must be 0 or more and limit from 1 to " + MAX_LIMIT, environment)).build();
        }
        Map<String, String> filters = new LinkedHashMap<>();
        for (String name : List.of("kind", "category", "status", "parentAssetId")) {
            Object value = environment.getArgument(name);
            filters.put(name, value == null ? null : value.toString());
        }
        List<Object> items = new ArrayList<>();
        // At most two calls (the service allows 50 per call); the second is made only when the first answered.
        for (int from = 0; from < limit; from += SERVICE_PAGE_LIMIT) {
            int size = Math.min(SERVICE_PAGE_LIMIT, limit - from);
            Outcome<List<Object>> outcome = Outcomes.fromCall(client.list(filters, offset + from, size), null, AssetsGraph::items);
            if (outcome.resolution() != Resolution.RESOLVED) {
                // All or nothing: the whole list is null, with one entry for the failed call.
                return DataFetcherResult.newResult().error(unavailable(outcome, environment)).build();
            }
            items.addAll(outcome.value());
        }
        return DataFetcherResult.newResult().data(items).build();
    }

    @SuppressWarnings("unchecked")
    private static List<Object> items(String body) {
        Object items = Json.object(body).get("items");
        if (!(items instanceof List<?>)) {
            throw new IllegalArgumentException("no items");
        }
        return (List<Object>) items;
    }

    private static GraphQLError unavailable(Outcome<?> outcome, DataFetchingEnvironment environment) {
        String message = outcome.errorCode() == ErrorCode.SERVICE_UNAVAILABLE
                ? "Assets service unavailable" : "Assets service answered something the adapter cannot use";
        return FederationErrors.of(outcome.errorCode(), message, environment);
    }
}
