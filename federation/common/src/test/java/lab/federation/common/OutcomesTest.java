package lab.federation.common;

import static org.assertj.core.api.Assertions.assertThat;

import graphql.ExecutionInput;
import graphql.GraphQL;
import graphql.GraphQLError;
import graphql.schema.DataFetchingEnvironment;
import graphql.schema.idl.RuntimeWiring;
import graphql.schema.idl.SchemaGenerator;
import graphql.schema.idl.SchemaParser;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class OutcomesTest {
    private static final String NOT_FOUND = "{\"code\":\"ASSET_NOT_FOUND\",\"message\":\"no\"}";

    @Test
    void a200IsResolvedWithTheObject() {
        Outcome<Map<String, Object>> outcome = Outcomes.fromCall(HttpResult.answer(200, "{\"assetId\":\"AST-0001\"}"), "ASSET_NOT_FOUND", Json::object);
        assertThat(outcome.resolution()).isEqualTo(Resolution.RESOLVED);
        assertThat(outcome.value()).containsEntry("assetId", "AST-0001");
        assertThat(outcome.errorCode()).isNull();
    }

    @Test
    void a404WithTheNotFoundCodeIsUnresolved() {
        Outcome<Map<String, Object>> outcome = Outcomes.fromCall(HttpResult.answer(404, NOT_FOUND), "ASSET_NOT_FOUND", Json::object);
        assertThat(outcome.resolution()).isEqualTo(Resolution.UNRESOLVED);
        assertThat(outcome.value()).isNull();
        assertThat(outcome.errorCode()).isNull();
    }

    @Test
    void aPathNotFoundIsNeverUnresolved() {
        Outcome<Map<String, Object>> outcome = Outcomes.fromCall(HttpResult.answer(404, "{\"code\":\"PATH_NOT_FOUND\",\"message\":\"no\"}"), "ASSET_NOT_FOUND", Json::object);
        assertThat(outcome.resolution()).isEqualTo(Resolution.UNAVAILABLE);
        assertThat(outcome.errorCode()).isEqualTo(ErrorCode.UPSTREAM_BAD_RESPONSE);
    }

    @Test
    void a404WithAnUnreadableBodyIsUnavailable() {
        assertThat(Outcomes.fromCall(HttpResult.answer(404, "<html>"), "ASSET_NOT_FOUND", Json::object).resolution()).isEqualTo(Resolution.UNAVAILABLE);
        assertThat(Outcomes.fromCall(HttpResult.answer(404, null), "ASSET_NOT_FOUND", Json::object).resolution()).isEqualTo(Resolution.UNAVAILABLE);
    }

    @Test
    void aFiveHundredAndAFailureAreServiceUnavailable() {
        for (HttpResult result : new HttpResult[] {HttpResult.answer(500, "{}"), HttpResult.answer(503, null), HttpResult.failed(new java.io.IOException("down"))}) {
            Outcome<Map<String, Object>> outcome = Outcomes.fromCall(result, "ASSET_NOT_FOUND", Json::object);
            assertThat(outcome.resolution()).isEqualTo(Resolution.UNAVAILABLE);
            assertThat(outcome.errorCode()).isEqualTo(ErrorCode.SERVICE_UNAVAILABLE);
        }
    }

    @Test
    void anotherFourHundredOrAMalformedTwoHundredIsAnUpstreamBadResponse() {
        assertThat(Outcomes.fromCall(HttpResult.answer(400, "{\"code\":\"INVALID_ASSET_ID\"}"), "ASSET_NOT_FOUND", Json::object).errorCode()).isEqualTo(ErrorCode.UPSTREAM_BAD_RESPONSE);
        assertThat(Outcomes.fromCall(HttpResult.answer(302, ""), "ASSET_NOT_FOUND", Json::object).errorCode()).isEqualTo(ErrorCode.UPSTREAM_BAD_RESPONSE);
        Outcome<Map<String, Object>> malformed = Outcomes.fromCall(HttpResult.answer(200, "[1]"), "ASSET_NOT_FOUND", Json::object);
        assertThat(malformed.resolution()).isEqualTo(Resolution.UNAVAILABLE);
        assertThat(malformed.errorCode()).isEqualTo(ErrorCode.UPSTREAM_BAD_RESPONSE);
    }

    @Test
    void aNullNotFoundCodeNeverGivesUnresolved() {
        assertThat(Outcomes.fromCall(HttpResult.answer(404, NOT_FOUND), null, Json::object).resolution()).isEqualTo(Resolution.UNAVAILABLE);
    }

    @Test
    void aServiceWhoseErrorsAreNotJsonSuppliesItsOwnCodeReader() {
        java.util.function.Function<HttpResult, String> xmlCode = result -> result.body() != null && result.body().contains("<code>GONE</code>") ? "GONE" : null;
        Outcome<String> unresolved = Outcomes.fromCall(HttpResult.answer(404, "<error><code>GONE</code></error>"), "GONE", body -> body, xmlCode);
        assertThat(unresolved.resolution()).isEqualTo(Resolution.UNRESOLVED);
        assertThat(Outcomes.fromCall(HttpResult.answer(404, "<error><code>OTHER</code></error>"), "GONE", body -> body, xmlCode).errorCode())
                .isEqualTo(ErrorCode.UPSTREAM_BAD_RESPONSE);
        assertThat(Outcomes.fromCall(HttpResult.answer(200, "<mission/>"), "GONE", body -> body, xmlCode).value()).isEqualTo("<mission/>");
        // The JSON reader of the three-argument form does not read an XML body: a 404 with one is not a not-found.
        assertThat(Outcomes.fromCall(HttpResult.answer(404, "<error><code>GONE</code></error>"), "GONE", body -> body).resolution())
                .isEqualTo(Resolution.UNAVAILABLE);
    }

    @Test
    void unmappedCarriesNoErrorCode() {
        Outcome<Object> outcome = Outcome.unmapped();
        assertThat(outcome.resolution()).isEqualTo(Resolution.UNMAPPED);
        assertThat(outcome.errorCode()).isNull();
    }

    @Test
    void aRefusedReleaseIsDataWithNoErrorCodeAndTheMappingOutcomesAreThree() {
        Outcome<Object> outcome = Outcome.releaseRefused();
        assertThat(outcome.resolution()).isEqualTo(Resolution.RELEASE_REFUSED);
        assertThat(outcome.value()).isNull();
        assertThat(outcome.errorCode()).isNull();
        assertThat(MappingOutcome.values()).extracting(Enum::name).containsExactly("MAPPED", "NO_ENTRY", "RELEASE_REFUSED");
    }

    @Test
    void theCodeListIsTheDecidedOne() {
        assertThat(ErrorCode.values()).extracting(Enum::name).containsExactly("SERVICE_UNAVAILABLE", "MAPPING_RELEASE_REQUIRED",
                "MAPPING_RELEASE_NOT_FOUND", "MAPPING_CLASS_REFUSED", "UPSTREAM_BAD_RESPONSE", "BAD_USER_INPUT", "INTERNAL_SERVER_ERROR");
        assertThat(Resolution.values()).extracting(Enum::name).containsExactly("RESOLVED", "UNRESOLVED", "UNAVAILABLE", "UNMAPPED", "RELEASE_REFUSED");
    }

    @Test
    void theErrorsEntryHasAShortMessageThePathAndTheCode() {
        AtomicReference<GraphQLError> built = new AtomicReference<>();
        var registry = new SchemaParser().parse("type Query { hello: String }");
        var wiring = RuntimeWiring.newRuntimeWiring().type("Query", type -> type.dataFetcher("hello", (DataFetchingEnvironment environment) -> {
            built.set(FederationErrors.of(ErrorCode.SERVICE_UNAVAILABLE, "Assets service unavailable", environment));
            return null;
        })).build();
        GraphQL.newGraphQL(new SchemaGenerator().makeExecutableSchema(registry, wiring)).build().execute(ExecutionInput.newExecutionInput("{ hello }").build());
        GraphQLError error = built.get();
        assertThat(error.getMessage()).isEqualTo("Assets service unavailable");
        assertThat(error.getPath()).containsExactly("hello");
        assertThat(error.getExtensions()).containsEntry("code", "SERVICE_UNAVAILABLE");
    }
}
