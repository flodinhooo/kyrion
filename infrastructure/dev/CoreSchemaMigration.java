import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.flywaydb.core.Flyway;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.*;
import java.util.*;

/** Standalone Flyway only. No application classes or Spring are on this classpath. */
public final class CoreSchemaMigration {
    private static final ObjectMapper JSON = new ObjectMapper();

    static void require(boolean condition, String code) {
        if (!condition) throw new IllegalStateException(code);
    }

    static String hash(String text) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)));
    }

    static String scalar(Connection db, String sql) throws Exception {
        try (Statement statement = db.createStatement(); ResultSet rows = statement.executeQuery(sql)) {
            require(rows.next(), "TARGET_METADATA_MISSING");
            return rows.getString(1);
        }
    }

    static String identity(Connection db) throws Exception {
        return hash(scalar(db, "SELECT json_build_array((SELECT system_identifier::text FROM pg_control_system()), " +
            "(SELECT oid::text FROM pg_database WHERE datname=current_database()),current_database()," +
            "inet_server_addr()::text,inet_server_port(),current_user)::text"));
    }

    static final class VerifiedDataSource extends org.postgresql.ds.PGSimpleDataSource {
        private final String expectedIdentity;
        VerifiedDataSource(String expectedIdentity) { this.expectedIdentity = expectedIdentity; }
        private Connection verify(Connection connection) throws SQLException {
            try {
                require(expectedIdentity.equals(identity(connection)), "TARGET_IDENTITY_MISMATCH");
                return connection;
            } catch (Exception error) {
                connection.close();
                throw new SQLException("TARGET_IDENTITY_MISMATCH");
            }
        }
        @Override public Connection getConnection() throws SQLException { return verify(super.getConnection()); }
        @Override public Connection getConnection(String user, String password) throws SQLException {
            return verify(super.getConnection(user, password));
        }
    }

    static Map<String, Object> state(Connection db) throws Exception {
        db.setAutoCommit(false);
        db.setTransactionIsolation(Connection.TRANSACTION_REPEATABLE_READ);
        try {
            // JDBC's startup TimeZone can override the options string with the JVM zone.
            // Normalize inside every snapshot transaction, including Windows vs Linux plans.
            try (Statement settings = db.createStatement()) {
                settings.execute("SET LOCAL TIME ZONE 'UTC'");
            }
            Map<String, Object> state = new TreeMap<>();
            state.put("targetIdentity", identity(db));
            List<Map<String, Object>> history = new ArrayList<>();
            try (Statement query = db.createStatement(); ResultSet rows = query.executeQuery(
                    "SELECT version,checksum,success,type FROM public.flyway_schema_history ORDER BY installed_rank")) {
                int expected = 1;
                while (rows.next()) {
                    require(rows.getBoolean(3) && "SQL".equals(rows.getString(4)) &&
                        Integer.toString(expected++).equals(rows.getString(1)), "SOURCE_HISTORY_INVALID");
                    history.add(Map.of("version", rows.getString(1), "checksum", rows.getInt(2)));
                }
            }
            int version = history.size();
            require(Set.of(39, 41, 43, 44, 45, 46, 47).contains(version), "SOURCE_VERSION_UNSUPPORTED");
            state.put("version", version);
            state.put("history", history);
            // Aggregate only digests/counts, never disclose account/event/token/ciphertext data.
            // All public tables are included, so role, grant, audit and delivery changes stale the plan.
            Map<String, Object> tables = new TreeMap<>();
            List<String> names = new ArrayList<>();
            try (Statement query = db.createStatement(); ResultSet rows = query.executeQuery(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")) {
                while (rows.next()) names.add(rows.getString(1));
            }
            for (String name : names) {
                String quoted = "\"" + name.replace("\"", "\"\"") + "\"";
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                long count = 0;
                try (Statement query = db.createStatement()) {
                    query.setFetchSize(256);
                    try (ResultSet rows = query.executeQuery("SELECT row_to_json(t)::text FROM public." + quoted + " t ORDER BY row_to_json(t)::text COLLATE \"C\"")) {
                        while (rows.next()) {
                            byte[] bytes = rows.getString(1).getBytes(StandardCharsets.UTF_8);
                            digest.update(Integer.toString(bytes.length).getBytes(StandardCharsets.UTF_8));
                            digest.update((byte) ':');
                            digest.update(bytes);
                            count++;
                        }
                    }
                }
                tables.put(name, Map.of("count", count, "sha256", HexFormat.of().formatHex(digest.digest())));
            }
            state.put("tables", tables);
            state.put("sequencesSha256", hash(scalar(db,
                "SELECT COALESCE(json_agg(t ORDER BY sequencename)::text,'[]') FROM " +
                "(SELECT * FROM pg_sequences WHERE schemaname='public') t")));
            return state;
        } finally { db.rollback(); db.setAutoCommit(true); }
    }

    static Map<String, Object> execute(JsonNode request) throws Exception {
        int targetVersion = request.required("targetVersion").asInt();
        require(targetVersion == 45 || targetVersion == 46 || targetVersion == 47, "TARGET_VERSION_UNSUPPORTED");
        JsonNode settings = request.required("connection");
        String url = "jdbc:postgresql://" + settings.required("host").asText() + ":" + settings.required("port").asInt() + "/" + settings.required("database").asText();
        Properties credentials = new Properties();
        credentials.setProperty("user", settings.required("user").asText());
        credentials.setProperty("password", settings.required("password").asText());
        credentials.setProperty("sslmode", settings.required("sslmode").asText());
        if (settings.has("sslrootcert")) credentials.setProperty("sslrootcert", settings.get("sslrootcert").asText());
        credentials.setProperty("connectTimeout", "10");
        credentials.setProperty("socketTimeout", "120");
        credentials.setProperty("ApplicationName", "kyrion-schema-only");
        // Every planning/validation connection is server-enforced read-only, including Flyway's.
        credentials.setProperty("options", "-c default_transaction_read_only=on -c search_path=public -c timezone=UTC");
        try (Connection guard = DriverManager.getConnection(url, credentials)) {
            require("true".equals(scalar(guard, "SELECT pg_try_advisory_lock(1264144985,45)::text")), "MIGRATION_TOOL_BUSY");
            var dataSource = new VerifiedDataSource(identity(guard));
            dataSource.setUrl(url);
            dataSource.setUser(credentials.getProperty("user")); dataSource.setPassword(credentials.getProperty("password"));
            dataSource.setSslMode(credentials.getProperty("sslmode"));
            if (credentials.containsKey("sslrootcert")) dataSource.setSslRootCert(credentials.getProperty("sslrootcert"));
            dataSource.setOptions(credentials.getProperty("options"));
            dataSource.setConnectTimeout(10); dataSource.setSocketTimeout(120); dataSource.setApplicationName("kyrion-schema-only");
            var configuration = Flyway.configure().dataSource(dataSource)
                .locations("filesystem:" + request.required("location").asText().replace('\\','/'))
                .defaultSchema("public").schemas("public").table("flyway_schema_history")
                .target(Integer.toString(targetVersion)).cleanDisabled(true).baselineOnMigrate(false).outOfOrder(false)
                // Pending migrations through the explicit target are the reviewed plan, not a validation defect.
                // Replace the default future tolerance: future history is never ignored.
                .validateMigrationNaming(true).ignoreMigrationPatterns("*:pending");
            Flyway flyway = configuration.load();
            Map<String, Object> before = state(guard);
            require((int) before.get("version") <= targetVersion, "SOURCE_NEWER_THAN_TARGET");
            flyway.validate();
            boolean apply = request.required("apply").asBoolean();
            int migrated = 0;
            if (apply) {
                require(before.get("targetIdentity").equals(request.required("expectedState").required("targetIdentity").asText()), "TARGET_IDENTITY_MISMATCH");
                require(JSON.readTree(JSON.writeValueAsBytes(before)).equals(request.required("expectedState")), "PLAN_SOURCE_DRIFT");
                require("0".equals(scalar(guard, "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'")), "TARGET_NOT_QUIESCENT");
                // Change only the dedicated Flyway datasource, never start the application.
                dataSource.setOptions("-c search_path=public -c timezone=UTC -c lock_timeout=10000 -c statement_timeout=120000");
                flyway = configuration.load();
                migrated = flyway.migrate().migrationsExecuted;
                flyway.validate();
            }
            Map<String, Object> after = state(guard);
            require(!apply || Integer.valueOf(targetVersion).equals(after.get("version")), "TARGET_VERSION_NOT_REACHED");
            require(apply || before.equals(after), "SOURCE_CHANGED_DURING_PLAN");
            return Map.of("ok", true, "applied", apply, "migrationsExecuted", migrated,
                "fromVersion", before.get("version"), "state", after);
        }
    }

    public static void main(String[] args) {
        Map<String, Object> result;
        try { result = execute(JSON.readTree(System.in)); }
        catch (Throwable error) {
            String code = error instanceof IllegalStateException && error.getMessage() != null && error.getMessage().matches("[A-Z][A-Z0-9_]+")
                ? error.getMessage() : "FLYWAY_OR_DATABASE_REJECTED";
            result = Map.of("ok", false, "code", code);
        }
        try { System.out.println("KYRION_RESULT:" + JSON.writeValueAsString(result)); }
        catch (Exception ignored) { System.exit(1); }
    }
}
