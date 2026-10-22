package lab.enterprise.missions.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import lab.enterprise.missions.ApiException;
import org.junit.jupiter.api.Test;

class IfMatchTest {
    private static void invalid(String... lines) {
        var e = assertThrows(ApiException.class, () -> IfMatch.changeId(List.of(lines)), String.join(" | ", lines));
        assertEquals(400, e.status);
        assertEquals("INVALID_REQUEST", e.code);
    }

    @Test void oneCanonicalStrongTagYieldsItsChangeId() {
        assertEquals("17", IfMatch.changeId(List.of("\"17\"")));
        assertEquals("9905464", IfMatch.changeId(List.of("\"9905464\"")));
        assertEquals("1", IfMatch.changeId(List.of("\"1\"")));
        // A tag longer than any stored change id is well formed: it simply never matches (412 later).
        assertEquals("1" + "0".repeat(40), IfMatch.changeId(List.of("\"1" + "0".repeat(40) + "\"")));
    }

    @Test void missingHeaderIs428() {
        var e = assertThrows(ApiException.class, () -> IfMatch.changeId(null));
        assertEquals(428, e.status);
        assertEquals("PRECONDITION_REQUIRED", e.code);
        assertEquals(428, assertThrows(ApiException.class, () -> IfMatch.changeId(List.of())).status);
    }

    @Test void wildcardWeakMalformedAndMultipleTagsAre400() {
        invalid("*");
        invalid("W/\"17\"");
        invalid("w/\"17\"");
        invalid("17");
        invalid("\"017\"");
        invalid("\"0\"");
        invalid("\"-5\"");
        invalid("\"1.5\"");
        invalid("\"abc\"");
        invalid("\"\"");
        invalid("");
        invalid(" ");
        invalid("\"17");
        invalid("17\"");
        invalid("'17'");
        invalid("\"17\", \"18\"");
        invalid("\"17\",\"18\"");
        invalid("\"17\" \"18\"");
        invalid("\"17\", *");
        invalid(" \"17\"");
        invalid("\"17\" ");
        invalid("\"17\"", "\"17\"");
        invalid("\"17\"", "*");
    }
}
