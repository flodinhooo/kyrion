package dev.kyrion.core.config

import org.springframework.boot.SpringApplication
import org.springframework.boot.env.EnvironmentPostProcessor
import org.springframework.core.env.ConfigurableEnvironment
import org.springframework.core.env.MapPropertySource
import java.nio.file.Files
import java.nio.file.Path

/** Resolves explicitly named *_FILE settings before datasource binding. */
class SecretFileEnvironmentPostProcessor : EnvironmentPostProcessor {
    override fun postProcessEnvironment(environment: ConfigurableEnvironment, application: SpringApplication) {
        val values = mutableMapOf<String, Any>()
        System.getenv().filterKeys { it.endsWith("_FILE") }.forEach { (fileKey, fileValue) ->
            require(fileValue.isNotBlank()) { "$fileKey must not be empty" }
            val path = Path.of(fileValue)
            require(Files.isRegularFile(path)) { "$fileKey points to a missing secret file" }
            val target = fileKey.removeSuffix("_FILE")
            values[target] = Files.readString(path).trimEnd('\r', '\n')
        }
        if (values.isNotEmpty()) environment.propertySources.addFirst(MapPropertySource("kyrion-secret-files", values))
    }
}
