package dev.kyrion.core.integration

import dev.kyrion.core.activity.*
import org.springframework.stereotype.Service
import java.net.Inet4Address
import java.net.InetAddress
import java.time.Clock
import java.util.UUID

@Service
class NanoleafIntegrationService(
    private val repository: IntegrationConnectionRepository,
    private val gateway: NanoleafGateway,
    private val cipher: CredentialCipher,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun connections(ownerId: UUID) = repository.findAll(ownerId).filter { it.provider == PROVIDER }.map(IntegrationConnection::view)

    fun pair(ownerId: UUID, host: String, displayName: String?): IntegrationConnectionView {
        val validatedHost = validatePrivateIpv4(host)
        val id = UUID.randomUUID()
        val correlationId = UUID.randomUUID()
        record(ownerId, "integration.nanoleaf.pairing", ActivityStatus.PROPOSED, "nanoleaf.pairing.proposed", correlationId)
        return try {
            val token = gateway.pair(validatedHost)
            val now = clock.instant()
            val context = "$ownerId:$id:$PROVIDER"
            val protected = cipher.protect(token, context)
            val connection = repository.save(
                IntegrationConnection(id, ownerId, PROVIDER, displayName?.trim()?.takeIf { it.isNotBlank() } ?: "Nanoleaf",
                    validatedHost, protected.ciphertext, protected.nonce, protected.version, now, now),
            )
            record(ownerId, "integration.nanoleaf.paired", ActivityStatus.SUCCEEDED, "nanoleaf.paired", correlationId)
            connection.view()
        } catch (exception: RuntimeException) {
            record(ownerId, "integration.nanoleaf.pairing", ActivityStatus.FAILED, "nanoleaf.pairing.failed", correlationId)
            throw exception
        }
    }

    fun state(ownerId: UUID, id: UUID): NanoleafDeviceState {
        val connection = owned(ownerId, id)
        return gateway.state(connection.endpointHost, cipher.reveal(connection))
    }

    fun rename(ownerId: UUID, id: UUID, displayName: String): IntegrationConnectionView {
        val name = displayName.trim()
        if (name.isBlank() || name.length > 160) throw IntegrationInvalidNameException()
        val connection = repository.rename(ownerId, id, name, clock.instant()) ?: throw IntegrationNotFoundException()
        record(ownerId, "integration.nanoleaf.renamed", ActivityStatus.SUCCEEDED, "nanoleaf.renamed", id)
        return connection.view()
    }

    fun power(ownerId: UUID, id: UUID, on: Boolean, confirmed: Boolean, correlationId: UUID = UUID.randomUUID()): NanoleafDeviceState {
        if (!confirmed) throw IntegrationConfirmationRequiredException()
        val connection = owned(ownerId, id)
        record(ownerId, "integration.nanoleaf.power", ActivityStatus.CONFIRMED, "nanoleaf.power.confirmed", correlationId)
        return try {
            val token = cipher.reveal(connection)
            gateway.setPower(connection.endpointHost, token, on)
            val state = gateway.state(connection.endpointHost, token)
            record(ownerId, "integration.nanoleaf.power", ActivityStatus.SUCCEEDED, if (on) "nanoleaf.power.on" else "nanoleaf.power.off", correlationId)
            state
        } catch (exception: RuntimeException) {
            record(ownerId, "integration.nanoleaf.power", ActivityStatus.FAILED, "nanoleaf.power.failed", correlationId)
            throw exception
        }
    }

    fun remove(ownerId: UUID, id: UUID) {
        if (!repository.delete(ownerId, id)) throw IntegrationNotFoundException()
        record(ownerId, "integration.nanoleaf.removed", ActivityStatus.SUCCEEDED, "nanoleaf.removed", id)
    }

    fun brightness(ownerId: UUID, id: UUID, brightness: Int, confirmed: Boolean, correlationId: UUID = UUID.randomUUID()): NanoleafDeviceState {
        if (!confirmed) throw IntegrationConfirmationRequiredException()
        if (brightness !in 0..100) throw IntegrationInvalidBrightnessException()
        val connection = owned(ownerId, id)
        record(ownerId, "integration.nanoleaf.brightness", ActivityStatus.CONFIRMED, "nanoleaf.brightness.confirmed", correlationId)
        return try {
            val token = cipher.reveal(connection)
            gateway.setBrightness(connection.endpointHost, token, brightness)
            gateway.state(connection.endpointHost, token).also {
                record(ownerId, "integration.nanoleaf.brightness", ActivityStatus.SUCCEEDED, "nanoleaf.brightness.changed", correlationId)
            }
        } catch (exception: RuntimeException) {
            record(ownerId, "integration.nanoleaf.brightness", ActivityStatus.FAILED, "nanoleaf.brightness.failed", correlationId)
            throw exception
        }
    }

    fun scenes(ownerId: UUID, id: UUID): NanoleafScenes {
        val connection = owned(ownerId, id)
        return gateway.scenes(connection.endpointHost, cipher.reveal(connection))
    }

    fun selectScene(ownerId: UUID, id: UUID, name: String, confirmed: Boolean): NanoleafScenes {
        if (!confirmed) throw IntegrationConfirmationRequiredException()
        val scene = name.trim()
        if (scene.isBlank() || scene.length > 160) throw IntegrationInvalidSceneException()
        val connection = owned(ownerId, id)
        val correlationId = UUID.randomUUID()
        record(ownerId, "integration.nanoleaf.scene", ActivityStatus.CONFIRMED, "nanoleaf.scene.confirmed", correlationId)
        return try {
            val token = cipher.reveal(connection)
            gateway.selectScene(connection.endpointHost, token, scene)
            gateway.scenes(connection.endpointHost, token).also {
                record(ownerId, "integration.nanoleaf.scene", ActivityStatus.SUCCEEDED, "nanoleaf.scene.selected", correlationId)
            }
        } catch (exception: RuntimeException) {
            record(ownerId, "integration.nanoleaf.scene", ActivityStatus.FAILED, "nanoleaf.scene.failed", correlationId)
            throw exception
        }
    }

    fun color(ownerId: UUID, id: UUID, hue: Int, saturation: Int, confirmed: Boolean): NanoleafDeviceState {
        if (!confirmed) throw IntegrationConfirmationRequiredException()
        if (hue !in 0..359 || saturation !in 0..100) throw IntegrationInvalidColorException()
        return executeStateCommand(ownerId, id, "color", "nanoleaf.color.changed") { host, token -> gateway.setColor(host, token, hue, saturation) }
    }

    fun colorTemperature(ownerId: UUID, id: UUID, kelvin: Int, confirmed: Boolean): NanoleafDeviceState {
        if (!confirmed) throw IntegrationConfirmationRequiredException()
        if (kelvin !in 1200..6500) throw IntegrationInvalidColorException()
        return executeStateCommand(ownerId, id, "color-temperature", "nanoleaf.color-temperature.changed") { host, token -> gateway.setColorTemperature(host, token, kelvin) }
    }

    private fun executeStateCommand(ownerId: UUID, id: UUID, type: String, summary: String, command: (String, String) -> Unit): NanoleafDeviceState {
        val connection = owned(ownerId, id); val correlationId = UUID.randomUUID()
        record(ownerId, "integration.nanoleaf.$type", ActivityStatus.CONFIRMED, "nanoleaf.$type.confirmed", correlationId)
        return try { val token = cipher.reveal(connection); command(connection.endpointHost, token); gateway.state(connection.endpointHost, token).also { record(ownerId, "integration.nanoleaf.$type", ActivityStatus.SUCCEEDED, summary, correlationId) } }
        catch (exception: RuntimeException) { record(ownerId, "integration.nanoleaf.$type", ActivityStatus.FAILED, "nanoleaf.$type.failed", correlationId); throw exception }
    }

    private fun owned(ownerId: UUID, id: UUID) = repository.find(ownerId, id)?.takeIf { it.provider == PROVIDER }
        ?: throw IntegrationNotFoundException()

    private fun validatePrivateIpv4(value: String): String {
        if (!value.matches(Regex("^(?:\\d{1,3}\\.){3}\\d{1,3}$"))) throw IntegrationInvalidHostException()
        val address = try { InetAddress.getByName(value) } catch (_: Exception) { throw IntegrationInvalidHostException() }
        if (address !is Inet4Address || !(address.isSiteLocalAddress || address.isLinkLocalAddress)) throw IntegrationInvalidHostException()
        return address.hostAddress
    }

    private fun record(ownerId: UUID, type: String, status: ActivityStatus, summary: String, correlationId: UUID) = activity.record(
        ActivityCategory.INTEGRATION, type, status, ActivityActorType.USER, "kyrion-core", summary,
        actorId = ownerId.toString(), correlationId = correlationId,
    )

    companion object { const val PROVIDER = "nanoleaf" }
}

class IntegrationNotFoundException : RuntimeException()
class IntegrationInvalidHostException : RuntimeException()
class IntegrationConfirmationRequiredException : RuntimeException()
class IntegrationInvalidNameException : RuntimeException()
class IntegrationInvalidBrightnessException : RuntimeException()
class IntegrationInvalidSceneException : RuntimeException()
class IntegrationInvalidColorException : RuntimeException()
