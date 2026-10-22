package lab.federation.adapters.mapping;

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
import org.springframework.boot.autoconfigure.graphql.GraphQlSourceBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.graphql.execution.DataFetcherExceptionResolverAdapter;
import org.springframework.graphql.execution.RuntimeWiringConfigurer;

/**
 * The Federation wiring of the mapping subgraph. Federation features used: @key, and @inaccessible on the two plain lookups. The entity
 * AssetReference is keyed by { localRef release }; it contributes assetId from the named release and ALWAYS states what the mapping
 * did in mappingOutcome: MAPPED (the release has an entry), NO_ENTRY (a valid release without an entry, or without a section for the
 * kind) or RELEASE_REFUSED. The entity PersonnelReference has the same key and contributes personnelId from the crew section and the
 * same mappingOutcome. The owning adapters read the outcome through @requires instead of inferring it from a null identifier.
 * There is no implicit latest: a representation whose release is missing or blank is refused with MAPPING_RELEASE_REQUIRED and an
 * unknown release with MAPPING_RELEASE_NOT_FOUND; the errors entry stays and the entity is still returned, with RELEASE_REFUSED. A
 * GraphQL String! argument already keeps a null release away from the router's queries, but an empty string passes it, and a direct
 * call to _entities can omit the field, so the adapter checks both itself.
 *
 * <p>The plain lookups Query.assetReferences and Query.personnelReferences answer a client that calls this adapter directly, with the
 * entity's answer for each reference: the same code, so the same fields, outcomes and release rules. They are @inaccessible, so the
 * supergraph a router serves does not change. They add one rule the entities do not apply: the personnel lookup refuses an outsider
 * reference (O-n) by class (D048) and does not resolve a participant reference (P-n), each with NO_ENTRY and MAPPING_CLASS_REFUSED.
 * The entities are unchanged.
 */
@Configuration
public class MappingGraph {
    static final String ASSET_REFERENCE = "AssetReference";
    static final String PERSONNEL_REFERENCE = "PersonnelReference";
    /** The most references one lookup answers, the page limit of the other adapters' queries. */
    static final int LOOKUP_LIMIT = 100;
    /** Not a schema field: it only tells the type resolver which entity type a returned map stands for. */
    private static final String TYPE_KEY = "typename$";

    private final MappingReleases releases;

    public MappingGraph(MappingReleases releases) {
        this.releases = releases;
    }

    @Bean
    GraphQlSourceBuilderCustomizer federation() {
        return builder -> builder.schemaFactory((registry, wiring) -> Federation.transform(registry, wiring)
                .fetchEntities(entities())
                .resolveEntityType(entityType())
                .build());
    }

