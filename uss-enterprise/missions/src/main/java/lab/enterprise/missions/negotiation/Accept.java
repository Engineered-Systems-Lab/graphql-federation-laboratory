package lab.enterprise.missions.negotiation;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;
import lab.enterprise.missions.ApiException;

/**
 * The Missions Accept grammar (D034), independent of Jersey's own matching.
 * Ranges application/xml, application/* and star-slash-star match; only q and charset=utf-8 are honored,
 * any other parameter makes that range non-matching; the most specific matching range decides and q=0 excludes.
 */
public final class Accept {
    private static final String TOKEN = "[!#$%&'*+.^_`|~0-9A-Za-z-]+";
    private static final Pattern RANGE = Pattern.compile(TOKEN + "/" + TOKEN);
    private static final Pattern NAME = Pattern.compile(TOKEN);
    private static final Pattern QVALUE = Pattern.compile("0(\\.[0-9]{0,3})?|1(\\.0{0,3})?");
    private static final Pattern TOKEN_ONLY = Pattern.compile(TOKEN);

    private Accept() { }

    /** True when an XML representation is acceptable; a malformed header is a 400 INVALID_REQUEST. */
    public static boolean acceptsXml(List<String> headerLines) {
        if (headerLines == null || headerLines.isEmpty()) return true;
        String joined = String.join(",", headerLines);
        if (joined.trim().isEmpty()) throw ApiException.invalidRequest("Empty Accept header");
        int bestSpecificity = 0;
        double bestQ = 0;
        boolean any = false;
        for (String element : split(joined, ',')) {
            if (element.trim().isEmpty()) continue;
            any = true;
            List<String> parts = split(element, ';');
            String range = parts.get(0).trim().toLowerCase(Locale.ROOT);
            if (!RANGE.matcher(range).matches()) throw ApiException.invalidRequest("Malformed Accept media range");
            boolean applicable = true;
            Double q = null;
            for (String parameter : parts.subList(1, parts.size())) {
                int eq = parameter.indexOf('=');
                if (eq < 0) throw ApiException.invalidRequest("Malformed Accept parameter");
                String name = parameter.substring(0, eq).trim().toLowerCase(Locale.ROOT);
                String value = parameter.substring(eq + 1).trim();
                if (!NAME.matcher(name).matches() || value.isEmpty()) throw ApiException.invalidRequest("Malformed Accept parameter");
                if (name.equals("q")) {
                    if (q != null || !QVALUE.matcher(value).matches()) throw ApiException.invalidRequest("Invalid Accept quality value");
                    q = Double.parseDouble(value);
                } else if (name.equals("charset") && unquote(value).equalsIgnoreCase("utf-8")) {
                    continue;
                } else {
                    applicable = false;
                }
            }
            int specificity = !applicable ? 0 : range.equals("application/xml") ? 3 : range.equals("application/*") ? 2 : range.equals("*/*") ? 1 : 0;
            if (specificity == 0) continue;
            double quality = q == null ? 1.0 : q;
            if (specificity > bestSpecificity || specificity == bestSpecificity && quality > bestQ) {
                bestSpecificity = specificity;
                bestQ = quality;
            }
        }
        if (!any) throw ApiException.invalidRequest("Empty Accept header");
        return bestSpecificity > 0 && bestQ > 0;
    }

    private static String unquote(String value) {
        if (value.length() >= 2 && value.startsWith("\"") && value.endsWith("\"")) return value.substring(1, value.length() - 1);
        return TOKEN_ONLY.matcher(value).matches() ? value : "\u0000";
    }

    /** Splits on a separator outside double-quoted strings; an unterminated quote is malformed. */
    static List<String> split(String text, char separator) {
        List<String> parts = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (quoted && c == '\\' && i + 1 < text.length()) { current.append(c).append(text.charAt(++i)); continue; }
            if (c == '"') quoted = !quoted;
            if (c == separator && !quoted) { parts.add(current.toString()); current.setLength(0); } else current.append(c);
        }
        if (quoted) throw ApiException.invalidRequest("Malformed Accept header");
        parts.add(current.toString());
        return parts;
    }
}
