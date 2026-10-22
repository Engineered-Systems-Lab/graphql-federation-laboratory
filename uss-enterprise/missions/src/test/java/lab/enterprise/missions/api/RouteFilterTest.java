package lab.enterprise.missions.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class RouteFilterTest {
    @Test void knownShapes() {
        assertTrue(RouteFilter.knownPath("missions"));
        assertTrue(RouteFilter.knownPath("missions/ST-00000LD4O"));
        assertTrue(RouteFilter.knownPath("missions/anything-malformed"));
        assertTrue(RouteFilter.knownPath("missions/ST-00000LD4O/changes"));
    }

    @Test void everythingElseIsUnknown() {
        for (String path : new String[] {"", "/", "missions/", "missions//changes", "missions/ST-00000LD4O/", "missions/x/changes/",
                "missions/x/other", "missions/x/changes/1", "mission", "Missions", "other", "missions/x/y/z"})
            assertFalse(RouteFilter.knownPath(path), "path: " + path);
    }

    @Test void allowListsNameOnlyTheMethodsEachPathSupports() {
        assertEquals("GET, POST", RouteFilter.allow("missions"));
        assertEquals("GET, PUT", RouteFilter.allow("missions/ST-00000LD4O"));
        assertEquals("GET, PUT", RouteFilter.allow("missions/anything-malformed"));
        assertEquals("GET", RouteFilter.allow("missions/ST-00000LD4O/changes"));
    }

    @Test void headAndOptionsAreOnNoPath() {
        for (String path : new String[] {"missions", "missions/ST-00000LD4O", "missions/ST-00000LD4O/changes"})
            for (String method : new String[] {"HEAD", "OPTIONS", "PATCH", "DELETE", "TRACE", "CONNECT", "get", "Post"})
                assertFalse(RouteFilter.methods(path).contains(method), method + " " + path);
        assertTrue(RouteFilter.methods("missions").contains("POST"));
        assertFalse(RouteFilter.methods("missions").contains("PUT"));
        assertTrue(RouteFilter.methods("missions/ST-00000LD4O").contains("PUT"));
        assertFalse(RouteFilter.methods("missions/ST-00000LD4O").contains("POST"));
        assertFalse(RouteFilter.methods("missions/ST-00000LD4O/changes").contains("POST"));
        assertFalse(RouteFilter.methods("missions/ST-00000LD4O/changes").contains("PUT"));
    }
}
