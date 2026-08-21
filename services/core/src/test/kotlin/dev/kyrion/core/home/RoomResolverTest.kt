package dev.kyrion.core.home

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertInstanceOf
import org.junit.jupiter.api.Test
import java.time.Instant
import java.util.UUID

class RoomResolverTest {
    private val owner = UUID.randomUUID()

    @Test
    fun `exact display name wins before semantic category`() {
        val exact = room("Büro", RoomType.OTHER)
        val semantic = room("Setup", RoomType.OFFICE)
        val result = RoomResolver(RoomResolverRepository(owner, listOf(exact, semantic))).resolve(owner, "  BÜRO! ", "de")
        assertEquals(exact, (result as RoomResolution.Resolved).room)
    }

    @Test
    fun `german office synonym resolves one unique semantic room`() {
        val office = room("Setup", RoomType.OFFICE)
        val result = RoomResolver(RoomResolverRepository(owner, listOf(office))).resolve(owner, "Büro", "de")
        assertEquals(office, (result as RoomResolution.Resolved).room)
    }

    @Test
    fun `german hallway synonyms resolve one unique semantic room`() {
        val hallway = room("Gang", RoomType.HALLWAY)
        val resolver = RoomResolver(RoomResolverRepository(owner, listOf(hallway)))

        listOf("Flur", "Gang", "Diele").forEach { requested ->
            assertEquals(hallway, (resolver.resolve(owner, requested, "de") as RoomResolution.Resolved).room)
        }
    }

    @Test
    fun `english hallway synonyms resolve one unique semantic room`() {
        val hallway = room("Passage", RoomType.HALLWAY)
        val resolver = RoomResolver(RoomResolverRepository(owner, listOf(hallway)))

        listOf("hallway", "hall", "corridor").forEach { requested ->
            assertEquals(hallway, (resolver.resolve(owner, requested, "en") as RoomResolution.Resolved).room)
        }
    }

    @Test
    fun `semantic category never guesses between multiple matching rooms`() {
        val result = RoomResolver(RoomResolverRepository(owner, listOf(room("Setup", RoomType.OFFICE), room("Studio", RoomType.OFFICE))))
            .resolve(owner, "Büro", "de")
        assertInstanceOf(RoomResolution.Ambiguous::class.java, result)
    }

    @Test
    fun `unknown localized name returns not found`() {
        val result = RoomResolver(RoomResolverRepository(owner, listOf(room("Setup", RoomType.OFFICE))))
            .resolve(owner, "Wintergarten", "de")
        assertInstanceOf(RoomResolution.NotFound::class.java, result)
    }

    private fun room(name: String, type: RoomType) = Room(UUID.randomUUID(), name, Instant.EPOCH, Instant.EPOCH, type)
}

private class RoomResolverRepository(private val owner: UUID, private val values: List<Room>) : RoomRepository {
    override fun all(ownerId: UUID) = if (ownerId == owner) values else emptyList()
    override fun find(ownerId: UUID, id: UUID) = all(ownerId).singleOrNull { it.id == id }
    override fun create(ownerId: UUID, room: Room) = error("not used")
    override fun rename(ownerId: UUID, id: UUID, name: String, updatedAt: Instant) = error("not used")
    override fun delete(ownerId: UUID, id: UUID) = false
    override fun assignConnection(ownerId: UUID, connectionId: UUID, roomId: UUID?) = false
}
