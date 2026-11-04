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
                .type("Query", type -> type.dataFetcher("asset", this::asset).dataFetcher("assets", this::assets).dataFetcher("assetsPage", this::assetsPage))
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

    /** The deprecated list: the window only, with no count check, exactly as in 1.0.0. */
    private DataFetcherResult<Object> assets(DataFetchingEnvironment environment) {
        DataFetcherResult<Object> refused = refusedWindow(environment);
        if (refused != null) {
            return refused;
        }
        int offset = environment.getArgument("offset");
        int limit = environment.getArgument("limit");
        Map<String, String> filters = filters(environment);
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

    /**
     * The page field: the same calls and the same items as the list, with the service's total of the assets that match the filters
     * (independent of offset and limit), the offset and limit asked, and hasMore. All or nothing: a failed call or count metadata that
     * cannot be used makes the whole page null, with one entry. A page is a live view with no snapshot guarantee, as the service's
     * pages are: equal totals across the two calls of a page do not prove that the assets did not change between them.
     */
    private DataFetcherResult<Object> assetsPage(DataFetchingEnvironment environment) {
        DataFetcherResult<Object> refused = refusedWindow(environment);
        if (refused != null) {
            return refused;
        }
        int offset = environment.getArgument("offset");
        int limit = environment.getArgument("limit");
        Map<String, String> filters = filters(environment);
        List<Object> items = new ArrayList<>();
        Long total = null;
        for (int from = 0; from < limit; from += SERVICE_PAGE_LIMIT) {
            int size = Math.min(SERVICE_PAGE_LIMIT, limit - from);
            // The offset of the call is computed in long: offset + from can pass 2147483647 (the deprecated list keeps its int sum, as in 1.0.0).
            long callOffset = (long) offset + from;
            Outcome<Map<String, Object>> outcome = Outcomes.fromCall(client.list(filters, callOffset, size), null, Json::object);
            if (outcome.resolution() != Resolution.RESOLVED) {
                return DataFetcherResult.newResult().error(unavailable(outcome, environment)).build();
            }
            List<Object> rows;
            try {
                // A JSON null parses to no object at all: it is a body the adapter cannot use, like an answer without items.
                if (outcome.value() == null) {
                    throw new IllegalArgumentException("not a JSON object");
                }
                rows = items(outcome.value());
            } catch (IllegalArgumentException error) {
                return DataFetcherResult.newResult().error(unavailable(Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "no items"), environment)).build();
            }
            String fault = countFault(outcome.value(), rows.size(), callOffset, size, total);
            if (fault != null) {
                return DataFetcherResult.newResult().error(FederationErrors.of(ErrorCode.UPSTREAM_BAD_RESPONSE, COUNT_FAULT + fault, environment)).build();
            }
            total = ((Number) outcome.value().get("total")).longValue();
            items.addAll(rows);
        }
        Map<String, Object> page = new LinkedHashMap<>();
        page.put("items", items);
        page.put("totalCount", total.intValue());
        page.put("offset", offset);
        page.put("limit", limit);
        page.put("hasMore", (long) offset + items.size() < total);
        return DataFetcherResult.newResult().data(page).build();
    }

    static final String COUNT_FAULT = "Assets service answered count metadata the adapter cannot use: ";

    /**
     * Why the count metadata of one answer cannot be used, or null. total must be a JSON integer from 0 to 2147483647 (a GraphQL Int;
     * not a float, a string, a boolean or null), the same in every call of the page; the answer must echo the offset and limit asked;
     * and its rows must be exactly min(limit, max(0, total - offset)) for that call, which covers zero matches, pages beyond the end
     * and the last page.
     */
    static String countFault(Map<String, Object> answer, int rows, long callOffset, int callLimit, Long previousTotal) {
        Object value = answer.get("total");
        if (!(value instanceof Integer || value instanceof Long || value instanceof java.math.BigInteger)) {
            return value == null ? "total is missing or null" : "total is not a whole number";
        }
        java.math.BigInteger whole = value instanceof java.math.BigInteger big ? big : java.math.BigInteger.valueOf(((Number) value).longValue());
        if (whole.signum() < 0 || whole.compareTo(java.math.BigInteger.valueOf(Integer.MAX_VALUE)) > 0) {
            return "total is not from 0 to 2147483647";
        }
        long total = whole.longValue();
        if (previousTotal != null && previousTotal != total) {
            return "the calls of one page gave different totals";
        }
        if (!isWhole(answer.get("offset"), callOffset) || !isWhole(answer.get("limit"), callLimit)) {
            return "the offset or limit the service echoed is not the one asked";
        }
        if (rows != Math.min(callLimit, Math.max(0, total - callOffset))) {
            return "the number of assets on the page does not match total";
        }
        return null;
    }

    private static boolean isWhole(Object value, long expected) {
        return (value instanceof Integer || value instanceof Long) && ((Number) value).longValue() == expected;
    }

    /** BAD_USER_INPUT, with no call, for an offset below 0 or a limit outside 1 to 100; null when the window is valid. */
    private static DataFetcherResult<Object> refusedWindow(DataFetchingEnvironment environment) {
        int offset = environment.getArgument("offset");
        int limit = environment.getArgument("limit");
        if (offset < 0 || limit < 1 || limit > MAX_LIMIT) {
            return DataFetcherResult.newResult().error(FederationErrors.of(ErrorCode.BAD_USER_INPUT,
                    "offset must be 0 or more and limit from 1 to " + MAX_LIMIT, environment)).build();
        }
        return null;
    }

    private static Map<String, String> filters(DataFetchingEnvironment environment) {
        Map<String, String> filters = new LinkedHashMap<>();
        for (String name : List.of("kind", "category", "status", "parentAssetId")) {
            Object value = environment.getArgument(name);
            filters.put(name, value == null ? null : value.toString());
        }
        return filters;
    }

    private static List<Object> items(String body) {
        return items(Json.object(body));
    }

    @SuppressWarnings("unchecked")
    private static List<Object> items(Map<String, Object> answer) {
        Object items = answer.get("items");
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
