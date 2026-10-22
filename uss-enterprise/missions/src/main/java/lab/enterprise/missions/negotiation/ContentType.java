package lab.enterprise.missions.negotiation;

import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;
import lab.enterprise.missions.ApiException;

/**
 * The Missions Content-Type grammar for request bodies (D034), independent of Jersey's own matching. The type is
 * application/xml, compared case-insensitively; the only permitted parameter is charset, once, with the value utf-8
 * (quoted or not, any case). A missing header, a second header line, any other parameter or an unparseable value is 415.
 */
public final class ContentType {
    private static final String TOKEN = "[!#$%&'*+.^_`|~0-9A-Za-z-]+";
    private static final Pattern MEDIA_TYPE = Pattern.compile(TOKEN + "/" + TOKEN);
    private static final Pattern NAME = Pattern.compile(TOKEN);
    private static final Pattern VALUE_TOKEN = Pattern.compile(TOKEN);

    private ContentType() { }

    public static void requireXml(List<String> headerLines) {
        if (headerLines == null || headerLines.isEmpty()) throw unsupported("Missing Content-Type; application/xml is required");
        if (headerLines.size() != 1) throw unsupported("Exactly one Content-Type header is required");
        List<String> parts;
        try {
            parts = Accept.split(headerLines.get(0), ';');
        } catch (ApiException e) {
            throw unsupported("Unparseable Content-Type");
        }
        String type = parts.get(0).trim();
        if (!MEDIA_TYPE.matcher(type).matches()) throw unsupported("Unparseable Content-Type");
        if (!type.toLowerCase(Locale.ROOT).equals("application/xml")) throw unsupported("Only application/xml is supported");
        boolean charset = false;
        for (String parameter : parts.subList(1, parts.size())) {
            String text = parameter.trim();
            int eq = text.indexOf('=');
            if (eq <= 0 || eq == text.length() - 1) throw unsupported("Unparseable Content-Type parameter");
            String name = text.substring(0, eq);
            String value = text.substring(eq + 1);
            if (!NAME.matcher(name).matches()) throw unsupported("Unparseable Content-Type parameter");
            if (!name.toLowerCase(Locale.ROOT).equals("charset")) throw unsupported("Unsupported Content-Type parameter");
            if (charset) throw unsupported("Duplicate charset parameter");
            charset = true;
            if (!unquote(value).equalsIgnoreCase("utf-8")) throw unsupported("Only the UTF-8 charset is supported");
        }
    }

    /** A quoted value drops its quotes; a token stays as written; anything else cannot equal utf-8. */
    private static String unquote(String value) {
        if (value.length() >= 2 && value.startsWith("\"") && value.endsWith("\"")) return value.substring(1, value.length() - 1);
        return VALUE_TOKEN.matcher(value).matches() ? value : "\u0000";
    }

    private static ApiException unsupported(String message) { return new ApiException(415, "UNSUPPORTED_MEDIA_TYPE", message); }
}
