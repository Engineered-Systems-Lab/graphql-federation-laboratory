package lab.federation.adapters.personnel;

import java.util.LinkedHashMap;
import java.util.Map;
import lab.federation.common.ErrorCode;
import lab.federation.common.Outcome;
import lab.federation.common.Resolution;
import org.springframework.stereotype.Component;

/**
 * The Personnel snapshot of one datasetVersion, read once and kept in memory. The Personnel v2 contract makes a snapshot immutable and
 * stamps every answer with its datasetVersion (a consumer compares it on every page and restarts at offset 0 when it changes), so
 * every lookup of one version can be served from the copy: a person's record cannot differ between two calls that name the same
 * version.
 *
 * <p>The copy never hides an outage. {@link #confirm} is what a batch of lookups calls first: ONE cheap list call (offset 0, limit 1)
 * that proves the service is reachable now and tells which datasetVersion it serves. A failed probe is the same UNAVAILABLE outcome,
 * with the same code, that the failed call of a lookup was; a version other than the copy's empties the copy and reads the whole
 * snapshot again through the list operation, in pages of {@value #PAGE}, restarting at offset 0 when the version changes between
 * pages. A reload that fails leaves no copy, so the next batch tries again. Reads are single-flight: batches that find the copy
 * missing wait for one load instead of making one each.
 */
@Component
public class PersonnelSnapshots {
    static final int PAGE = 100;
    /** How many times a read starts over because the service changed version between two pages, before it gives up. */
    static final int RESTARTS = 3;

    /** One snapshot as the list operation served it: its version and its members by personnelId, in the service's order. */
    record Snapshot(String datasetVersion, Map<String, Map<String, Object>> members) {
    }

    private final PersonnelClient client;
    private final Object loading = new Object();
    private volatile Snapshot current;

    public PersonnelSnapshots(PersonnelClient client) {
        this.client = client;
    }

    /**
     * Proves the service is reachable and returns the snapshot it serves now: the copy when the version is unchanged, else the
     * freshly read one. UNAVAILABLE carries the code of the call that failed.
     */
    Outcome<Snapshot> confirm() {
        Outcome<PersonnelXml.Page> probe = PersonnelCalls.outcome(client.list(null, null, 0, 1), body -> echoed(PersonnelXml.page(body), 0, 1));
        if (probe.resolution() != Resolution.RESOLVED) {
            return failure(probe);
        }
        String version = probe.value().datasetVersion();
        Snapshot copy = current;
        if (copy != null && copy.datasetVersion().equals(version)) {
            return Outcome.resolved(copy);
        }
        synchronized (loading) {
            copy = current;
            if (copy != null && copy.datasetVersion().equals(version)) {
                return Outcome.resolved(copy);
            }
            current = null;
            Outcome<Snapshot> read = read();
            if (read.resolution() == Resolution.RESOLVED) {
                current = read.value();
            }
            return read;
        }
    }

    /** The whole snapshot, page by page; one version across all pages or the read starts over. */
    private Outcome<Snapshot> read() {
        for (int attempt = 0; attempt <= RESTARTS; attempt++) {
            Map<String, Map<String, Object>> members = new LinkedHashMap<>();
            String version = null;
            int total = -1;
            int offset = 0;
            boolean changed = false;
            while (true) {
                int at = offset;
                Outcome<PersonnelXml.Page> answer = PersonnelCalls.outcome(client.list(null, null, at, PAGE), body -> echoed(PersonnelXml.page(body), at, PAGE));
                if (answer.resolution() != Resolution.RESOLVED) {
                    return failure(answer);
                }
                PersonnelXml.Page page = answer.value();
                if (version == null) {
                    version = page.datasetVersion();
                    total = page.totalCount();
                } else if (!version.equals(page.datasetVersion())) {
                    changed = true;
                    break;
                } else if (total != page.totalCount()) {
                    return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service changed the size of one snapshot");
                }
                for (Map<String, Object> member : page.members()) {
                    if (members.put((String) member.get("personnelId"), member) != null) {
                        return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service listed one member twice");
                    }
                }
                offset += page.members().size();
                if (!page.hasMore()) {
                    break;
                }
                if (page.members().isEmpty()) {
                    return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service answered an empty page that has more");
                }
            }
            if (changed) {
                continue;
            }
            if (members.size() != total) {
                return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service listed another number of members than it counted");
            }
            return Outcome.resolved(new Snapshot(version, Map.copyOf(members)));
        }
        return Outcome.unavailable(ErrorCode.SERVICE_UNAVAILABLE, "Service changed its snapshot while it was read");
    }

    /** The page as asked for: it must echo the offset and the limit of the call, or the answer is not this call's. */
    private static PersonnelXml.Page echoed(PersonnelXml.Page page, int offset, int limit) {
        if (page.offset() != offset || page.limit() != limit) {
            throw new IllegalArgumentException("the service answered another page");
        }
        return page;
    }

    /** A list has no "not found": that fault on a list call is something the adapter cannot use. */
    private static <T> Outcome<Snapshot> failure(Outcome<T> outcome) {
        if (outcome.resolution() == Resolution.UNAVAILABLE) {
            return Outcome.unavailable(outcome.errorCode(), outcome.message());
        }
        return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service answered something the adapter cannot use");
    }

    /** True for an id the contract can hold: only such an id is looked up in a snapshot. Any other is left to the service to refuse. */
    static boolean cacheable(String personnelId) {
        return personnelId != null && PersonnelXml.isPersonnelId(personnelId);
    }

    /** For tests: forgets the copy, as a new adapter has none. */
    void clear() {
        synchronized (loading) {
            current = null;
        }
    }

    /** For tests: the version of the copy, or null. */
    String cachedVersion() {
        Snapshot copy = current;
        return copy == null ? null : copy.datasetVersion();
    }
}
