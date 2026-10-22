package lab.federation.common;

/**
 * The outcome of one call: the resolution, the object (only when RESOLVED) and, when UNAVAILABLE, the code of the errors entry
 * and a short message. UNRESOLVED, UNMAPPED and RELEASE_REFUSED are data and carry no error code (the refused release has its own errors entry, made by the mapping subgraph).
 */
public record Outcome<T>(Resolution resolution, T value, ErrorCode errorCode, String message) {
    public static <T> Outcome<T> resolved(T value) {
        return new Outcome<>(Resolution.RESOLVED, value, null, null);
    }

    public static <T> Outcome<T> unresolved() {
        return new Outcome<>(Resolution.UNRESOLVED, null, null, null);
    }

    public static <T> Outcome<T> unmapped() {
        return new Outcome<>(Resolution.UNMAPPED, null, null, null);
    }

    public static <T> Outcome<T> releaseRefused() {
        return new Outcome<>(Resolution.RELEASE_REFUSED, null, null, null);
    }

    public static <T> Outcome<T> unavailable(ErrorCode code, String message) {
        return new Outcome<>(Resolution.UNAVAILABLE, null, code, message);
    }
}
