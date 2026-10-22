package lab.federation.adapters.missions;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.math.BigDecimal;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * A stub of the Missions service on loopback. Its real answers come from the files of the repository: the released dataset 1.2
 * (its 300 missions, six pages of 50 files, listed in the contract's order) serves GET /missions and GET /missions/{id} with the
 * contract's filters, paging and error bodies,
 * and the contract fixtures are served by route. A route is an exact request target (path and query) and wins over the dataset, so
 * a test can make any call fail. Every request target is recorded.
 */
final class StubMissions implements AutoCloseable {
    record Reply(int status, String body, long delayMs) {
    }

    static final String XML = "application/xml;charset=UTF-8";
    static final String NS = "urn:starfleet:missions:v1";

    static String error(String code) {
        return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<error xmlns=\"" + NS + "\"><code>" + code + "</code><message>Illustrative message.</message></error>";
    }

    /** The repository root, found from the working directory of the test (the module folder, in Docker or on a checkout). */
    static Path root() {
        Path path = Path.of("").toAbsolutePath();
        while (path != null && !Files.isDirectory(path.resolve("uss-enterprise/missions/fixtures"))) {
            path = path.getParent();
        }
        if (path == null) {
            throw new IllegalStateException("The Missions fixtures were not found above " + Path.of("").toAbsolutePath());
        }
        return path;
    }

    static String fixture(String name) {
        return read(root().resolve("uss-enterprise/missions/fixtures").resolve(name));
    }

    /** One numbered page file (1 to 6) of the released dataset 1.2, as the file holds it. */
    static String releasePage(int number) {
        return read(root().resolve("uss-enterprise/missions/datasets/releases/1.2/missions-" + number + ".xml"));
    }

    /** The 300 missions of the released dataset 1.2 in the contract's order: stardate, priority, missionId, ascending (not the file order). */
    static List<String> releaseBlocks() {
        List<String> blocks = new ArrayList<>();
        for (int number = 1; number <= 6; number++) {
            blocks.addAll(missionBlocks(releasePage(number)));
        }
        blocks.sort(Comparator.comparing((String block) -> new BigDecimal(field(block, "stardate")))
                .thenComparing(block -> Integer.parseInt(field(block, "priority"))).thenComparing(block -> field(block, "missionId")));
        return blocks;
    }

    private static String read(Path path) {
        try {
            return Files.readString(path, StandardCharsets.UTF_8);
        } catch (IOException error) {
            throw new IllegalStateException(error);
        }
    }

    /** The blocks <mission>...</mission> of the released list, in the service's order. */
    static List<String> missionBlocks(String listXml) {
        List<String> blocks = new ArrayList<>();
        Matcher matcher = Pattern.compile("(?s)<mission>.*?</mission>").matcher(listXml);
        while (matcher.find()) {
            blocks.add(matcher.group());
        }
        return blocks;
    }

    static String field(String block, String name) {
        Matcher matcher = Pattern.compile("(?s)<" + name + ">(.*?)</" + name + ">").matcher(block);
        return matcher.find() ? matcher.group(1) : null;
    }

    private final HttpServer server;
    private final List<String> blocks = releaseBlocks();
    private final Map<String, Reply> routes = new HashMap<>();
    private final List<String> calls = Collections.synchronizedList(new ArrayList<>());

    StubMissions() throws IOException {
        server = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        server.setExecutor(Executors.newCachedThreadPool());
        server.createContext("/", exchange -> {
            String target = exchange.getRequestURI().getRawPath()
                    + (exchange.getRequestURI().getRawQuery() == null ? "" : "?" + exchange.getRequestURI().getRawQuery());
            calls.add(target);
            Reply reply;
            synchronized (routes) {
                reply = routes.containsKey(target) ? routes.get(target) : dataset(exchange);
            }
            try {
                if (reply.delayMs() > 0) {
                    Thread.sleep(reply.delayMs());
                }
                byte[] bytes = reply.body().getBytes(StandardCharsets.UTF_8);
                if (reply.body().isEmpty()) {
                    exchange.sendResponseHeaders(reply.status(), -1);
                } else {
                    exchange.getResponseHeaders().add("Content-Type", XML);
                    exchange.sendResponseHeaders(reply.status(), bytes.length);
                    exchange.getResponseBody().write(bytes);
                }
            } catch (InterruptedException | IOException ignored) {
                // the client gave up (a timeout test)
            } finally {
                exchange.close();
            }
        });
        server.start();
    }

    // ---- the service, from the released dataset ---------------------------------------------------------------------

    private Reply dataset(HttpExchange exchange) {
        String path = exchange.getRequestURI().getRawPath();
        if (path.equals("/missions")) {
            return list(exchange.getRequestURI().getRawQuery());
        }
        if (path.startsWith("/missions/") && path.indexOf('/', 10) < 0) {
            String id = URLDecoder.decode(path.substring(10), StandardCharsets.UTF_8);
            if (!id.matches("ST-[A-Z0-9]{9}")) {
                return new Reply(400, error("INVALID_MISSION_ID"), 0);
            }
            for (String block : blocks) {
                if (id.equals(field(block, "missionId"))) {
                    return new Reply(200, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + block.replaceFirst("<mission>", "<mission xmlns=\"" + NS + "\">"), 0);
                }
            }
            return new Reply(404, error("MISSION_NOT_FOUND"), 0);
        }
        return new Reply(404, "", 0);
    }

    private Reply list(String rawQuery) {
        Map<String, List<String>> parameters = new LinkedHashMap<>();
        if (rawQuery != null) {
            for (String pair : rawQuery.split("&")) {
                int equals = pair.indexOf('=');
                String name = URLDecoder.decode(equals < 0 ? pair : pair.substring(0, equals), StandardCharsets.UTF_8);
                String value = equals < 0 ? "" : URLDecoder.decode(pair.substring(equals + 1), StandardCharsets.UTF_8);
                parameters.computeIfAbsent(name, key -> new ArrayList<>()).add(value);
            }
        }
        List<String> known = List.of("type", "classification", "status", "priority", "issuingAuthority", "commandingOfficerId", "assignedCrewId",
                "assignedAssetId", "locationType", "page", "pageSize");
        for (Map.Entry<String, List<String>> entry : parameters.entrySet()) {
            if (!known.contains(entry.getKey()) || entry.getValue().size() != 1) {
                return new Reply(400, error("INVALID_REQUEST"), 0);
            }
        }
        String page = parameters.containsKey("page") ? parameters.get("page").get(0) : "1";
        String pageSize = parameters.containsKey("pageSize") ? parameters.get("pageSize").get(0) : "20";
        if (!page.matches("[1-9][0-9]*") || !pageSize.matches("[1-9]|[1-4][0-9]|50")
                || (parameters.containsKey("priority") && !parameters.get("priority").get(0).matches("[1-5]"))
                || (parameters.containsKey("commandingOfficerId") && !parameters.get("commandingOfficerId").get(0).matches("C-[1-9][0-9]*"))
                || (parameters.containsKey("assignedCrewId") && !parameters.get("assignedCrewId").get(0).matches("C-[1-9][0-9]*"))
                || (parameters.containsKey("assignedAssetId") && !parameters.get("assignedAssetId").get(0).matches("[A-Z]{2,5}-[1-9][0-9]*"))) {
            return new Reply(400, error("INVALID_REQUEST"), 0);
        }
        List<String> matching = new ArrayList<>();
        for (String block : blocks) {
            if (matches(block, parameters)) {
                matching.add(block);
            }
        }
        long size = Long.parseLong(pageSize);
        long from = (Long.parseLong(page) - 1) * size;
        List<String> window = from >= matching.size() ? List.of() : matching.subList((int) from, (int) Math.min(matching.size(), from + size));
        long totalPages = (matching.size() + size - 1) / size;
        return new Reply(200, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<missionList xmlns=\"" + NS + "\"><page>" + page + "</page><pageSize>" + pageSize
                + "</pageSize><totalCount>" + matching.size() + "</totalCount><totalPages>" + totalPages + "</totalPages>" + String.join("", window)
                + "</missionList>", 0);
    }

    private static boolean matches(String block, Map<String, List<String>> parameters) {
        String location = field(block, "location");
        String top = block.replaceFirst("(?s)<location>.*?</location>", "");
        for (Map.Entry<String, List<String>> entry : parameters.entrySet()) {
            String value = entry.getValue().get(0);
            boolean ok = switch (entry.getKey()) {
                case "type", "classification", "status", "priority", "issuingAuthority", "commandingOfficerId" -> value.equals(field(top, entry.getKey()));
                case "locationType" -> value.equals(field(location, "type"));
                case "assignedCrewId" -> block.contains("<crewId>" + value + "</crewId>");
                case "assignedAssetId" -> block.contains("<assetId>" + value + "</assetId>");
                default -> true;
            };
            if (!ok) {
                return false;
            }
        }
        return true;
    }

    // ---- control ----------------------------------------------------------------------------------------------------

    String url() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    int port() {
        return server.getAddress().getPort();
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
