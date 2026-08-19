package dev.kyrion.core.home

import java.time.Instant
import java.util.UUID
import com.fasterxml.jackson.annotation.JsonValue
import org.springframework.stereotype.Service

enum class RoomType(@get:JsonValue val value: String) {
    LIVING_ROOM("living_room"), OFFICE("office"), STUDY("study"), BEDROOM("bedroom"),
    CHILDREN_ROOM("children_room"), GUEST_ROOM("guest_room"), HOBBY_ROOM("hobby_room"),
    GAMING_ROOM("gaming_room"), KITCHEN("kitchen"), DINING_ROOM("dining_room"),
    BATHROOM("bathroom"), TOILET("toilet"), HALLWAY("hallway"), ENTRANCE("entrance"),
    STORAGE("storage"), BASEMENT("basement"), LAUNDRY_ROOM("laundry_room"), GARAGE("garage"),
    WORKSHOP("workshop"), BALCONY("balcony"), TERRACE("terrace"), GARDEN("garden"), OTHER("other");
}

data class Room(val id: UUID, val name: String, val createdAt: Instant, val updatedAt: Instant, val roomType: RoomType = RoomType.OTHER)

interface RoomRepository {
    fun all(ownerId: UUID): List<Room>
    fun find(ownerId: UUID, id: UUID): Room?
    fun create(ownerId: UUID, room: Room): Room
    fun rename(ownerId: UUID, id: UUID, name: String, updatedAt: Instant): Room?
    fun changeType(ownerId: UUID, id: UUID, roomType: RoomType, updatedAt: Instant): Room? = null
    fun update(ownerId: UUID, id: UUID, name: String, roomType: RoomType, updatedAt: Instant): Room? =
        rename(ownerId, id, name, updatedAt)?.let { changeType(ownerId, id, roomType, updatedAt) }
    fun delete(ownerId: UUID, id: UUID): Boolean
    fun assignConnection(ownerId: UUID, connectionId: UUID, roomId: UUID?): Boolean
}

sealed interface RoomResolution {
    data class Resolved(val room: Room) : RoomResolution
    data object NotFound : RoomResolution
    data object Ambiguous : RoomResolution
}

@Service
class RoomResolver(private val rooms: RoomRepository) {
    fun resolve(ownerId: UUID, requested: String, language: String): RoomResolution {
        val normalized = normalize(requested)
        val ownerRooms = rooms.all(ownerId)
        ownerRooms.singleOrNull { normalize(it.name) == normalized }?.let {
            return RoomResolution.Resolved(it)
        }
        val types = synonyms[language.lowercase()]?.get(normalized).orEmpty()
        val matches = ownerRooms.filter { it.roomType in types }
        return when (matches.size) {
            0 -> RoomResolution.NotFound
            1 -> RoomResolution.Resolved(matches.single())
            else -> RoomResolution.Ambiguous
        }
    }

    private fun normalize(value: String) = value.trim().lowercase()
        .replace(Regex("[\\p{Punct}]"), " ").replace(Regex("\\s+"), " ").trim()

    companion object {
        private val synonyms = mapOf(
            "de" to mapOf(
                "büro" to setOf(RoomType.OFFICE),
                "arbeitszimmer" to setOf(RoomType.OFFICE, RoomType.STUDY),
                "wohnzimmer" to setOf(RoomType.LIVING_ROOM), "schlafzimmer" to setOf(RoomType.BEDROOM),
                "küche" to setOf(RoomType.KITCHEN), "bad" to setOf(RoomType.BATHROOM),
                "badezimmer" to setOf(RoomType.BATHROOM), "garten" to setOf(RoomType.GARDEN),
                "garage" to setOf(RoomType.GARAGE), "werkstatt" to setOf(RoomType.WORKSHOP),
                "gamingraum" to setOf(RoomType.GAMING_ROOM),
            ),
            "en" to mapOf(
                "office" to setOf(RoomType.OFFICE), "study" to setOf(RoomType.STUDY),
                "living room" to setOf(RoomType.LIVING_ROOM), "bedroom" to setOf(RoomType.BEDROOM),
                "kitchen" to setOf(RoomType.KITCHEN), "bathroom" to setOf(RoomType.BATHROOM),
                "garden" to setOf(RoomType.GARDEN), "garage" to setOf(RoomType.GARAGE),
                "workshop" to setOf(RoomType.WORKSHOP), "gaming room" to setOf(RoomType.GAMING_ROOM),
            ),
        )
    }
}
