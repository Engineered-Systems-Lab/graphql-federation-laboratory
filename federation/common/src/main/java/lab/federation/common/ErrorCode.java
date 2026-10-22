package lab.federation.common;

/**
 * The extensions.code values of the lab's GraphQL errors entries. UNMAPPED is data and has no code here: it adds no errors entry.
 * BAD_USER_INPUT and INTERNAL_SERVER_ERROR are the names of Apollo Server's documented error codes (checked 2026-10-16).
 */
public enum ErrorCode {
    /** The service behind the adapter could not answer: a connection failure, a timeout or a 5xx. */
    SERVICE_UNAVAILABLE,
    /** A request that names no mapping release is refused. */
    MAPPING_RELEASE_REQUIRED,
    /** An unknown mapping release. */
    MAPPING_RELEASE_NOT_FOUND,
    /**
     * A reference whose class the mapping lookup does not resolve: an outsider (O-n), refused by class and never mapped (D048), or a
     * participant (P-n), which the graph does not resolve yet. Only the mapping adapter's plain lookups give it; the entities do not.
     */
    MAPPING_CLASS_REFUSED,
    /** The service answered something the adapter cannot use: a malformed body, or a 4xx that is not a plain not-found. */
    UPSTREAM_BAD_RESPONSE,
    /** A malformed argument from the client. */
    BAD_USER_INPUT,
    /** A fault of the adapter itself. */
    INTERNAL_SERVER_ERROR
}
