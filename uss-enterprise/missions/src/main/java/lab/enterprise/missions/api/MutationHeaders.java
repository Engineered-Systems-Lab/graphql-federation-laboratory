package lab.enterprise.missions.api;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.function.Function;
import java.util.regex.Pattern;
import lab.enterprise.missions.ApiException;
import lab.enterprise.missions.domain.MissionRules;
import lab.enterprise.missions.domain.Text;

/**
 * The provenance and audit metadata every POST and PUT carries in headers: who performed it, who ordered it and a
 * human summary. All are 400 INVALID_REQUEST when missing or invalid; none is a Mission XML field.
 */
public record MutationHeaders(String changedBy, String orderedBy, String summary) {
    public static final String USER = "X-Starfleet-User";
    public static final String ORDERED_BY = "X-Starfleet-Ordered-By";
    public static final String SUMMARY = "X-Starfleet-Audit-Summary";
    private static final Pattern CREW = Pattern.compile("C-[1-9][0-9]*");
    private static final int SUMMARY_LIMIT = 256;

    public static MutationHeaders parse(Function<String, List<String>> header) {
        String user = crew(USER, header.apply(USER));
        String orderedBy = crew(ORDERED_BY, header.apply(ORDERED_BY));
        return new MutationHeaders(user, orderedBy, summary(header.apply(SUMMARY)));
    }

    private static String single(String name, List<String> lines) {
        if (lines == null || lines.isEmpty()) throw ApiException.invalidRequest("Missing " + name + " header");
        if (lines.size() != 1) throw ApiException.invalidRequest("Repeated " + name + " header");
        return lines.get(0);
    }

    private static String crew(String name, List<String> lines) {
        String value = single(name, lines);
        if (!CREW.matcher(value).matches()) throw ApiException.invalidRequest(name + " must be a Crew reference such as C-71");
        MissionRules.capacity(name, value);
        return value;
    }

    /**
     * The summary is UTF-8 text. The container hands header bytes over one per char (ISO-8859-1), so the original bytes are
     * recovered and decoded strictly; the text is then kept exactly: no trimming, no normalization.
     */
    static String summary(List<String> lines) {
        String raw = single(SUMMARY, lines);
        byte[] bytes = new byte[raw.length()];
        for (int i = 0; i < bytes.length; i++) {
            char c = raw.charAt(i);
            if (c > 0xFF) throw ApiException.invalidRequest(SUMMARY + " must be UTF-8 text");
            bytes[i] = (byte) c;
        }
        String text;
        try {
            text = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
        } catch (CharacterCodingException e) {
            throw ApiException.invalidRequest(SUMMARY + " must be valid UTF-8 text");
        }
        if (text.isEmpty()) throw ApiException.invalidRequest(SUMMARY + " must not be empty");
        if (Text.length(text) > SUMMARY_LIMIT) throw ApiException.invalidRequest(SUMMARY + " is longer than 256 characters");
        if (text.codePoints().anyMatch(c -> !Text.xmlChar(c)))
            throw ApiException.invalidRequest(SUMMARY + " contains a character that the XML change log cannot carry");
        if (Text.blank(text)) throw ApiException.invalidRequest(SUMMARY + " must contain a non-whitespace character");
        return text;
    }
}
