package lab.federation.adapters.personnel;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.TimeUnit;
import lab.federation.common.HttpResult;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * One SOAP 1.1 call to the Personnel v2 service per method call, with short, configurable timeouts. The envelopes are written by
 * hand (the two requests of the contract are a few lines each) and sent with the JDK's HTTP client, so no SOAP stack is needed.
 * It never throws: a failure is a result.
 */
@Component
public class PersonnelClient {
    static final String NAMESPACE = PersonnelXml.NAMESPACE;

    private final HttpClient http;
    private final String url;
    private final long readTimeoutMs;

    public PersonnelClient(@Value("${personnel.service-url}") String serviceUrl,
                           @Value("${personnel.connect-timeout-ms}") long connectTimeoutMs,
                           @Value("${personnel.read-timeout-ms}") long readTimeoutMs) {
        this.url = serviceUrl;
        this.readTimeoutMs = readTimeoutMs;
        this.http = HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connectTimeoutMs)).build();
    }

    /** GetPersonnelMember(personnelId). The id must pass {@link #sendable}. */
    public HttpResult get(String personnelId) {
        return post("GetPersonnelMember", "<GetPersonnelMemberRequest xmlns=\"" + NAMESPACE + "\"><personnelId>" + escape(personnelId)
                + "</personnelId></GetPersonnelMemberRequest>");
    }

    /**
     * ListPersonnelMembers(department, dutyStatus, offset, limit). A null filter is left out; the filters combine with AND in the
     * service. The values are the contract's enum names (the GraphQL enums carry exactly those) and two integers.
     */
    public HttpResult list(String department, String dutyStatus, int offset, int limit) {
        StringBuilder children = new StringBuilder();
        if (department != null) {
            children.append("<department>").append(escape(department)).append("</department>");
        }
        if (dutyStatus != null) {
            children.append("<dutyStatus>").append(escape(dutyStatus)).append("</dutyStatus>");
        }
        children.append("<offset>").append(offset).append("</offset><limit>").append(limit).append("</limit>");
        return post("ListPersonnelMembers", "<ListPersonnelMembersRequest xmlns=\"" + NAMESPACE + "\">" + children + "</ListPersonnelMembersRequest>");
    }

    /**
     * True when the text can be sent as the content of an element: printable ASCII only. Escaping handles the markup characters, but a
     * control character is not legal XML at all, so such an id never leaves the adapter (the service owns the grammar of a valid one).
     */
    static boolean sendable(String text) {
        if (text == null) {
            return false;
        }
        for (int index = 0; index < text.length(); index++) {
            char character = text.charAt(index);
            if (character < 0x20 || character > 0x7E) {
                return false;
            }
        }
        return true;
    }

    static String escape(String text) {
        StringBuilder out = new StringBuilder(text.length());
        for (int index = 0; index < text.length(); index++) {
            char character = text.charAt(index);
            switch (character) {
                case '&' -> out.append("&amp;");
                case '<' -> out.append("&lt;");
                case '>' -> out.append("&gt;");
                case '"' -> out.append("&quot;");
                case '\'' -> out.append("&apos;");
                default -> out.append(character);
            }
        }
        return out.toString();
    }

    static String envelope(String payload) {
        return "<soap:Envelope xmlns:soap=\"" + PersonnelXml.SOAP + "\"><soap:Body>" + payload + "</soap:Body></soap:Envelope>";
    }

    private HttpResult post(String operation, String payload) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofMillis(readTimeoutMs))
                    .header("Content-Type", "text/xml; charset=utf-8").header("Accept", "text/xml")
                    .header("SOAPAction", "\"" + NAMESPACE + ":" + operation + "\"")
                    .POST(HttpRequest.BodyPublishers.ofString(envelope(payload))).build();
            HttpResponse<String> response = http.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                    .orTimeout(readTimeoutMs, TimeUnit.MILLISECONDS).join();
            return HttpResult.answer(response.statusCode(), response.body());
        } catch (Exception failure) {
            return HttpResult.failed(failure);
        }
    }
}