    @Bean
    RuntimeWiringConfigurer mappingWiring() {
        return wiring -> wiring.type("Query", type -> type
                .dataFetcher("mappingReleases", environment -> describe())
                .dataFetcher("assetReferences", lookup(ASSET_REFERENCE))
                .dataFetcher("personnelReferences", lookup(PERSONNEL_REFERENCE)));
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

    private DataFetcher<Object> entities() {
        return environment -> {
            List<Map<String, Object>> representations = environment.getArgument(_Entity.argumentName);
            List<Object> found = new ArrayList<>();
            // One errors entry per failed cause, however many representations share it.
            Map<String, GraphQLError> errors = new LinkedHashMap<>();
            for (Map<String, Object> representation : representations) {
                Object typename = representation.get("__typename");
                if (!ASSET_REFERENCE.equals(typename) && !PERSONNEL_REFERENCE.equals(typename)) {
                    throw new IllegalArgumentException("unknown entity type");
                }
                String localRef = required(representation, "localRef");
                Object requested = representation.get("release");
                found.add(answer((String) typename, localRef, requested instanceof String text ? text : null, false, errors, environment));
            }
            return DataFetcherResult.newResult().data(found).errors(new ArrayList<>(errors.values())).build();
        };
    }

    /** A plain lookup: the entity's answer for each reference, in the order given, with one errors entry per failed cause. */
    private DataFetcher<Object> lookup(String typename) {
        return environment -> {
            String release = environment.getArgument("release");
            List<String> localRefs = environment.getArgument("localRefs");
            if (localRefs.size() > LOOKUP_LIMIT) {
                return DataFetcherResult.newResult().error(FederationErrors.of(ErrorCode.BAD_USER_INPUT,
                        "At most " + LOOKUP_LIMIT + " references in one call", environment)).build();
            }
            List<Object> found = new ArrayList<>();
            Map<String, GraphQLError> errors = new LinkedHashMap<>();
            for (String localRef : localRefs) {
                found.add(answer(typename, localRef, release, true, errors, environment));
            }
            return DataFetcherResult.newResult().data(found).errors(new ArrayList<>(errors.values())).build();
        };
    }

    /**
     * The answer for one reference in the named release: the entity with its identifier and mappingOutcome. The release rules come
     * first. When byClass is set (the plain lookups), a personnel reference of the outsider or participant class is not looked up.
     */
    private Map<String, Object> answer(String typename, String localRef, String name, boolean byClass, Map<String, GraphQLError> errors,
                                       DataFetchingEnvironment environment) {
        Map<String, Object> entity = new LinkedHashMap<>();
        entity.put("localRef", localRef);
        entity.put(TYPE_KEY, typename);
        if (name == null || name.isBlank()) {
            errors.computeIfAbsent("required", key -> FederationErrors.of(ErrorCode.MAPPING_RELEASE_REQUIRED,
                    "A mapping release is required; there is no implicit latest", environment));
            refused(entity, name);
            return entity;
        }
        MappingReleases.Release release = releases.find(name);
        if (release == null) {
            errors.computeIfAbsent("not-found:" + name, key -> FederationErrors.of(ErrorCode.MAPPING_RELEASE_NOT_FOUND,
                    "Mapping release not found", environment));
            refused(entity, name);
            return entity;
        }
        entity.put("release", release.release());
        if (ASSET_REFERENCE.equals(typename)) {
            String mapped = release.assetId(localRef);
            entity.put("assetId", mapped);
            entity.put("mappingOutcome", (mapped == null ? MappingOutcome.NO_ENTRY : MappingOutcome.MAPPED).name());
            return entity;
        }
        String refusal = byClass ? refusedClass(localRef) : null;
        if (refusal != null) {
            errors.computeIfAbsent("class:" + refusal, key -> FederationErrors.of(ErrorCode.MAPPING_CLASS_REFUSED, refusal, environment));
            entity.put("personnelId", null);
            entity.put("mappingOutcome", MappingOutcome.NO_ENTRY.name());
            return entity;
        }
        // The crew section of the named release; no entry when it has none (release 1.0) or has none for the reference.
        String mapped = release.personnelId(localRef);
        entity.put("personnelId", mapped);
        entity.put("mappingOutcome", (mapped == null ? MappingOutcome.NO_ENTRY : MappingOutcome.MAPPED).name());
        return entity;
    }

    /** Why the personnel lookup does not look a reference up, by its class letter, or null for any other reference. */
    static String refusedClass(String localRef) {
        if (localRef.startsWith("O-")) {
            return "An outsider reference (O-n) is refused by class and never maps to Personnel";
        }
        if (localRef.startsWith("P-")) {
            return "A participant reference (P-n) is not resolved by the graph; the lookup resolves crew references (C-n) only";
        }
        return null;
    }

    /** A refused release: the entity is still returned, with the outcome stated, so that no owning adapter has to guess it from a null id. */
    private static void refused(Map<String, Object> entity, String requestedRelease) {
        entity.put("release", requestedRelease == null ? "" : requestedRelease);
        entity.put("mappingOutcome", MappingOutcome.RELEASE_REFUSED.name());
    }

    private static String required(Map<String, Object> representation, String name) {
        if (!(representation.get(name) instanceof String text)) {
            throw new IllegalArgumentException("representation lacks " + name);
        }
        return text;
    }

    private static TypeResolver entityType() {
        return environment -> environment.getSchema().getObjectType((String) ((Map<?, ?>) environment.getObject()).get(TYPE_KEY));
    }

    private List<Map<String, Object>> describe() {
        List<Map<String, Object>> described = new ArrayList<>();
        for (MappingReleases.Release release : releases.all()) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("release", release.release());
            item.put("sections", new ArrayList<>(release.sections().keySet()));
            item.put("checkedAgainst", release.checkedAgainst());
            described.add(item);
        }
        return described;
    }
}
