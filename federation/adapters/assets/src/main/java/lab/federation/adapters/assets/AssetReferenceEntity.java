package lab.federation.adapters.assets;

import java.util.Map;
import lab.federation.common.ErrorCode;
import lab.federation.common.Json;
import lab.federation.common.MappingOutcome;
import lab.federation.common.Outcome;
import lab.federation.common.Outcomes;

/**
 * One AssetReference entity. The outcome is computed ONCE, on the first field that needs it, with ONE call to the service (or with
 * none when the mapping states NO_ENTRY (UNMAPPED) or RELEASE_REFUSED). The first field that finds the call failed carries the errors entry, so one failed
 * call makes one entry however many fields are selected.
 */
final class AssetReferenceEntity {
    static final String NOT_FOUND_CODE = "ASSET_NOT_FOUND";

    final String localRef;
    final String release;
    final String assetId;
    final MappingOutcome mappingOutcome;
    private Outcome<Map<String, Object>> outcome;
    private boolean errorClaimed;

    AssetReferenceEntity(String localRef, String release, String assetId, MappingOutcome mappingOutcome) {
        this.localRef = localRef;
        this.release = release;
        this.assetId = assetId;
        this.mappingOutcome = mappingOutcome;
    }

    synchronized Outcome<Map<String, Object>> outcome(AssetsClient client) {
        if (outcome == null) {
            if (mappingOutcome == MappingOutcome.NO_ENTRY) {
                outcome = Outcome.unmapped();
            } else if (mappingOutcome == MappingOutcome.RELEASE_REFUSED) {
                outcome = Outcome.releaseRefused();
            } else if (assetId == null) {
                // MAPPED without an identifier is a contradiction of the mapping subgraph; nothing is called and nothing is guessed.
                outcome = Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "The mapping said MAPPED without an assetId");
            } else {
                outcome = Outcomes.fromCall(client.asset(assetId), NOT_FOUND_CODE, Json::object);
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
