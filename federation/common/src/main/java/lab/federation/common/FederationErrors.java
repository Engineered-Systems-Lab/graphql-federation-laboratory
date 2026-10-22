package lab.federation.common;

import graphql.GraphQLError;
import graphql.GraphqlErrorBuilder;
import graphql.schema.DataFetchingEnvironment;
import java.util.Map;

/** Builds the GraphQL errors entry: a short message, the path of the field and extensions.code. */
public final class FederationErrors {
    private FederationErrors() {
    }

    public static GraphQLError of(ErrorCode code, String message, DataFetchingEnvironment environment) {
        return GraphqlErrorBuilder.newError(environment).message(message).extensions(Map.of("code", code.name())).build();
    }
}
