package lab.enterprise.missions.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import lab.enterprise.missions.ApiException;
import lab.enterprise.missions.Samples;
import lab.enterprise.missions.domain.MissionRules.Role;
import lab.enterprise.missions.xml.Mission;
import lab.enterprise.missions.xml.Status;
import org.junit.jupiter.api.Test;

class MissionRulesTest {
    private static final String ID = "ST-00000LD4O";

    private static ApiException rejected(Mission mission, Role role, String uriId, int status, String code) {
        var e = assertThrows(ApiException.class, () -> MissionRules.validate(mission, role, uriId));
        assertEquals(status, e.status, e.getMessage());
        assertEquals(code, e.code);
        return e;
    }

    private static void domain(Mission mission, Role role, String uriId) { rejected(mission, role, uriId, 422, "DOMAIN_VALIDATION_FAILED"); }

    private static Mission replacement() {
        Mission mission = Samples.planned();
        mission.setMissionId(ID);
        return mission;
    }

    /** The cost lifecycle table of the design, written out as rows independent of the implementation. */
    private static final Object[][] COST_TABLE = {
            // status, estimate present, actual present, allowed (CANCELLED: without the PLANNED-origin exemption)
            {Status.PLANNED, false, false, true}, {Status.PLANNED, true, false, true},
            {Status.PLANNED, false, true, false}, {Status.PLANNED, true, true, false},
            {Status.AUTHORIZED, false, false, false}, {Status.AUTHORIZED, true, false, true},
            {Status.AUTHORIZED, false, true, false}, {Status.AUTHORIZED, true, true, false},
            {Status.ACTIVE, false, false, false}, {Status.ACTIVE, true, false, true},
            {Status.ACTIVE, false, true, false}, {Status.ACTIVE, true, true, false},
            {Status.POSTPONED, false, false, false}, {Status.POSTPONED, true, false, true},
            {Status.POSTPONED, false, true, false}, {Status.POSTPONED, true, true, false},
            {Status.COMPLETED, false, false, false}, {Status.COMPLETED, true, false, false},
            {Status.COMPLETED, false, true, false}, {Status.COMPLETED, true, true, true},
            {Status.FAILED, false, false, false}, {Status.FAILED, true, false, false},
            {Status.FAILED, false, true, false}, {Status.FAILED, true, true, true},
            {Status.CANCELLED, false, false, false}, {Status.CANCELLED, true, false, false},
            {Status.CANCELLED, false, true, false}, {Status.CANCELLED, true, true, true}};

    @Test void costLifecycleMatrixWithoutTheCancellationExemption() {
        for (Object[] row : COST_TABLE) {
            String estimate = (boolean) row[1] ? "100.00" : null;
            String actual = (boolean) row[2] ? "0.00" : null;
            String violation = MissionRules.costViolation((Status) row[0], estimate, actual, false);
            assertEquals((boolean) row[3], violation == null, row[0] + " estimate=" + row[1] + " actual=" + row[2] + " " + violation);
        }
    }

    @Test void aCancelledMissionWithPlannedOriginMayOmitItsEstimateButStillNeedsActual() {
        assertNull(MissionRules.costViolation(Status.CANCELLED, null, "0.00", true));
        assertNotNull(MissionRules.costViolation(Status.CANCELLED, null, null, true));
        assertNotNull(MissionRules.costViolation(Status.CANCELLED, "5.00", null, true));
        // The exemption belongs to CANCELLED only.
        assertNotNull(MissionRules.costViolation(Status.ACTIVE, null, null, true));
        assertNotNull(MissionRules.costViolation(Status.COMPLETED, null, "1.00", true));
    }

    @Test void cancellationProvenanceFollowsTheImmediatePredecessor() {
        assertTrue(MissionRules.retainsCancelledExemption(Status.PLANNED, false));
        assertTrue(MissionRules.retainsCancelledExemption(Status.CANCELLED, true));
        assertFalse(MissionRules.retainsCancelledExemption(Status.CANCELLED, false));
        for (Status other : new Status[] {Status.AUTHORIZED, Status.ACTIVE, Status.POSTPONED, Status.COMPLETED, Status.FAILED})
            assertFalse(MissionRules.retainsCancelledExemption(other, true), other.name());
    }

