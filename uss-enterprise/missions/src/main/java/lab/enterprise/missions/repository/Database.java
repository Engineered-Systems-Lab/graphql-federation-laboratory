package lab.enterprise.missions.repository;

import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import lab.enterprise.missions.Config;
import org.apache.tomcat.jdbc.pool.DataSource;
import org.apache.tomcat.jdbc.pool.PoolProperties;

/** Plain JDBC behind Tomcat's own pool. Connections open lazily, so a database outage is a per-request 500, not a startup failure. */
public final class Database implements AutoCloseable {
    /** A unit of database work on one transaction. */
    @FunctionalInterface
    public interface Work<T> { T run(Connection connection) throws SQLException; }

    private final DataSource pool;

    public Database(Config config) {
        var properties = new PoolProperties();
        properties.setDriverClassName("oracle.jdbc.OracleDriver");
        properties.setUrl(config.jdbcUrl());
        properties.setUsername(config.dbUser());
        properties.setPassword(config.dbPassword());
        properties.setInitialSize(0);
        properties.setMinIdle(0);
        properties.setMaxActive(8);
        properties.setMaxWait(10_000);
        properties.setTestOnBorrow(true);
        properties.setValidationQuery("SELECT 1 FROM DUAL");
        properties.setDefaultAutoCommit(false);
        // The schema name was validated as a plain identifier when the configuration was read.
        properties.setInitSQL("ALTER SESSION SET CURRENT_SCHEMA = " + config.dbSchema());
        this.pool = new DataSource(properties);
    }

    /** Runs the work in one read-only transaction so counts and rows of a response agree. */
    public <T> T read(Work<T> work) throws SQLException {
        try (Connection connection = pool.getConnection()) {
            try (Statement statement = connection.createStatement()) {
                statement.execute("SET TRANSACTION READ ONLY");
            }
            try {
                return work.run(connection);
            } finally {
                connection.rollback();
            }
        }
    }

    /**
     * Runs the work as one transaction that commits only if it returns. Any failure, a contract failure thrown by the
     * work included, rolls the whole transaction back, so a mutation, its audit event and the clock advance never part.
     */
    public <T> T write(Work<T> work) throws SQLException {
        try (Connection connection = pool.getConnection()) {
            try {
                T result = work.run(connection);
                connection.commit();
                return result;
            } catch (Throwable failure) {
                try {
                    connection.rollback();
                } catch (SQLException rollbackFailure) {
                    failure.addSuppressed(rollbackFailure);
                }
                throw failure;
            }
        }
    }

    @Override public void close() { pool.close(); }
}
