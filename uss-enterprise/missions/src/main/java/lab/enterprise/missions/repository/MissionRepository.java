package lab.enterprise.missions.repository;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Types;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lab.enterprise.missions.ApiException;
import lab.enterprise.missions.api.MutationHeaders;
import lab.enterprise.missions.api.Query;
import lab.enterprise.missions.domain.CostAudit;
import lab.enterprise.missions.domain.MissionIds;
import lab.enterprise.missions.domain.MissionRules;
import lab.enterprise.missions.xml.Change;
import lab.enterprise.missions.xml.Classification;
import lab.enterprise.missions.xml.IssuingAuthority;
import lab.enterprise.missions.xml.Location;
import lab.enterprise.missions.xml.LocationType;
import lab.enterprise.missions.xml.Mission;
import lab.enterprise.missions.xml.MissionType;
import lab.enterprise.missions.xml.Operation;
import lab.enterprise.missions.xml.Status;
import lab.enterprise.missions.xml.AssetIds;
import lab.enterprise.missions.xml.CrewIds;
import lab.enterprise.missions.xml.ParticipantIds;

/**
 * Access to the six-table schema. Every number and timestamp is formatted by Oracle into its canonical wire spelling,
 * and every timestamp is written from Oracle's own transactional clock, so no client locale, time zone, floating-point
 * conversion or host clock can alter a value. Each mutation is one transaction: clock tick, row, collections, audit event.
 */
public final class MissionRepository {
    private static final String STARDATE = "TO_CHAR(%s.stardate,'FM00000.00')";
    private static final String CREDITS = "TO_CHAR(%s.%s,'FM9999999999990.00')";
    private static final String TIME = "TO_CHAR(%s.%s,'YYYY-MM-DD\"T\"HH24:MI:SS.FF3\"Z\"')";
    private static final String BIG = "TO_CHAR(%s.%s,'FM9999999999999999999999999990')";
    private static final String MISSION_COLUMNS = "m.mission_id, m.title, m.mission_type, m.classification, m.status, m.priority, "
            + String.format(STARDATE, "m") + ", m.duration_hours, m.objective, m.location_type, m.location_name, m.coordinates, "
            + "m.travel_vector, m.issuing_authority, m.commanding_officer_id, "
            + String.format(CREDITS, "m", "estimated_cost") + ", " + String.format(CREDITS, "m", "actual_cost") + ", m.outcome, "
            + String.format(TIME, "m", "last_updated") + ", " + String.format(BIG, "m", "current_change_id");
    private static final String CHANGE_COLUMNS = String.format(BIG, "c", "change_id") + ", c.mission_id, c.operation, "
            + String.format(TIME, "c", "changed_at") + ", c.changed_by, c.ordered_by, c.previous_status, c.new_status, "
            + String.format(CREDITS, "c", "estimated_cost") + ", " + String.format(CREDITS, "c", "estimated_cost_change") + ", "
            + String.format(CREDITS, "c", "actual_cost") + ", " + String.format(CREDITS, "c", "actual_cost_change") + ", c.summary";

    /** The client-managed scalar columns, in the order {@link #bindScalars} binds them. */
    private static final String[] SCALARS = {"title", "mission_type", "classification", "status", "priority", "stardate",
            "duration_hours", "objective", "location_type", "location_name", "coordinates", "travel_vector", "issuing_authority",
            "commanding_officer_id", "estimated_cost", "actual_cost", "outcome"};
    private static final String STAMP = "TO_TIMESTAMP(?,'YYYY-MM-DD\"T\"HH24:MI:SS.FF3')";
    private static final String INSERT_MISSION = "INSERT INTO missions (mission_id, " + String.join(", ", SCALARS)
            + ", last_updated, current_change_id, cancelled_without_estimate_allowed) VALUES (?, "
            + String.join(", ", Collections.nCopies(SCALARS.length, "?")) + ", " + STAMP + ", ?, ?)";
    private static final String UPDATE_MISSION = "UPDATE missions SET " + String.join(" = ?, ", SCALARS)
            + " = ?, last_updated = " + STAMP + ", current_change_id = ?, cancelled_without_estimate_allowed = ? WHERE mission_id = ?";
    private static final String INSERT_CHANGE = "INSERT INTO mission_changes (change_id, mission_id, operation, changed_at, "
            + "changed_by, ordered_by, previous_status, new_status, estimated_cost, estimated_cost_change, actual_cost, "
            + "actual_cost_change, summary) VALUES (?, ?, ?, " + STAMP + ", ?, ?, ?, ?, ?, ?, ?, ?, ?)";
    private static final int ORACLE_UNIQUE_VIOLATION = 1;
    private static final int LOCK_TIMEOUT_SECONDS = 30;

