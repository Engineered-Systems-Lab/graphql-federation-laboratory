package lab.federation.adapters.assets;

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

/** One GET to the Assets service per call, with short, configurable timeouts. It never throws: a failure is a result. */
@Component
public class AssetsClient {
    private final HttpClient http;
    private final String base;
    private final long readTimeoutMs;

    public AssetsClient(@Value("${assets.service-url}") String serviceUrl,
                        @Value("${assets.connect-timeout-ms}") long connectTimeoutMs,
                        @Value("${assets.read-timeout-ms}") long readTimeoutMs) {
        this.base = serviceUrl.endsWith("/") ? serviceUrl.substring(0, serviceUrl.length() - 1) : serviceUrl;
        this.readTimeoutMs = readTimeoutMs;
        this.http = HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connectTimeoutMs)).build();
    }

    /** GET /assets/{assetId} */
    public HttpResult asset(String assetId) {
        return get("/assets/" + encode(assetId));
    }

    /** GET /assets with the filters that are present (a null value is left out), the offset and the limit (1 to 50 for the service). */
    public HttpResult list(Map<String, String> filters, int offset, int limit) {
        StringBuilder query = new StringBuilder();
        filters.forEach((name, value) -> {
            if (value != null) {
                query.append(query.isEmpty() ? '?' : '&').append(name).append('=').append(encode(value));
            }
        });
        query.append(query.isEmpty() ? '?' : '&').append("offset=").append(offset).append("&limit=").append(limit);
        return get("/assets" + query);
    }

    private HttpResult get(String pathAndQuery) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(base + pathAndQuery))
                    .timeout(Duration.ofMillis(readTimeoutMs)).header("Accept", "application/json").GET().build();
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
