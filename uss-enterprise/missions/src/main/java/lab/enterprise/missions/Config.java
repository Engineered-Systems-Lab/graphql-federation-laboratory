package lab.enterprise.missions;

import java.util.Map;
import java.util.regex.Pattern;

/** Service settings from the process environment; the database password is never printed. */
public record Config(String bindHost, int port, String jdbcUrl, String dbUser, String dbPassword, String dbSchema) {
    private static final Pattern SCHEMA = Pattern.compile("[A-Z][A-Z0-9_$]{0,29}");

    public static Config fromEnvironment(Map<String, String> env) {
        String host = env.getOrDefault("MISSIONS_BIND_HOST", "127.0.0.1");
        if (!host.equals("127.0.0.1") && !host.equals("0.0.0.0"))
            throw new IllegalArgumentException("MISSIONS_BIND_HOST must be 127.0.0.1 or 0.0.0.0");
        int port = Integer.parseInt(env.getOrDefault("MISSIONS_PORT", "8080"));
        if (port < 1 || port > 65535) throw new IllegalArgumentException("MISSIONS_PORT must be 1..65535");
        String schema = env.getOrDefault("MISSIONS_DB_SCHEMA", "MISSIONS_LAB");
        if (!SCHEMA.matcher(schema).matches()) throw new IllegalArgumentException("MISSIONS_DB_SCHEMA is not a plain Oracle identifier");
        return new Config(host, port, required(env, "MISSIONS_JDBC_URL"), required(env, "MISSIONS_DB_USER"),
                required(env, "MISSIONS_DB_PASSWORD"), schema);
    }

    private static String required(Map<String, String> env, String key) {
        String value = env.get(key);
        if (value == null || value.isEmpty()) throw new IllegalArgumentException(key + " is required");
        return value;
    }
}
