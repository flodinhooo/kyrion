"""Presentation hints for stable Core/installer error codes; no authority here."""

KEYS = {
    "CENTRAL_UNAVAILABLE": "identityErrorUnavailable",
    "CENTRAL_DISABLED": "identityErrorConfiguration",
    "E_IDENTITY_NOT_CONFIGURED": "identityErrorConfiguration",
    "CENTRAL_OPERATION_INVALID": "identityErrorRestart",
    "CENTRAL_OPERATION_PENDING": "identityErrorRestart",
    "E_IDENTITY_EXPIRED": "identityErrorRestart",
    "CENTRAL_DENIED": "identityErrorRestart",
    "BOOTSTRAP_FORBIDDEN": "identityErrorBootstrap",
    "E_BOOTSTRAP_EXPIRED": "identityErrorBootstrap",
    "E_BOOTSTRAP_EXPECTED_OWNER": "identityErrorExistingOwner",
    "E_BOOTSTRAP_ALREADY_INITIALIZED": "identityErrorExistingOwner",
    "SETUP_ALREADY_COMPLETED": "identityErrorExistingOwner",
    "SPACE_ACCESS_REQUIRED": "identityErrorMembership",
    "INVITATION_INVALID": "identityErrorInvitation",
    "CENTRAL_IDENTITY_ALREADY_LINKED": "identityErrorLinked",
    "E_IDENTITY_ALREADY_LINKED": "identityErrorLinked",
    "E_IDENTITY_LINK_REQUIRED": "identityErrorMembership",
    "UNAUTHENTICATED": "identityErrorLocalAccess",
    "INVALID_CURRENT_PASSWORD": "identityErrorLocalAccess",
    "LOGIN_RATE_LIMITED": "identityErrorRateLimit",
    "FORBIDDEN": "identityErrorPermission",
    "E_PASSWORD_MISMATCH": "identityErrorPasswordMismatch",
    "E_IDENTITY_CANCELLED": "identitySetupPaused",
    "E_SPACE_CANCELLED": "identitySetupPaused",
}


def guidance(code: str, messages: dict[str, str]) -> str | None:
    return messages.get(KEYS.get(code, ""))
