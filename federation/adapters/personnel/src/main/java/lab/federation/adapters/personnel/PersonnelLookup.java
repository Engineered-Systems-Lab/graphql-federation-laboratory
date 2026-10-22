package lab.federation.adapters.personnel;

import java.util.Map;
import lab.federation.common.Outcome;
import lab.federation.common.Resolution;

/**
 * The lookups of ONE batch of entities (one {@code _entities} call). The first lookup that needs the service confirms it once
 * ({@link PersonnelSnapshots#confirm}: one cheap probe, and a read of the snapshot only when its version is not the copy's), and
 * every lookup of the batch is answered from the snapshot that confirmation returned, or with the failure it returned. A batch that
 * looks nothing up (every reference UNMAPPED or RELEASE_REFUSED, or no field selected) makes no call at all.
 *
 * An id the contract cannot hold is not looked up in a snapshot: it is sent to the service, which owns the grammar and refuses it
 * exactly as it did before the snapshot was kept.
 */
final class PersonnelLookup {
    private final PersonnelClient client;
    private final PersonnelSnapshots snapshots;
    private Outcome<PersonnelSnapshots.Snapshot> confirmed;

    PersonnelLookup(PersonnelClient client, PersonnelSnapshots snapshots) {
        this.client = client;
        this.snapshots = snapshots;
    }

    /** The outcome for {@code personnelId}, which must pass {@link PersonnelClient#sendable}. */
    synchronized Outcome<Map<String, Object>> member(String personnelId) {
        if (!PersonnelSnapshots.cacheable(personnelId)) {
            return PersonnelCalls.member(client.get(personnelId), personnelId);
        }
        if (confirmed == null) {
            confirmed = snapshots.confirm();
        }
        if (confirmed.resolution() != Resolution.RESOLVED) {
            return Outcome.unavailable(confirmed.errorCode(), confirmed.message());
        }
        Map<String, Object> member = confirmed.value().members().get(personnelId);
        return member == null ? Outcome.unresolved() : Outcome.resolved(member);
    }
}
