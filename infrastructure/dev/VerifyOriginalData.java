import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.kyrion.core.activity.ActivityIntegrity;
import dev.kyrion.core.activity.ActivityIntegrityVerifier;
import dev.kyrion.core.integration.CredentialCipher;
import dev.kyrion.core.integration.DeviceClass;
import dev.kyrion.core.integration.IntegrationConnection;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.jdbc.core.simple.JdbcClient;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Read-only original-key/data recovery check. No Spring context or provider clients. */
public final class VerifyOriginalData {
    public static void main(String[] args) {
        Map<String, Object> result = new LinkedHashMap<>();
        boolean valid = false;
        String stage = "CONFIGURATION";
        try {
            JsonNode settings = new ObjectMapper().readTree(Files.readAllBytes(Path.of(args[0])));
            if (!"127.0.0.1".equals(settings.required("host").asText())) {
                throw new IllegalArgumentException();
            }
            PGSimpleDataSource source = new PGSimpleDataSource();
            source.setServerNames(new String[]{"127.0.0.1"});
            source.setPortNumbers(new int[]{settings.required("port").asInt()});
            source.setDatabaseName(settings.required("database").asText());
            source.setUser(settings.required("user").asText());
            source.setPassword(settings.required("password").asText());
            source.setOptions("-c default_transaction_read_only=on -c timezone=UTC");
            source.setConnectTimeout(10);
            source.setSocketTimeout(60);

            stage = "ORIGINAL_KEYS";
            var verifier = new ActivityIntegrityVerifier(JdbcClient.create(source),
                    new ActivityIntegrity(settings.required("auditKey").asText(), false));
            var cipher = new CredentialCipher(settings.required("credentialKey").asText(), false);
            int chains = 0, sealed = 0, legacy = 0, credentials = 0, uncredentialed = 0, documents = 0;
            valid = true;
            stage = "DATABASE_CONNECTION";
            try (var db = source.getConnection(); var statement = db.createStatement()) {
                stage = "AUDIT_VERIFICATION";
                try (var rows = statement.executeQuery("SELECT chain_scope FROM activity_integrity_chain UNION " +
                        "SELECT chain_scope FROM activity_event WHERE integrity_version=1")) {
                    while (rows.next()) {
                        var report = verifier.verify(rows.getString(1));
                        valid &= report.getValid();
                        chains++;
                        sealed += report.getSealedEvents();
                        legacy += report.getLegacyEvents();
                    }
                }
                stage = "CREDENTIAL_VERIFICATION";
                try (var rows = statement.executeQuery("SELECT id,owner_id,provider,credential_ciphertext," +
                        "credential_nonce,credential_version FROM integration_connection")) {
                    while (rows.next()) {
                        byte[] ciphertext = rows.getBytes(4), nonce = rows.getBytes(5);
                        // These adapters deliberately persist device references without secrets.
                        if (ciphertext.length == 0 && nonce.length == 0 && rows.getInt(6) == 1 &&
                                Set.of("bluetooth", "zigbee", "home_assistant", "shelly").contains(rows.getString(3))) {
                            uncredentialed++;
                            continue;
                        }
                        var connection = new IntegrationConnection(rows.getObject(1, UUID.class),
                                rows.getObject(2, UUID.class), rows.getString(3), "", "", rows.getBytes(4),
                                rows.getBytes(5), rows.getInt(6), Instant.EPOCH, Instant.EPOCH, null, DeviceClass.OTHER);
                        cipher.reveal(connection); // Verify AEAD with the actual domain implementation; never print it.
                        credentials++;
                    }
                }
                stage = "ORIGINAL_DOCUMENTS";
                Path root = Path.of(settings.required("knowledgeRoot").asText()).toAbsolutePath().normalize();
                if (Files.isSymbolicLink(root)) throw new IllegalStateException();
                try (var rows = statement.executeQuery("SELECT storage_key,byte_size,content_sha256 " +
                        "FROM knowledge_documents WHERE deleted_at IS NULL")) {
                    while (rows.next()) {
                        Path original = root.resolve(rows.getObject(1, UUID.class).toString()).normalize();
                        if (!original.startsWith(root) || Files.isSymbolicLink(original) || !Files.isRegularFile(original) ||
                                Files.size(original) != rows.getLong(2)) throw new IllegalStateException();
                        MessageDigest hash = MessageDigest.getInstance("SHA-256");
                        try (var stream = Files.newInputStream(original)) {
                            byte[] buffer = new byte[65536];
                            for (int length; (length = stream.read(buffer)) != -1;) hash.update(buffer, 0, length);
                        }
                        if (!HexFormat.of().formatHex(hash.digest()).equals(rows.getString(3))) {
                            throw new IllegalStateException();
                        }
                        documents++;
                    }
                }
            }
            result.put("auditChains", chains);
            result.put("sealedEvents", sealed);
            result.put("legacyEvents", legacy);
            result.put("decryptedCredentialRecords", credentials);
            result.put("uncredentialedDeviceReferences", uncredentialed);
            result.put("verifiedOriginalDocuments", documents);
            if (!valid) result.put("code", "AUDIT_CHAIN_INVALID");
        } catch (Throwable error) {
            // Never print exceptions, SQL, account IDs, credentials or document names.
            valid = false;
            result.put("code", stage + "_FAILED");
            result.put("failureType", error.getClass().getSimpleName());
            if (error instanceof java.sql.SQLException sql) result.put("sqlState", sql.getSQLState());
        }
        result.put("valid", valid);
        try { System.out.println(new ObjectMapper().writeValueAsString(result)); }
        catch (Exception ignored) { System.exit(1); }
        if (!valid) System.exit(1);
    }
}
