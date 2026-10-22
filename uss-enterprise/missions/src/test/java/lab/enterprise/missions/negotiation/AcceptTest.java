package lab.enterprise.missions.negotiation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import lab.enterprise.missions.ApiException;
import org.junit.jupiter.api.Test;

class AcceptTest {
    private static boolean ok(String... lines) { return Accept.acceptsXml(List.of(lines)); }

    @Test void absentHeaderAcceptsXml() {
        assertTrue(Accept.acceptsXml(null));
        assertTrue(Accept.acceptsXml(List.of()));
    }

    @Test void acceptedRanges() {
        assertTrue(ok("application/xml"));
        assertTrue(ok("APPLICATION/XML"));
        assertTrue(ok("*/*"));
        assertTrue(ok("application/*"));
        assertTrue(ok("text/html, application/xml;q=0.1"));
        assertTrue(ok("application/xml;charset=utf-8"));
        assertTrue(ok("application/xml;charset=\"UTF-8\""));
        assertTrue(ok("text/html", "application/xml"));
    }

    @Test void noAcceptableRangeIsNotAcceptable() {
        assertFalse(ok("application/json"));
        assertFalse(ok("text/xml"));
        assertFalse(ok("application/xhtml+xml"));
    }

    @Test void mostSpecificRangeWinsAndQualityZeroExcludes() {
        assertFalse(ok("*/*, application/xml;q=0"));
        assertFalse(ok("application/*;q=0, */*"));
        assertTrue(ok("application/xml;q=0.5, */*;q=0"));
        assertFalse(ok("application/xml;q=0.000"));
        assertTrue(ok("application/xml;q=1.000"));
    }

    @Test void otherParametersMakeTheRangeNonMatching() {
        assertFalse(ok("application/xml;version=2"));
        assertFalse(ok("application/xml;charset=latin1"));
        assertTrue(ok("application/xml;version=2, */*;q=0.1"));
    }

    @Test void malformedHeadersAreInvalidRequests() {
        for (String bad : new String[] {"", "   ", ",", "application", "application/xml;q=2", "application/xml;q=abc",
                "application/xml;q=0.1234", "application/xml;q=-1", "application/xml;q=1;q=1", "application/xml;q",
                "application/xml;q=", "text/html;x=\"unterminated", "ap plication/xml"}) {
            ApiException e = assertThrows(ApiException.class, () -> ok(bad), "header: " + bad);
            assertEquals(400, e.status);
            assertEquals("INVALID_REQUEST", e.code);
        }
    }

    @Test void multipleHeaderLinesCombine() {
        assertFalse(ok("application/xml;q=0", "text/html"));
        assertTrue(ok("text/html", "*/*"));
    }
}
