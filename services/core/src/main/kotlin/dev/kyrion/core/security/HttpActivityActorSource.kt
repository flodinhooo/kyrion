package dev.kyrion.core.security

import dev.kyrion.core.activity.ActivityActorSource
import org.springframework.stereotype.Component
import org.springframework.web.context.request.RequestContextHolder
import org.springframework.web.context.request.ServletRequestAttributes
import java.util.UUID

@Component
class HttpActivityActorSource : ActivityActorSource {
    override fun currentActorId(): String? {
        val request = (RequestContextHolder.getRequestAttributes() as? ServletRequestAttributes)?.request
        return (request?.getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID)?.toString()
    }
}
