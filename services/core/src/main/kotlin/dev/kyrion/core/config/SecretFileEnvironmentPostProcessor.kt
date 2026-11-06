package dev.kyrion.core.config

import org.springframework.boot.SpringApplication
import org.springframework.boot.env.EnvironmentPostProcessor
import org.springframework.core.env.ConfigurableEnvironment
import org.springframework.core.env.MapPropertySource
import java.nio.file.Files
import java.nio.file.Path

/** Resolves text database secrets; key and bootstrap file settings remain paths. */
class SecretFileEnvironmentPostProcessor : EnvironmentPostProcessor {
    override fun postProcessEnvironment(environment: ConfigurableEnvironment, application: SpringApplication) {
        val values = resolveSecretFiles(System.getenv())
        if (values.isNotEmpty()) environment.propertySources.addFirst(MapPropertySource("kyrion-secret-files", values))
    }
}

internal fun resolveSecretFiles(variables: Map<String, String>): Map<String, Any> {
    val values = mutableMapOf<String, Any>()
    variables.filterKeys { it == "KYRION_DATABASE_PASSWORD_FILE" }.forEach { (fileKey, fileValue) ->
        require(fileValue.isNotBlank()) { "$fileKey must not be empty" }
        val path = Path.of(fileValue)
        require(Files.isRegularFile(path)) { "$fileKey points to a missing secret file" }
        val target = fileKey.removeSuffix("_FILE")
        values[target] = Files.readString(path).trimEnd('\r', '\n')
    }
    return values
}
