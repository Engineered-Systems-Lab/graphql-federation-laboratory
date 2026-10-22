package lab.federation.common;

/** How a reference to a thing in another system turned out. UNMAPPED and RELEASE_REFUSED are the mapping layer's own outcomes and are never UNRESOLVED. */
public enum Resolution {
    /** The owning service has the thing (whatever its status). */
    RESOLVED,
    /** The owning service answered that the thing does not exist. */
    UNRESOLVED,
    /** The owning service could not answer, so it is not known whether the thing exists. */
    UNAVAILABLE,
    /** The mapping layer has no entry for the reference in the named release; the service was not called. */
    UNMAPPED,
    /** The mapping layer refused the release (blank or unknown), so there is no mapping to look up; the service was not called. */
    RELEASE_REFUSED
}
