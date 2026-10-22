package lab.enterprise.missions.negotiation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import lab.enterprise.missions.ApiException;
import org.junit.jupiter.api.Test;

class ContentTypeTest {
    private static void accepted(String... lines) { ContentType.requireXml(List.of(lines)); }

    private static void unsupported(String... lines) {
        var e = assertThrows(ApiException.class, () -> ContentType.requireXml(List.of(lines)), String.join(" | ", lines));
        assertEquals(415, e.status);
        assertEquals("UNSUPPORTED_MEDIA_TYPE", e.code);
    }

    @Test void applicationXmlWithOrWithoutUtf8CharsetIsAccepted() {
        for (String ok : new String[] {"application/xml", "APPLICATION/XML", "Application/Xml", "application/xml;charset=UTF-8",
                "application/xml; charset=utf-8", "application/xml;CHARSET=Utf-8", "application/xml; charset=\"utf-8\"",
                "application/xml ; charset=utf-8", "application/xml;\tcharset=UTF-8"})
            accepted(ok);
    }

    @Test void missingHeaderIsUnsupported() {
        var e = assertThrows(ApiException.class, () -> ContentType.requireXml(null));
        assertEquals(415, e.status);
        assertEquals(415, assertThrows(ApiException.class, () -> ContentType.requireXml(List.of())).status);
    }

    @Test void otherTypesAreNotAliases() {
        for (String type : new String[] {"text/xml", "application/json", "application/atom+xml", "application/xml-dtd", "application/*",
                "*/*", "application", "application/", "/xml", "application/xml/x", "multipart/form-data", "application/x-www-form-urlencoded",
                "", " "})
            unsupported(type);
    }

    @Test void otherCharsetsAndParametersAreUnsupported() {
        for (String type : new String[] {"application/xml;charset=ISO-8859-1", "application/xml;charset=utf-16", "application/xml;charset=utf8",
                "application/xml;charset=\"utf-8", "application/xml;charset=", "application/xml;charset", "application/xml;=utf-8",
                "application/xml;version=1.0", "application/xml;q=1", "application/xml;charset=utf-8;boundary=x",
                "application/xml;charset=utf-8;charset=utf-8", "application/xml;charset=utf-8;CHARSET=utf-8", "application/xml;",
                "application/xml;;charset=utf-8", "application/xml;charset = utf-8", "application/xml;charset=\"utf-8\"x"})
            unsupported(type);
    }

    @Test void moreThanOneHeaderLineIsUnsupportedEvenWhenEachIsValid() {
        unsupported("application/xml", "application/xml");
        unsupported("application/xml;charset=utf-8", "application/xml");
    }
}
