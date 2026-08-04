package dev.kyrion.core.home

import java.time.Instant
import java.util.UUID

data class Room(val id: UUID, val name: String, val createdAt: Instant, val updatedAt: Instant)

interface RoomRepository {
    fun all(ownerId: UUID): List<Room>
    fun find(ownerId: UUID, id: UUID): Room?
    fun create(ownerId: UUID, room: Room): Room
    fun rename(ownerId: UUID, id: UUID, name: String, updatedAt: Instant): Room?
    fun delete(ownerId: UUID, id: UUID): Boolean
    fun assignConnection(ownerId: UUID, connectionId: UUID, roomId: UUID?): Boolean
}
