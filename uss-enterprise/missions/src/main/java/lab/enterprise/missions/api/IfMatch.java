package lab.enterprise.missions.api;

import java.util.List;
import java.util.regex.Pattern;
import lab.enterprise.missions.ApiException;

/** PUT If-Match: exactly one explicit strong tag in the canonical quoted changeId form, or a precise failure. */
public final class IfMatch {
    private static final Pattern STRONG_TAG = Pattern.compile("\"([1-9][0-9]*)\"");

    private IfMatch() { }

    /** @return the changeId text the tag names; 428 when the header is missing, 400 when it is anything but one canonical tag */
    public static String changeId(List<String> headerLines) {
        if (headerLines == null || headerLines.isEmpty())
            throw new ApiException(428, "PRECONDITION_REQUIRED", "If-Match is required for a replacement");
        if (headerLines.size() != 1) throw ApiException.invalidRequest("Exactly one If-Match header with one strong tag is required");
        var matcher = STRONG_TAG.matcher(headerLines.get(0));
        if (!matcher.matches()) throw ApiException.invalidRequest("If-Match must be one strong tag such as \"17\"");
        return matcher.group(1);
    }
}