    /** One page of results with the filtered total. */
    public record Result<T>(long totalCount, List<T> items) { }

    /** A mission with the strong-ETag source, the current change id. */
    public record Found(Mission mission, String changeId) { }

    /** The stored facts a replacement is decided against, read under the row lock. */
    private record Current(Status status, BigDecimal estimated, BigDecimal actual, String changeId, boolean cancelledExemption) { }

    private final Database database;

    public MissionRepository(Database database) { this.database = database; }

    public Result<Mission> list(Query.MissionQuery query) throws SQLException {
        return database.read(connection -> {
            var where = new StringBuilder(" WHERE 1=1");
            List<String> binds = new ArrayList<>();
            for (Map.Entry<String, String> filter : query.filters().entrySet()) {
                String value = filter.getValue();
                switch (filter.getKey()) {
                    case "type" -> where.append(" AND m.mission_type = ?");
                    case "classification" -> where.append(" AND m.classification = ?");
                    case "status" -> where.append(" AND m.status = ?");
                    case "priority" -> where.append(" AND m.priority = ?");
                    case "issuingAuthority" -> where.append(" AND m.issuing_authority = ?");
                    case "commandingOfficerId" -> where.append(" AND m.commanding_officer_id = ?");
                    case "locationType" -> where.append(" AND m.location_type = ?");
                    case "assignedCrewId" -> where.append(" AND EXISTS (SELECT 1 FROM mission_assigned_crew x WHERE x.mission_id = m.mission_id AND x.reference = ?)");
                    case "assignedAssetId" -> where.append(" AND EXISTS (SELECT 1 FROM mission_assigned_assets x WHERE x.mission_id = m.mission_id AND x.reference = ?)");
                    default -> throw new IllegalStateException("Unvalidated filter " + filter.getKey());
                }
                binds.add(value);
            }
            long total = count(connection, "SELECT COUNT(*) FROM missions m" + where, binds);
            List<Mission> missions = new ArrayList<>();
            Query.Paging paging = query.paging();
            long offset = offset(paging, total);
            if (offset >= 0) {
                String sql = "SELECT " + MISSION_COLUMNS + " FROM missions m" + where
                        + " ORDER BY m.stardate ASC, m.priority ASC, m.mission_id ASC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY";
                try (PreparedStatement statement = connection.prepareStatement(sql)) {
                    int index = bind(statement, binds);
                    statement.setLong(index++, offset);
                    statement.setInt(index, paging.pageSize());
                    try (ResultSet rows = statement.executeQuery()) {
                        while (rows.next()) missions.add(mission(rows));
                    }
                }
                attachCollections(connection, missions);
            }
            return new Result<>(total, missions);
        });
    }

    public Found get(String missionId) throws SQLException {
        return database.read(connection -> load(connection, missionId));
    }

