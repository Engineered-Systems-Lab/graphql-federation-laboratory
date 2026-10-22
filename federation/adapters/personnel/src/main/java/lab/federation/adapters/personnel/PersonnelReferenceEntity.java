package lab.federation.adapters.personnel;

import java.util.Map;
import lab.federation.common.ErrorCode;
import lab.federation.common.MappingOutcome;
import lab.federation.common.Outcome;

/**
 * One PersonnelReference entity. The outcome is computed ONCE, on the first field that needs it, by a lookup of the batch the entity
 * came in with (or with no lookup when the mapping states NO_ENTRY (UNMAPPED) or RELEASE_REFUSED). The first field that finds the
 * lookup failed carries the errors entry, so one failed lookup makes one entry however many fields are selected.
 */
final class PersonnelReferenceEntity {
    final String localRef;
    final String release;
    final String personnelId;
    final MappingOutcome mappingOutcome;
    private final PersonnelLookup lookup;
    private Outcome<Map<String, Object>> outcome;
    private boolean errorClaimed;

    PersonnelReferenceEntity(String localRef, String release, String personnelId, MappingOutcome mappingOutcome, PersonnelLookup lookup) {
        this.localRef = localRef;
        this.release = release;
        this.personnelId = personnelId;
        this.mappingOutcome = mappingOutcome;
        this.lookup = lookup;
    }

    synchronized Outcome<Map<String, Object>> outcome() {
        if (outcome == null) {
            if (mappingOutcome == MappingOutcome.NO_ENTRY) {
                outcome = Outcome.unmapped();
            } else if (mappingOutcome == MappingOutcome.RELEASE_REFUSED) {
                outcome = Outcome.releaseRefused();
            } else if (personnelId == null) {
                // MAPPED without an identifier is a contradiction of the mapping subgraph; nothing is called and nothing is guessed.
                outcome = Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "The mapping said MAPPED without a personnelId");
            } else if (!PersonnelClient.sendable(personnelId)) {
                // The mapping handed on something that cannot be an id; nothing is sent and nothing is guessed.
                outcome = Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "The mapped personnelId cannot be used");
            } else {
                outcome = lookup.member(personnelId);
            }
        }
        return outcome;
    }

    /** True once, for the first caller. */
    synchronized boolean claimError() {
        boolean first = !errorClaimed;
        errorClaimed = true;
        return first;
    }
}
