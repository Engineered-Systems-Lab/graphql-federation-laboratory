package lab.federation.adapters.assets;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;

/** A stub of the Assets service on loopback: the routes are exact request targets (path and query), the calls are recorded. */
final class StubAssets implements AutoCloseable {
    record Reply(int status, String body, long delayMs) {
    }

    static final String PATH_NOT_FOUND = "{\"code\":\"PATH_NOT_FOUND\",\"message\":\"No such path\"}";
    static final String ASSET_NOT_FOUND = "{\"code\":\"ASSET_NOT_FOUND\",\"message\":\"No such asset\"}";

    private final HttpServer server;
    private final Map<String, Reply> routes = new HashMap<>();
    private final List<String> calls = Collections.synchronizedList(new ArrayList<>());

    StubAssets() throws IOException {
        server = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        server.setExecutor(Executors.newCachedThreadPool());
        server.createContext("/", exchange -> {
            String target = exchange.getRequestURI().getRawPath()
                    + (exchange.getRequestURI().getRawQuery() == null ? "" : "?" + exchange.getRequestURI().getRawQuery());
            calls.add(target);
            Reply reply;
            synchronized (routes) {
                reply = routes.getOrDefault(target, new Reply(404, PATH_NOT_FOUND, 0));
            }
            try {
                if (reply.delayMs() > 0) {
                    Thread.sleep(reply.delayMs());
                }
                byte[] bytes = reply.body().getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.sendResponseHeaders(reply.status(), bytes.length);
                exchange.getResponseBody().write(bytes);
            } catch (InterruptedException | IOException ignored) {
                // the client gave up (a timeout test)
            } finally {
                exchange.close();
            }
        });
        server.start();
    }

    String url() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    void route(String target, int status, String body) {
        route(target, status, body, 0);
    }

    void route(String target, int status, String body, long delayMs) {
        synchronized (routes) {
            routes.put(target, new Reply(status, body, delayMs));
        }
    }

    List<String> calls() {
        synchronized (calls) {
            return new ArrayList<>(calls);
        }
    }

    void reset() {
        synchronized (routes) {
            routes.clear();
        }
        calls.clear();
    }

    @Override
    public void close() {
        server.stop(0);
    }
}
