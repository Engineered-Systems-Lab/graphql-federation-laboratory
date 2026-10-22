package lab.enterprise.missions.domain;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import lab.enterprise.missions.ApiException;
import lab.enterprise.missions.xml.Mission;
import lab.enterprise.missions.xml.Status;

/**
 * Domain validation of a schema-valid Mission request body (422 DOMAIN_VALIDATION_FAILED), fail-fast: the first
 * failure is reported and nothing is aggregated. Grammar and schema failures never reach here; they are 400.
 */
public final class MissionRules {
    /** Which request the body belongs to: the service-owned elements differ by role. */
    public enum Role { CREATE, REPLACE }

    /** Physical capacity of an external reference column, VARCHAR2(50 BYTE); counted in UTF-8 bytes, not characters. */
    public static final int REFERENCE_CAPACITY_BYTES = 50;

    private MissionRules() { }

    /**
     * @param uriId the mission identifier of the PUT target, null for a POST
     */
    public static void validate(Mission mission, Role role, String uriId) {
        if (mission.getLastUpdated() != null) throw failed("lastUpdated is service-owned and must be omitted");
        if (role == Role.CREATE) {
            if (mission.getMissionId() != null) throw failed("missionId is service-generated and must be omitted");
        } else {
            if (mission.getMissionId() == null) throw failed("missionId is required in a replacement");
            if (!mission.getMissionId().equals(uriId))
                throw new ApiException(409, "RESOURCE_CONFLICT", "The body missionId differs from the mission in the URI");
        }
        text("title", mission.getTitle());
        text("objective", mission.getObjective());
        if (mission.getOutcome() != null) text("outcome", mission.getOutcome());
        text("location name", mission.getLocation().getName());
        if (mission.getLocation().getCoordinates() != null) text("coordinates", mission.getLocation().getCoordinates());
        if (mission.getLocation().getTravelVector() != null) text("travelVector", mission.getLocation().getTravelVector());
        distinct("assignedCrewIds", mission.getAssignedCrewIds().getCrewId());
        distinct("participantIds", mission.getParticipantIds().getParticipantId());
        distinct("assignedAssetIds", mission.getAssignedAssetIds().getAssetId());
        if (mission.getCommandingOfficerId() != null) capacity("commandingOfficerId", mission.getCommandingOfficerId());
        mission.getAssignedCrewIds().getCrewId().forEach(r -> capacity("assignedCrewIds", r));
        mission.getParticipantIds().getParticipantId().forEach(r -> capacity("participantIds", r));
        mission.getAssignedAssetIds().getAssetId().forEach(r -> capacity("assignedAssetIds", r));
        Status status = mission.getStatus();
        if (mission.getCommandingOfficerId() == null && commanderRequired(status))
            throw failed("commandingOfficerId is required when the status is " + status);
        if (mission.getOutcome() != null && !outcomeAllowed(status))
            throw failed("outcome is forbidden when the status is " + status);
        // A replacement that cancels without an estimate is decided against the stored provenance, under the lock.
        String violation = costViolation(status, mission.getEstimatedCostCredits(), mission.getActualCostCredits(), role == Role.REPLACE);
        if (violation != null) throw failed(violation);
    }

    public static boolean commanderRequired(Status status) { return status != Status.PLANNED && status != Status.CANCELLED; }

    public static boolean outcomeAllowed(Status status) {
        return status == Status.COMPLETED || status == Status.FAILED || status == Status.CANCELLED;
    }

    /**
     * The cost lifecycle table. A cancelled mission may omit its estimate only with retained PLANNED-origin eligibility,
     * which the caller establishes; pass true to defer that one decision.
     *
     * @return the violation, or null when the costs are allowed
     */
    public static String costViolation(Status status, String estimated, String actual, boolean cancelledMayOmitEstimate) {
        boolean hasEstimate = estimated != null;
        boolean hasActual = actual != null;
        switch (status) {
            case PLANNED:
                return hasActual ? "actualCostCredits is forbidden when the status is PLANNED" : null;
            case AUTHORIZED:
            case ACTIVE:
            case POSTPONED:
                if (!hasEstimate) return "estimatedCostCredits is required when the status is " + status;
                return hasActual ? "actualCostCredits is forbidden when the status is " + status : null;
            case COMPLETED:
            case FAILED:
                if (!hasEstimate) return "estimatedCostCredits is required when the status is " + status;
                return hasActual ? null : "actualCostCredits is required when the status is " + status;
            case CANCELLED:
                if (!hasActual) return "actualCostCredits is required when the status is CANCELLED";
                return hasEstimate || cancelledMayOmitEstimate ? null : "estimatedCostCredits is required for this CANCELLED mission";
            default:
                throw new IllegalStateException("Unhandled status " + status);
        }
    }

    /** Whether a replacement's CANCELLED result keeps the exemption to omit the estimate. */
    public static boolean retainsCancelledExemption(Status previous, boolean previousExemption) {
        return previous == Status.PLANNED || previous == Status.CANCELLED && previousExemption;
    }

    public static ApiException failed(String message) { return new ApiException(422, "DOMAIN_VALIDATION_FAILED", message); }

    /** A valid reference that the physical column cannot hold is refused, never truncated and never left to the database. */
    public static void capacity(String name, String reference) {
        if (Text.utf8Length(reference) > REFERENCE_CAPACITY_BYTES)
            throw failed(name + " holds a reference that exceeds the storage capacity of " + REFERENCE_CAPACITY_BYTES + " bytes");
    }

    private static void text(String name, String value) {
        if (Text.blank(value)) throw failed(name + " must contain a non-whitespace character");
    }

    private static void distinct(String name, List<String> references) {
        Set<String> seen = new HashSet<>();
        for (String reference : references)
            if (!seen.add(reference)) throw failed(name + " contains a duplicate reference");
    }
}
