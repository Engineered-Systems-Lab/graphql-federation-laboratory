package lab.enterprise.missions.api;

import java.math.BigInteger;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import lab.enterprise.missions.ApiException;

/** Query-string validation: recognized values are exact tokens, unknown or repeated parameters are 400 INVALID_REQUEST. */
public final class Query {
    public static final Set<String> MISSION_TYPES = Set.of("DIPLOMATIC", "EXPLORATION", "SCIENTIFIC", "FIRST_CONTACT", "MEDICAL",
            "RESCUE", "HUMANITARIAN", "SECURITY", "TACTICAL", "TRANSPORT", "MAINTENANCE");
    public static final Set<String> CLASSIFICATIONS = Set.of("UNCLASSIFIED", "SECRET", "TOP_SECRET");
    public static final Set<String> STATUSES = Set.of("PLANNED", "AUTHORIZED", "ACTIVE", "POSTPONED", "COMPLETED", "FAILED", "CANCELLED");
    public static final Set<String> LOCATION_TYPES = Set.of("PLANET", "STARBASE", "VESSEL", "SECTOR", "DEEP_SPACE", "ENTERPRISE", "OTHER");
    public static final Set<String> AUTHORITIES = Set.of("STARFLEET_COMMAND", "ENTERPRISE_COMMAND", "STARFLEET_MEDICAL",
            "STARFLEET_SCIENCE", "STARFLEET_SECURITY", "FEDERATION_COUNCIL");
    private static final Set<String> RECOGNIZED = Set.of("type", "classification", "status", "priority", "issuingAuthority",
            "commandingOfficerId", "assignedCrewId", "assignedAssetId", "locationType", "page", "pageSize");
    static final Pattern PAGE = Pattern.compile("[1-9][0-9]*");
    static final Pattern PAGE_SIZE = Pattern.compile("[1-9]|[1-4][0-9]|50");
    static final Pattern PRIORITY = Pattern.compile("[1-5]");
    static final Pattern CREW = Pattern.compile("C-[1-9][0-9]*");
    static final Pattern ASSET = Pattern.compile("[A-Z]{2,5}-[1-9][0-9]*");
    static final Pattern MISSION_ID = Pattern.compile("ST-[A-Z0-9]{9}");

    /** Validated paging: the request's own canonical page text plus numeric values. */
    public record Paging(String pageText, BigInteger page, int pageSize) { }

    /** Validated list request. Filters keep declaration order so the SQL text is deterministic. */
    public record MissionQuery(Map<String, String> filters, Paging paging) { }

    private Query() { }

    public static boolean validMissionId(String id) { return MISSION_ID.matcher(id).matches(); }

    public static MissionQuery missions(Map<String, List<String>> parameters) {
        for (String key : parameters.keySet())
            if (!RECOGNIZED.contains(key)) throw ApiException.invalidRequest("Unknown query parameter: " + printable(key));
        Map<String, String> filters = new LinkedHashMap<>();
        filter(parameters, filters, "type", MISSION_TYPES, null);
        filter(parameters, filters, "classification", CLASSIFICATIONS, null);
        filter(parameters, filters, "status", STATUSES, null);
        filter(parameters, filters, "priority", null, PRIORITY);
        filter(parameters, filters, "issuingAuthority", AUTHORITIES, null);
        filter(parameters, filters, "commandingOfficerId", null, CREW);
        filter(parameters, filters, "assignedCrewId", null, CREW);
        filter(parameters, filters, "assignedAssetId", null, ASSET);
        filter(parameters, filters, "locationType", LOCATION_TYPES, null);
        return new MissionQuery(filters, paging(parameters));
    }

    public static Paging changes(Map<String, List<String>> parameters) {
        for (String key : parameters.keySet())
            if (!key.equals("page") && !key.equals("pageSize")) throw ApiException.invalidRequest("Unknown query parameter: " + printable(key));
        return paging(parameters);
    }

    private static Paging paging(Map<String, List<String>> parameters) {
        String page = single(parameters, "page");
        String size = single(parameters, "pageSize");
        if (page == null) page = "1";
        if (size == null) size = "20";
        if (!PAGE.matcher(page).matches()) throw ApiException.invalidRequest("page must be a positive integer");
        if (!PAGE_SIZE.matcher(size).matches()) throw ApiException.invalidRequest("pageSize must be 1..50");
        return new Paging(page, new BigInteger(page), Integer.parseInt(size));
    }

    private static void filter(Map<String, List<String>> parameters, Map<String, String> out, String name, Set<String> tokens, Pattern pattern) {
        String value = single(parameters, name);
        if (value == null) return;
        boolean valid = tokens != null ? tokens.contains(value) : pattern.matcher(value).matches();
        if (!valid) throw ApiException.invalidRequest("Invalid value for " + name);
        out.put(name, value);
    }

    private static String single(Map<String, List<String>> parameters, String name) {
        List<String> values = parameters.get(name);
        if (values == null) return null;
        if (values.size() != 1) throw ApiException.invalidRequest("Repeated query parameter: " + name);
        return values.get(0);
    }

    /** Echoed names are shortened and stripped of control characters so messages stay valid XML text. */
    private static String printable(String text) {
        String clean = text.codePoints().filter(c -> c >= 0x20 && c != 0x7F).limit(40)
                .collect(StringBuilder::new, StringBuilder::appendCodePoint, StringBuilder::append).toString();
        return clean.isEmpty() ? "(empty)" : clean;
    }
}
