package dev.kyrion.core.security

import dev.kyrion.core.activity.*
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import org.springframework.mock.web.MockHttpServletRequest
import java.util.UUID

class WorkspaceAccessTest {
    @Test
    fun `workspace access requires authenticated identity and server scope`() {
        val request = MockHttpServletRequest()
        val owner = UUID.randomUUID()
        val friend = UUID.randomUUID()
        request.addHeader("workspaceOwnerId", owner.toString())
        assertThatThrownBy { request.workspaceOwnerId() }.isInstanceOf(UnauthenticatedException::class.java)
        request.setAttribute(WORKSPACE_OWNER_ID_ATTRIBUTE, owner)
        assertThatThrownBy { request.workspaceOwnerId() }.isInstanceOf(UnauthenticatedException::class.java)
        request.setAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE, friend)
        assertThat(request.workspaceOwnerId()).isEqualTo(owner)
        assertThat(request.getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE)).isEqualTo(friend)
    }

    @Test
    fun `shared user actions retain the friend as actor and installation as owner`() {
        val friend = UUID.randomUUID()
        val owner = UUID.randomUUID()
        val events = mutableListOf<ActivityEvent>()
        val repository = object : ActivityEventRepository {
            override fun append(event: ActivityEvent) = event.also(events::add)
            override fun findRecent(limit: Int) = events.take(limit)
        }
        val service = ActivityService(repository, actors = ActivityActorSource { friend.toString() })
        val event = service.record(ActivityCategory.CAPABILITY, "room.created", ActivityStatus.SUCCEEDED,
            ActivityActorType.USER, "web", "room.created", owner.toString())
        assertThat(event.actorId).isEqualTo(friend.toString())
        assertThat(event.ownerId).isEqualTo(owner)
        val integration = service.record(ActivityCategory.CAPABILITY, "completed", ActivityStatus.SUCCEEDED,
            ActivityActorType.INTEGRATION, "gateway", "completed", owner.toString())
        assertThat(integration.actorId).isEqualTo(owner.toString())
    }
}