    @Test void aPostCancelledWithoutEstimateIsRejectedButAReplacementDefersTheDecision() {
        Mission post = Samples.planned();
        post.setStatus(Status.CANCELLED);
        post.setActualCostCredits("0.00");
        domain(post, Role.CREATE, null);
        Mission put = replacement();
        put.setStatus(Status.CANCELLED);
        put.setActualCostCredits("0.00");
        MissionRules.validate(put, Role.REPLACE, ID);
    }

    @Test void aValidPlannedMissionPassesBothRoles() {
        MissionRules.validate(Samples.planned(), Role.CREATE, null);
        MissionRules.validate(replacement(), Role.REPLACE, ID);
    }

    @Test void serviceOwnedElementsFollowTheRoleTable() {
        Mission post = Samples.planned();
        post.setMissionId(ID);
        domain(post, Role.CREATE, null);
        post = Samples.planned();
        post.setLastUpdated("2366-10-14T19:42:31.472Z");
        domain(post, Role.CREATE, null);
        Mission put = replacement();
        put.setMissionId(null);
        domain(put, Role.REPLACE, ID);
        put = replacement();
        put.setLastUpdated("2366-10-14T19:42:31.472Z");
        domain(put, Role.REPLACE, ID);
        put = replacement();
        rejected(put, Role.REPLACE, "ST-00000LD4P", 409, "RESOURCE_CONFLICT");
    }

    @Test void commanderIsRequiredExceptForPlannedAndCancelled() {
        for (Status status : Status.values()) {
            Mission mission = replacement();
            mission.setStatus(status);
            mission.setEstimatedCostCredits("10.00");
            if (status == Status.COMPLETED || status == Status.FAILED || status == Status.CANCELLED) mission.setActualCostCredits("9.00");
            if (status == Status.AUTHORIZED || status == Status.ACTIVE || status == Status.POSTPONED || status == Status.PLANNED) mission.setActualCostCredits(null);
            boolean required = status != Status.PLANNED && status != Status.CANCELLED;
            if (required) domain(mission, Role.REPLACE, ID);
            else MissionRules.validate(mission, Role.REPLACE, ID);
            mission.setCommandingOfficerId("C-71");
            MissionRules.validate(mission, Role.REPLACE, ID);
        }
    }

    @Test void outcomeIsForbiddenBeforeATerminalStatusAndOptionalAfter() {
        for (Status status : Status.values()) {
            Mission mission = replacement();
            mission.setStatus(status);
            mission.setCommandingOfficerId("C-71");
            mission.setEstimatedCostCredits("10.00");
            if (status == Status.COMPLETED || status == Status.FAILED || status == Status.CANCELLED) mission.setActualCostCredits("9.00");
            MissionRules.validate(mission, Role.REPLACE, ID);
            mission.setOutcome("Recorded.");
            boolean terminal = status == Status.COMPLETED || status == Status.FAILED || status == Status.CANCELLED;
            if (terminal) MissionRules.validate(mission, Role.REPLACE, ID);
            else domain(mission, Role.REPLACE, ID);
        }
    }