    /** Null when the mission does not exist. */
    private static Found load(Connection connection, String missionId) throws SQLException {
        String sql = "SELECT " + MISSION_COLUMNS + " FROM missions m WHERE m.mission_id = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, missionId);
            try (ResultSet rows = statement.executeQuery()) {
                if (!rows.next()) return null;
                Mission mission = mission(rows);
                String changeId = rows.getString(20);
                attachCollections(connection, List.of(mission));
                return new Found(mission, changeId);
            }
        }
    }

    /** Null when the mission does not exist, so the caller can answer 404 MISSION_NOT_FOUND. */
    public Result<Change> changes(String missionId, Query.Paging paging) throws SQLException {
        return database.read(connection -> {
            long exists = count(connection, "SELECT COUNT(*) FROM missions m WHERE m.mission_id = ?", List.of(missionId));
            if (exists == 0) return null;
            long total = count(connection, "SELECT COUNT(*) FROM mission_changes c WHERE c.mission_id = ?", List.of(missionId));
            List<Change> changes = new ArrayList<>();
            long offset = offset(paging, total);
            if (offset >= 0) {
                String sql = "SELECT " + CHANGE_COLUMNS + " FROM mission_changes c WHERE c.mission_id = ?"
                        + " ORDER BY c.change_id ASC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY";
                try (PreparedStatement statement = connection.prepareStatement(sql)) {
                    statement.setString(1, missionId);
                    statement.setLong(2, offset);
                    statement.setInt(3, paging.pageSize());
                    try (ResultSet rows = statement.executeQuery()) {
                        while (rows.next()) changes.add(change(rows));
                    }
                }
            }
            return new Result<>(total, changes);
        });
    }

    // --- writes ----------------------------------------------------------------------------------------------------

    /**
     * POST: generates the identifier, change id and timestamp, stores the mission and its collections and appends CREATED.
     * The input has passed {@link MissionRules#validate}; a created mission has no cancellation provenance to retain.
     */
    public Found create(Mission input, MutationHeaders audit) throws SQLException {
        return database.write(connection -> {
            // The clock row is locked first, so everything below is serialized in one global mutation order.
            String stamp = tick(connection);
            BigInteger changeId = next(connection, "change_id_seq");
            String missionId = MissionIds.fromSequence(next(connection, "mission_id_seq").longValueExact());
            try (PreparedStatement statement = connection.prepareStatement(INSERT_MISSION)) {
                statement.setString(1, missionId);
                int index = bindScalars(statement, 2, input);
                statement.setString(index++, stamp);
                statement.setBigDecimal(index++, new BigDecimal(changeId));
                statement.setInt(index, 0);
                statement.executeUpdate();
            } catch (SQLException e) {
                if (e.getErrorCode() == ORACLE_UNIQUE_VIOLATION)
                    throw new ApiException(409, "RESOURCE_CONFLICT", "A mission with the generated identifier already exists");
                throw e;
            }
            insertCollections(connection, missionId, input);
            insertChange(connection, changeId, missionId, Operation.CREATED, stamp, audit, null, input.getStatus(),
                    CostAudit.of(null, credits(input.getEstimatedCostCredits())), CostAudit.of(null, credits(input.getActualCostCredits())));
            return load(connection, missionId);
        });
    }

    /**
     * PUT: replaces the whole mission if the stored change id still equals the one the client holds. Always advances the
     * change id and appends UPDATED, even when no client-managed value changed.
     */
    public Found replace(String missionId, String expectedChangeId, Mission input, MutationHeaders audit) throws SQLException {
        return database.write(connection -> {
            String stamp = tick(connection);
            Current current = lock(connection, missionId);
            if (current == null) throw new ApiException(404, "MISSION_NOT_FOUND", "No mission " + missionId);
            // Rechecked under the mission lock, so two writers holding one tag cannot both succeed.
            if (!current.changeId().equals(expectedChangeId))
                throw new ApiException(412, "ETAG_MISMATCH", "The mission changed since the If-Match tag was issued");
            Status status = input.getStatus();
            boolean exemption = status == Status.CANCELLED && MissionRules.retainsCancelledExemption(current.status(), current.cancelledExemption());
            if (status == Status.CANCELLED && input.getEstimatedCostCredits() == null && !exemption)
                throw MissionRules.failed("estimatedCostCredits is required for this CANCELLED mission");
            BigInteger changeId = next(connection, "change_id_seq");
            try (PreparedStatement statement = connection.prepareStatement(UPDATE_MISSION)) {
                int index = bindScalars(statement, 1, input);
                statement.setString(index++, stamp);
                statement.setBigDecimal(index++, new BigDecimal(changeId));
                statement.setInt(index++, exemption ? 1 : 0);
                statement.setString(index, missionId);
                statement.executeUpdate();
            }
            for (String table : new String[] {"mission_assigned_crew", "mission_participants", "mission_assigned_assets"}) {
                try (PreparedStatement statement = connection.prepareStatement("DELETE FROM " + table + " WHERE mission_id = ?")) {
                    statement.setString(1, missionId);
                    statement.executeUpdate();
                }
            }
            insertCollections(connection, missionId, input);
            insertChange(connection, changeId, missionId, Operation.UPDATED, stamp, audit, current.status(), status,
                    CostAudit.of(current.estimated(), credits(input.getEstimatedCostCredits())),
                    CostAudit.of(current.actual(), credits(input.getActualCostCredits())));
            return load(connection, missionId);
        });
    }

    /** Advances Oracle's transactional reference clock and returns the new instant as canonical text, holding the clock lock. */
    private static String tick(Connection connection) throws SQLException {
        try (CallableStatement call = connection.prepareCall(
                "BEGIN ? := TO_CHAR(missions_clock_tick,'YYYY-MM-DD\"T\"HH24:MI:SS.FF3'); END;")) {
            call.registerOutParameter(1, Types.VARCHAR);
            call.setQueryTimeout(LOCK_TIMEOUT_SECONDS);
            call.execute();
            return call.getString(1);
        }
    }

    private static BigInteger next(Connection connection, String sequence) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement("SELECT " + sequence + ".NEXTVAL FROM dual");
             ResultSet rows = statement.executeQuery()) {
            rows.next();
            return rows.getBigDecimal(1).toBigIntegerExact();
        }
    }

    private static Current lock(Connection connection, String missionId) throws SQLException {
        String sql = "SELECT m.status, m.estimated_cost, m.actual_cost, " + String.format(BIG, "m", "current_change_id")
                + ", m.cancelled_without_estimate_allowed FROM missions m WHERE m.mission_id = ? FOR UPDATE";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, missionId);
            statement.setQueryTimeout(LOCK_TIMEOUT_SECONDS);
            try (ResultSet rows = statement.executeQuery()) {
                if (!rows.next()) return null;
                return new Current(Status.fromValue(rows.getString(1)), rows.getBigDecimal(2), rows.getBigDecimal(3), rows.getString(4),
                        rows.getInt(5) == 1);
            }
        }
    }

    /** Binds the client-managed columns, null as SQL NULL, and returns the next parameter index. */
    private static int bindScalars(PreparedStatement statement, int index, Mission mission) throws SQLException {
        Location location = mission.getLocation();
        statement.setString(index++, mission.getTitle());
        statement.setString(index++, mission.getType().value());
        statement.setString(index++, mission.getClassification().value());
        statement.setString(index++, mission.getStatus().value());
        statement.setInt(index++, Integer.parseInt(mission.getPriority()));
        statement.setBigDecimal(index++, new BigDecimal(mission.getStardate()));
        statement.setInt(index++, Integer.parseInt(mission.getDurationHours()));
        statement.setString(index++, mission.getObjective());
        statement.setString(index++, location.getType().value());
        statement.setString(index++, location.getName());
        text(statement, index++, location.getCoordinates());
        text(statement, index++, location.getTravelVector());
        statement.setString(index++, mission.getIssuingAuthority().value());
        text(statement, index++, mission.getCommandingOfficerId());
        decimal(statement, index++, credits(mission.getEstimatedCostCredits()));
        decimal(statement, index++, credits(mission.getActualCostCredits()));
        text(statement, index++, mission.getOutcome());
        return index;
    }

    private static void insertCollections(Connection connection, String missionId, Mission mission) throws SQLException {
        insertReferences(connection, "mission_assigned_crew", missionId, mission.getAssignedCrewIds().getCrewId());
        insertReferences(connection, "mission_participants", missionId, mission.getParticipantIds().getParticipantId());
        insertReferences(connection, "mission_assigned_assets", missionId, mission.getAssignedAssetIds().getAssetId());
    }

    private static void insertReferences(Connection connection, String table, String missionId, List<String> references) throws SQLException {
        if (references.isEmpty()) return;
        try (PreparedStatement statement = connection.prepareStatement("INSERT INTO " + table + " (mission_id, reference) VALUES (?, ?)")) {
            for (String reference : references) {
                statement.setString(1, missionId);
                statement.setString(2, reference);
                statement.addBatch();
            }
            statement.executeBatch();
        }
    }

    private static void insertChange(Connection connection, BigInteger changeId, String missionId, Operation operation, String stamp,
                                     MutationHeaders audit, Status previous, Status resulting, CostAudit estimate, CostAudit actual) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(INSERT_CHANGE)) {
            statement.setBigDecimal(1, new BigDecimal(changeId));
            statement.setString(2, missionId);
            statement.setString(3, operation.value());
            statement.setString(4, stamp);
            statement.setString(5, audit.changedBy());
            statement.setString(6, audit.orderedBy());
            text(statement, 7, previous == null ? null : previous.value());
            statement.setString(8, resulting.value());
            decimal(statement, 9, estimate.resulting());
            decimal(statement, 10, estimate.change());
            decimal(statement, 11, actual.resulting());
            decimal(statement, 12, actual.change());
            statement.setString(13, audit.summary());
            statement.executeUpdate();
        }
    }

    private static BigDecimal credits(String text) { return text == null ? null : new BigDecimal(text); }

    private static void text(PreparedStatement statement, int index, String value) throws SQLException {
        if (value == null) statement.setNull(index, Types.VARCHAR);
        else statement.setString(index, value);
    }

    private static void decimal(PreparedStatement statement, int index, BigDecimal value) throws SQLException {
        if (value == null) statement.setNull(index, Types.NUMERIC);
        else statement.setBigDecimal(index, value);
    }

    // --- reads -----------------------------------------------------------------------------------------------------

    /** Row offset of the requested page, or -1 when the page lies beyond the last page (an empty page, not an error). */
    static long offset(Query.Paging paging, long total) {
        BigInteger size = BigInteger.valueOf(paging.pageSize());
        BigInteger pages = BigInteger.valueOf(total).add(size).subtract(BigInteger.ONE).divide(size);
        if (paging.page().compareTo(pages) > 0) return -1;
        return paging.page().subtract(BigInteger.ONE).multiply(size).longValueExact();
    }

    private static long count(Connection connection, String sql, List<String> binds) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            bind(statement, binds);
            try (ResultSet rows = statement.executeQuery()) {
                rows.next();
                return rows.getLong(1);
            }
        }
    }

    private static int bind(PreparedStatement statement, List<String> binds) throws SQLException {
        int index = 1;
        for (String value : binds) statement.setString(index++, value);
        return index;
    }

    private static Mission mission(ResultSet rows) throws SQLException {
        var mission = new Mission();
        mission.setMissionId(rows.getString(1));
        mission.setTitle(rows.getString(2));
        mission.setType(MissionType.fromValue(rows.getString(3)));
        mission.setClassification(Classification.fromValue(rows.getString(4)));
        mission.setStatus(Status.fromValue(rows.getString(5)));
        mission.setPriority(Integer.toString(rows.getInt(6)));
        mission.setStardate(rows.getString(7));
        mission.setDurationHours(Integer.toString(rows.getInt(8)));
        mission.setObjective(rows.getString(9));
        var location = new Location();
        location.setType(LocationType.fromValue(rows.getString(10)));
        location.setName(rows.getString(11));
        location.setCoordinates(rows.getString(12));
        location.setTravelVector(rows.getString(13));
        mission.setLocation(location);
        mission.setIssuingAuthority(IssuingAuthority.fromValue(rows.getString(14)));
        mission.setCommandingOfficerId(rows.getString(15));
        mission.setEstimatedCostCredits(rows.getString(16));
        mission.setActualCostCredits(rows.getString(17));
        mission.setOutcome(rows.getString(18));
        mission.setLastUpdated(rows.getString(19));
        // The containers occur exactly once, empty when the mission has no members.
        mission.setAssignedCrewIds(new CrewIds());
        mission.setParticipantIds(new ParticipantIds());
        mission.setAssignedAssetIds(new AssetIds());
        return mission;
    }

    private static void attachCollections(Connection connection, List<Mission> missions) throws SQLException {
        if (missions.isEmpty()) return;
        Map<String, Mission> byId = new HashMap<>();
        for (Mission mission : missions) byId.put(mission.getMissionId(), mission);
        String marks = String.join(",", Collections.nCopies(missions.size(), "?"));
        Map<String, List<String>> crew = members(connection, "mission_assigned_crew", marks, byId);
        Map<String, List<String>> participants = members(connection, "mission_participants", marks, byId);
        Map<String, List<String>> assets = members(connection, "mission_assigned_assets", marks, byId);
        for (Mission mission : missions) {
            String id = mission.getMissionId();
            mission.getAssignedCrewIds().getCrewId().addAll(crew.getOrDefault(id, List.of()));
            mission.getParticipantIds().getParticipantId().addAll(participants.getOrDefault(id, List.of()));
            mission.getAssignedAssetIds().getAssetId().addAll(assets.getOrDefault(id, List.of()));
        }
    }

    /** Members per mission in canonical order: ascending ordinal comparison of the reference text, not numeric suffix. */
    private static Map<String, List<String>> members(Connection connection, String table, String marks, Map<String, Mission> byId) throws SQLException {
        Map<String, List<String>> result = new HashMap<>();
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT mission_id, reference FROM " + table + " WHERE mission_id IN (" + marks + ")")) {
            int index = 1;
            for (String id : byId.keySet()) statement.setString(index++, id);
            try (ResultSet rows = statement.executeQuery()) {
                while (rows.next()) result.computeIfAbsent(rows.getString(1), k -> new ArrayList<>()).add(rows.getString(2));
            }
        }
        for (List<String> references : result.values()) Collections.sort(references);
        return result;
    }

    private static Change change(ResultSet rows) throws SQLException {
        var change = new Change();
        change.setChangeId(rows.getString(1));
        change.setMissionId(rows.getString(2));
        change.setOperation(Operation.fromValue(rows.getString(3)));
        change.setChangedAt(rows.getString(4));
        change.setChangedBy(rows.getString(5));
        change.setOrderedBy(rows.getString(6));
        String previous = rows.getString(7);
        if (previous != null) change.setPreviousStatus(Status.fromValue(previous));
        change.setNewStatus(Status.fromValue(rows.getString(8)));
        change.setEstimatedCostCredits(rows.getString(9));
        change.setEstimatedCostCreditsChange(rows.getString(10));
        change.setActualCostCredits(rows.getString(11));
        change.setActualCostCreditsChange(rows.getString(12));
        change.setSummary(rows.getString(13));
        return change;
    }
}
