package lab.federation.common;

/**
 * What the mapping layer did with a reference, stated by the mapping subgraph and read by the owning adapters, which no longer infer
 * the cause from a null identifier. The names are the values of the GraphQL enum MappingOutcome.
 */
public enum MappingOutcome {
    /** The named release has an entry for the reference: the identifier is set. */
    MAPPED,
    /** The release is valid and has no entry for the reference (or no section for its kind, such as crew in release 1.0). */
    NO_ENTRY,
    /** The release was refused: it is blank or unknown. The errors entry MAPPING_RELEASE_REQUIRED or MAPPING_RELEASE_NOT_FOUND says which. */
    RELEASE_REFUSED
}
