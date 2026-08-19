package dev.kyrion.core.action

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.capability.DeviceAvailability
import dev.kyrion.core.capability.DeviceCapabilityView
import dev.kyrion.core.capability.DeviceCatalogItem
import dev.kyrion.core.capability.DeviceCatalogService
import dev.kyrion.core.capability.DeviceCommandArguments
import dev.kyrion.core.capability.DeviceCommandOutcome
import dev.kyrion.core.capability.DeviceCommandResult
import dev.kyrion.core.capability.DeviceCommandService
import dev.kyrion.core.capability.DeviceTargetNotFoundException
import dev.kyrion.core.capability.DeviceTargetSelector
import dev.kyrion.core.capability.ExecuteDeviceCommandRequest
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test
import org.mockito.Mockito.mock
import org.mockito.Mockito.verify
import org.mockito.Mockito.verifyNoInteractions
import org.mockito.Mockito.`when`
import java.util.Locale
import java.util.UUID

class DeviceActionHandlerTest {
    @Test
    fun `handler reloads owner catalog and passes action correlation to command service`() {
        val catalog = mock(DeviceCatalogService::class.java)
        val commands = mock(DeviceCommandService::class.java)
        val handler = DeviceActionHandler(catalog, commands)
        val context = context()
        val targetId = UUID.randomUUID()
        val proposal = DeviceActionProposal(
            targetId,
            DeviceCommandService.POWER_SET,
            DeviceCommandArguments(on = true),
        )
        val request = ExecuteDeviceCommandRequest(
            DeviceCommandService.POWER_SET,
            DeviceTargetSelector(provider = "nanoleaf", deviceId = targetId),
            proposal.arguments,
        )
        `when`(catalog.devices(context.ownerId)).thenReturn(
            listOf(
                DeviceCatalogItem(
                    targetId,
                    "nanoleaf",
                    "Desk light",
                    "Nanoleaf",
                    null,
                    listOf(DeviceCapabilityView(DeviceCommandService.POWER_SET)),
                    DeviceAvailability.ONLINE,
                    null,
                    null,
                ),
            ),
        )
        `when`(commands.execute(context.ownerId, request, context.correlationId, false)).thenReturn(
            DeviceCommandResult(
                DeviceCommandService.POWER_SET,
                "Office",
                1,
                1,
                0,
                listOf(DeviceCommandOutcome(targetId, "Desk light", "succeeded")),
                context.correlationId,
            ),
        )

        val outcome = handler.execute(context, proposal)

        assertEquals(ActionOutcomeStatus.SUCCEEDED, outcome.status)
        assertEquals("action.succeeded", outcome.code)
        assertEquals(context.correlationId, outcome.correlationId)
        verify(commands).execute(context.ownerId, request, context.correlationId, false)
    }

    @Test
    fun `handler cannot target a device absent from the owner catalog`() {
        val catalog = mock(DeviceCatalogService::class.java)
        val commands = mock(DeviceCommandService::class.java)
        val context = context()
        `when`(catalog.devices(context.ownerId)).thenReturn(emptyList())

        assertThrows(DeviceTargetNotFoundException::class.java) {
            DeviceActionHandler(catalog, commands).execute(
                context,
                DeviceActionProposal(
                    UUID.randomUUID(),
                    DeviceCommandService.POWER_SET,
                    DeviceCommandArguments(on = true),
                ),
            )
        }
        verifyNoInteractions(commands)
    }

    private fun context() = ActionContext(
        ownerId = UUID.randomUUID(),
        actorType = ActivityActorType.AI,
        actorId = "velora",
        channel = InteractionChannel.VOICE,
        locale = Locale.GERMAN,
        correlationId = UUID.randomUUID(),
        idempotencyKey = UUID.randomUUID(),
        sessionId = UUID.randomUUID(),
    )
}
