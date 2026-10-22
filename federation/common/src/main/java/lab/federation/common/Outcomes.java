package lab.federation.common;

import java.util.Map;
import java.util.function.Function;

/** Derives the outcome of a reference from the result of ONE call. */
public final class Outcomes {
    private Outcomes() {
    }

    /**
     * 200 gives RESOLVED with the parsed object; a 404 whose body carries {@code notFoundCode} gives UNRESOLVED (any other 404, such as
     * PATH_NOT_FOUND, is not); a 5xx or a failure to answer gives UNAVAILABLE with SERVICE_UNAVAILABLE; any other answer, or a 200 that
     * cannot be parsed, gives UNAVAILABLE with UPSTREAM_BAD_RESPONSE. A null {@code notFoundCode} never gives UNRESOLVED.
     */
    public static <T> Outcome<T> fromCall(HttpResult result, String notFoundCode, Function<String, T> parse) {
        return fromCall(result, notFoundCode, parse, Outcomes::serviceCode);
    }

    /** The same derivation for a service whose error body is not JSON: {@code codeReader} reads the service's error code from the result. */
    public static <T> Outcome<T> fromCall(HttpResult result, String notFoundCode, Function<String, T> parse,
                                          Function<HttpResult, String> codeReader) {
        if (result.failed()) {
            return Outcome.unavailable(ErrorCode.SERVICE_UNAVAILABLE, "Service unavailable");
        }
        int status = result.status();
        if (status == 200) {
            try {
                return Outcome.resolved(parse.apply(result.body()));
            } catch (RuntimeException error) {
                return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service answered a body the adapter cannot use");
            }
        }
        if (status == 404 && notFoundCode != null && notFoundCode.equals(codeReader.apply(result))) {
            return Outcome.unresolved();
        }
        if (status >= 500) {
            return Outcome.unavailable(ErrorCode.SERVICE_UNAVAILABLE, "Service unavailable");
        }
        return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service answered " + status + " and the adapter cannot use it");
    }

    /** The {@code code} field of the service's error body, or null when the body is not such an object. */
    public static String serviceCode(HttpResult result) {
        if (result.failed() || result.body() == null) {
            return null;
        }
        try {
            Object code = Json.object(result.body()).get("code");
            return code instanceof String text ? text : null;
        } catch (IllegalArgumentException error) {
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> asObject(Object value) {
        return (Map<String, Object>) value;
    }
}