    @Test void whitespaceOnlyMinimumOneStringsAreDomainFailures() {
        String[] blanks = {" ", "\t", "　", "   ", " "};
        for (String blank : blanks) {
            Mission mission = Samples.planned();
            mission.setTitle(blank);
            domain(mission, Role.CREATE, null);
            mission = Samples.planned();
            mission.setObjective(blank);
            domain(mission, Role.CREATE, null);
            mission = Samples.planned();
            mission.getLocation().setName(blank);
            domain(mission, Role.CREATE, null);
            mission = Samples.planned();
            mission.getLocation().setCoordinates(blank);
            domain(mission, Role.CREATE, null);
            mission = Samples.planned();
            mission.getLocation().setTravelVector(blank);
            domain(mission, Role.CREATE, null);
            mission = Samples.planned();
            mission.setStatus(Status.CANCELLED);
            mission.setEstimatedCostCredits("1.00");
            mission.setActualCostCredits("1.00");
            mission.setOutcome(blank);
            domain(mission, Role.CREATE, null);
        }
        // Spaces around content and non-whitespace look-alikes are accepted and kept as they are.
        Mission mission = Samples.planned();
        mission.setTitle("  padded  ");
        mission.setObjective(" ");
        mission.getLocation().setCoordinates("​");
        MissionRules.validate(mission, Role.CREATE, null);
        assertEquals("  padded  ", mission.getTitle());
    }

    @Test void duplicatesInAnyCollectionAreDomainFailuresAndOrderIsFree() {
        Mission mission = Samples.planned();
        mission.getAssignedCrewIds().getCrewId().addAll(java.util.List.of("C-2", "C-10", "C-2"));
        domain(mission, Role.CREATE, null);
        mission = Samples.planned();
        mission.getParticipantIds().getParticipantId().addAll(java.util.List.of("P-1", "O-1", "P-1"));
        domain(mission, Role.CREATE, null);
        mission = Samples.planned();
        mission.getAssignedAssetIds().getAssetId().addAll(java.util.List.of("SH-17", "SH-17"));
        domain(mission, Role.CREATE, null);
        mission = Samples.planned();
        mission.getAssignedCrewIds().getCrewId().addAll(java.util.List.of("C-2", "C-10"));
        mission.getParticipantIds().getParticipantId().addAll(java.util.List.of("P-2", "O-2"));
        mission.getAssignedAssetIds().getAssetId().addAll(java.util.List.of("SH-17", "SH-2"));
        MissionRules.validate(mission, Role.CREATE, null);
    }

    @Test void onlyTheFirstFailureIsReported() {
        Mission mission = Samples.planned();
        mission.setLastUpdated("2366-10-14T19:42:31.472Z");
        mission.setTitle(" ");
        var e = assertThrows(ApiException.class, () -> MissionRules.validate(mission, Role.CREATE, null));
        assertTrue(e.getMessage().contains("lastUpdated"), e.getMessage());
    }

    @Test void aReferenceBeyondFiftyBytesIsRefusedAs422InEveryReferenceField() {
        String fits = "C-" + "9".repeat(48);
        String tooLong = "C-" + "9".repeat(49);
        Mission ok = Samples.planned();
        ok.getAssignedCrewIds().getCrewId().add(fits);
        MissionRules.validate(ok, Role.CREATE, null);
        Mission crew = Samples.planned();
        crew.getAssignedCrewIds().getCrewId().add(tooLong);
        assertTrue(rejectedMessage(crew).contains("storage capacity"));
        Mission participant = Samples.planned();
        participant.getParticipantIds().getParticipantId().add("P-" + "9".repeat(49));
        domain(participant, Role.CREATE, null);
        Mission asset = Samples.planned();
        asset.getAssignedAssetIds().getAssetId().add("SH-" + "9".repeat(48));
        domain(asset, Role.CREATE, null);
        Mission commander = Samples.planned();
        commander.setCommandingOfficerId(tooLong);
        domain(commander, Role.CREATE, null);
    }

    @Test void theCapacityCountsUtf8BytesNeverCharacters() {
        // 49 ASCII characters plus one two-byte character: 50 characters, 51 bytes.
        String wide = "C-" + "9".repeat(47) + new String(Character.toChars(0xE9));
        assertEquals(50, wide.length());
        var e = assertThrows(ApiException.class, () -> MissionRules.capacity("assignedCrewIds", wide));
        assertEquals(422, e.status);
        MissionRules.capacity("assignedCrewIds", "C-" + "9".repeat(48));
    }

    private static String rejectedMessage(Mission mission) {
        return assertThrows(ApiException.class, () -> MissionRules.validate(mission, Role.CREATE, null)).getMessage();
    }
}
