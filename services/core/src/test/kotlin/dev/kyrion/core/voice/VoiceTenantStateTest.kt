package dev.kyrion.core.voice

import dev.kyrion.core.action.*
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.capability.DeviceCommandArguments
import java.util.Locale
import java.util.UUID
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test

class VoiceTenantStateTest {
    @Test
    fun `foreign session cannot consume a pending action with the same turn UUID`() {
        val owner = UUID.randomUUID()
        val satellite = UUID.randomUUID()
        val session = UUID.randomUUID()
        val turn = UUID.randomUUID()
        val context =
            ActionContext(
                owner,
                ActivityActorType.INTEGRATION,
                satellite.toString(),
                InteractionChannel.VOICE,
                Locale.ENGLISH,
                turn,
                turn,
                session,
            )
        val action =
            PendingVoiceAction(
                VoiceActionAttempt.Pending(
                    context,
                    DeviceActionProposal(
                        UUID.randomUUID(),
                        "power.set",
                        DeviceCommandArguments(on = true),
                    ),
                ),
                owner,
                UUID.randomUUID(),
                UUID.randomUUID(),
                "en",
            )
        val pending = PendingVoiceActions()
        pending.put(turn.toString(), action)
        assertThatThrownBy { pending.take(turn.toString(), UUID.randomUUID(), session, satellite) }
            .isInstanceOf(VoicePlaybackAcknowledgementInvalidException::class.java)
        assertThatThrownBy { pending.take(turn.toString(), owner, UUID.randomUUID(), satellite) }
            .isInstanceOf(VoicePlaybackAcknowledgementInvalidException::class.java)
        assertThat(pending.take(turn.toString(), owner, session, satellite)).isEqualTo(action)
    }

    @Test
    fun `playback acknowledgement keys are scoped to the session`() {
        val acknowledgements = VoicePlaybackAcknowledgements()
        acknowledgements.expect("session-a:turn")
        assertThatThrownBy { acknowledgements.acknowledge("session-b:turn") }
            .isInstanceOf(VoicePlaybackAcknowledgementInvalidException::class.java)
        acknowledgements.acknowledge("session-a:turn")
        acknowledgements.await("session-a:turn")
    }
}
