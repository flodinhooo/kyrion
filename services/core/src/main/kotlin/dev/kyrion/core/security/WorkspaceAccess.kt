package dev.kyrion.core.security

import jakarta.servlet.http.HttpServletRequest
import java.util.UUID

/** The interceptor derives both attributes from a validated session, never from client input. */
fun HttpServletRequest.workspaceOwnerId(): UUID {
    if (getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) !is UUID) throw UnauthenticatedException()
    return getAttribute(WORKSPACE_OWNER_ID_ATTRIBUTE) as? UUID ?: throw UnauthenticatedException()
}
