package lab.enterprise.missions.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lab.enterprise.missions.ApiException;
import org.junit.jupiter.api.Test;

class MutationHeadersTest {
    /** What the servlet container hands over: each header byte as one char. */
    private static String wire(String text) { return new String(text.getBytes(StandardCharsets.UTF_8), StandardCharsets.ISO_8859_1); }

    private static MutationHeaders parse(String user, String ordered, String summary) {
        Map<String, List<String>> headers = new HashMap<>();
        if (user != null) headers.put(MutationHeaders.USER, List.of(user));
        if (ordered != null) headers.put(MutationHeaders.ORDERED_BY, List.of(ordered));
        if (summary != null) headers.put(MutationHeaders.SUMMARY, List.of(summary));
        return MutationHeaders.parse(headers::get);
    }

    private static void invalid(String user, String ordered, String summary) {
        var e = assertThrows(ApiException.class, () -> parse(user, ordered, summary), user + "|" + ordered + "|" + summary);
        assertEquals(400, e.status);
        assertEquals("INVALID_REQUEST", e.code);
    }

    @Test void validHeadersAreReturnedExactly() {
        var headers = parse("C-71", "C-1", wire("Reviewed and approved"));
        assertEquals(new MutationHeaders("C-71", "C-1", "Reviewed and approved"), headers);
        assertEquals("C-71", parse("C-71", "C-71", "x").orderedBy());
    }

    @Test void crewReferencesFollowTheGrammarExactly() {
        for (String bad : new String[] {"P-71", "O-71", "c-71", "C-0", "C-071", "C-", "C71", "C-7a", "C--7", "C-+7", "C-7 ", " C-7", "CRW-71", "SH-17", ""}) {
            invalid(bad, "C-1", "x");
            invalid("C-1", bad, "x");
        }
        invalid(null, "C-1", "x");
        invalid("C-1", null, "x");
        invalid("C-1", "C-1", null);
    }

    @Test void aRepeatedHeaderLineIsRefusedAsAmbiguous() {
        var e = assertThrows(ApiException.class, () -> MutationHeaders.parse(name -> List.of("C-1", "C-2")));
        assertEquals(400, e.status);
        var summary = assertThrows(ApiException.class, () -> MutationHeaders.summary(List.of("a", "b")));
        assertEquals(400, summary.status);
    }

    @Test void theSummaryIsDecodedAsUtf8AndKeptExactly() {
        for (String text : new String[] {"Prüfung für die Brücke", "日本語のメモ", "Rocket 🚀 launched", "inner  double  spaces", "tab\there",
                " edge-nbsp ", "a　b", "​zero-width", "　x　", "Ω≈ç√∫", "é combining"})
            assertEquals(text, MutationHeaders.summary(List.of(wire(text))), text);
    }

    @Test void theSummaryBoundIsTwoHundredFiftySixCodePoints() {
        String limit = "🚀".repeat(256);
        assertEquals(limit, MutationHeaders.summary(List.of(wire(limit))));
        String over = limit + "a";
        var e = assertThrows(ApiException.class, () -> MutationHeaders.summary(List.of(wire(over))));
        assertEquals(400, e.status);
        // 256 code points but 512 UTF-16 units and 1024 bytes: only the code point count decides.
        assertEquals(512, limit.length());
    }

    @Test void anEmptyOrWhitespaceOnlySummaryIsRefused() {
        for (String blank : new String[] {"", " ", "\t", "\u000B", "\u000C", "\u001C", "\u001F", " ", " ", " ", " ", " ", " ",
                " ", " ", "　", " \t　 \u000B "})
            invalid("C-1", "C-1", wire(blank));
        // Not whitespace under the contract: accepted.
        for (String ok : new String[] {" ", " ", " ", "\u0085", "​", "﻿"})
            assertEquals(ok, MutationHeaders.summary(List.of(wire(ok))));
    }

    @Test void invalidUtf8AndNonByteCharsAreRefused() {
        invalid("C-1", "C-1", new String(new byte[] {(byte) 0xC3, (byte) 0x28}, StandardCharsets.ISO_8859_1));
        invalid("C-1", "C-1", new String(new byte[] {(byte) 0xFF}, StandardCharsets.ISO_8859_1));
        invalid("C-1", "C-1", new String(new byte[] {(byte) 0xC0, (byte) 0xAF}, StandardCharsets.ISO_8859_1));
        invalid("C-1", "C-1", new String(new byte[] {(byte) 0xED, (byte) 0xA0, (byte) 0x80}, StandardCharsets.ISO_8859_1));
        invalid("C-1", "C-1", "caféŒ");
        invalid("C-1", "C-1", "あ");
    }

    @Test void charactersTheChangeLogCannotCarryAreRefused() {
        for (String bad : new String[] {"a\u0000b", "a\u0001b", "a\u000Bb", "a\u001Fb", "a￾b", "a￿b"})
            invalid("C-1", "C-1", wire(bad));
        for (String ok : new String[] {"a\tb", "a\u007Fb", "a\u0080b", "a�b"})
            assertEquals(ok, MutationHeaders.summary(List.of(wire(ok))));
    }

    @Test void anActorReferenceBeyondFiftyBytesIs422NotAGrammarFailure() {
        String tooLong = "C-" + "9".repeat(49);
        for (String[] pair : new String[][] {{tooLong, "C-1"}, {"C-1", tooLong}}) {
            var e = assertThrows(ApiException.class, () -> parse(pair[0], pair[1], "x"));
            assertEquals(422, e.status);
            assertEquals("DOMAIN_VALIDATION_FAILED", e.code);
        }
        assertEquals("C-" + "9".repeat(48), parse("C-" + "9".repeat(48), "C-1", "x").changedBy());
    }
}
