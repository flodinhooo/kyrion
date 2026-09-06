package dev.kyrion.core.activity

/** Supplies the authenticated initiator independently of resource ownership. */
fun interface ActivityActorSource {
    fun currentActorId(): String?
}
