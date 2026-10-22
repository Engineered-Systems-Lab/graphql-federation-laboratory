package lab.federation.adapters.missions;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import lab.federation.common.HttpResult;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * One GET to the Missions service per call, with short, configurable timeouts. It never throws: a failure is a result. It asks for
 * XML and ignores the ETag header: the adapter only reads.
 */
@Component
public class MissionsClient {
    private final HttpClient http;
    private final String base;
    private final long readTimeoutMs;

    public MissionsClient(@Value("${missions.service-url}") String serviceUrl,
                          @Value("${missions.connect-timeout-ms}") long connectTimeoutMs,
                          @Value("${missions.read-timeout-ms}") long readTimeoutMs) {
        this.base = serviceUrl.endsWith("/") ? serviceUrl.substring(0, serviceUrl.length() - 1) : serviceUrl;
        this.readTimeoutMs = readTimeoutMs;
        this.http = HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connectTimeoutMs)).build();
    }

    /** GET /missions/{missionId} */
    public HttpResult mission(String missionId) {
        return get("/missions/" + encode(missionId));
    }

    /**
     * GET /missions with the filters that are present (a null value is left out), in the order the map gives, then page and pageSize
     * (the service takes pages from 1 and sizes from 1 to 50).
     */
    public HttpResult list(Map<String, String> filters, long page, int pageSize) {
        StringBuilder query = new StringBuilder();
        filters.forEach((name, value) -> {
            if (value != null) {
                query.append(query.isEmpty() ? '?' : '&').append(name).append('=').append(encode(value));
            }
        });
        query.append(query.isEmpty() ? '?' : '&').append("page=").append(page).append("&pageSize=").append(pageSize);
        return get("/missions" + query);
    }

    private HttpResult get(String pathAndQuery) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(base + pathAndQuery))
                    .timeout(Duration.ofMillis(readTimeoutMs)).header("Accept", "application/xml").GET().build();
            HttpResponse<String> response = http.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                    .orTimeout(readTimeoutMs, TimeUnit.MILLISECONDS).join();
            return HttpResult.answer(response.statusCode(), response.body());
        } catch (Exception failure) {
            return HttpResult.failed(failure);
        }
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }
}
