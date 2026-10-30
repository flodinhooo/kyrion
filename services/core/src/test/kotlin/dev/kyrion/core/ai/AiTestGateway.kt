package dev.kyrion.core.ai

import org.springframework.boot.test.context.TestConfiguration
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Primary
import java.util.UUID

/** Explicitly simulated provider transport. No real model/account requests. */
class AiTestGateway : AiGateway {
    val model =
        AiModel("test-local", modelId = "synthetic", capabilities = listOf("chat", "streaming"), maxOutputTokens = 16)
    var catalogValue = AiCatalog(model.id, listOf(model))
    val payloads = mutableListOf<String>()
    var behavior: ((Int, (String) -> Unit) -> Unit)? = null
    fun reset() {
        payloads.clear(); behavior = null; catalogValue = AiCatalog(model.id, listOf(model))
    }

    override fun catalog() = catalogValue
    override fun stream(payload: String, timeoutSeconds: Int, receive: (String) -> Unit) {
        payloads.add(payload)
        behavior?.let { it(payloads.size, receive); return }
        val id = UUID.randomUUID()
        receive("""{"type":"message.started","messageId":"$id"}""")
        receive("""{"type":"message.delta","messageId":"$id","delta":"Synthetic answer"}""")
        receive("""{"type":"usage","usage":{"inputTokens":12,"outputTokens":2,"totalTokens":14}}""")
        receive("""{"type":"message.completed","messageId":"$id"}""")
    }
}

@TestConfiguration(proxyBeanMethods = false)
class AiTestGatewayConfiguration {
    @Bean
    @Primary
    fun aiTestGateway() = AiTestGateway()
}
