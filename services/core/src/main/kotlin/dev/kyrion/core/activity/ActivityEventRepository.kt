package dev.kyrion.core.activity

interface ActivityEventRepository {
    fun append(event: ActivityEvent): ActivityEvent

    fun findRecent(limit: Int): List<ActivityEvent>
}
