package lab.enterprise.missions.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class MissionsServletTest {
    @Test void aSingleMediaTypeLineIsParseable() {
        for (String ok : new String[] {"application/xml", "text/xml", "application/xml; charset=utf-8", "application/json;q=1", "a/b;c=d"})
            assertTrue(MissionsServlet.parseable(List.of(ok)), ok);
    }

    @Test void whatJerseyCannotReadIsNotParseable() {
        for (String bad : new String[] {"", " ", "application", "/", "a/b;c", "application/xml; charset", "app lication/xml", "/xml"})
            assertFalse(MissionsServlet.parseable(List.of(bad)), "[" + bad + "]");
        assertFalse(MissionsServlet.parseable(List.of("application/xml", "application/xml")));
        assertFalse(MissionsServlet.parseable(List.of()));
    }

    @Test void onlyPostAndPutOnTheirOwnPathsCarryABodyTheContractDecides() {
        assertTrue(MissionsServlet.carriesBody("POST", "/missions"));
        assertTrue(MissionsServlet.carriesBody("PUT", "/missions/ST-00000LD4O"));
        assertTrue(MissionsServlet.carriesBody("PUT", "/missions/anything"));
        assertFalse(MissionsServlet.carriesBody("PUT", "/missions"));
        assertFalse(MissionsServlet.carriesBody("POST", "/missions/ST-00000LD4O"));
        assertFalse(MissionsServlet.carriesBody("POST", "/missions/ST-00000LD4O/changes"));
        assertFalse(MissionsServlet.carriesBody("POST", "/other"));
        assertFalse(MissionsServlet.carriesBody("POST", "/missions/"));
        for (String method : new String[] {"GET", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"})
            assertFalse(MissionsServlet.carriesBody(method, "/missions"), method);
        assertEquals(List.of("GET", "POST"), RouteFilter.methods("missions"));
    }
}
