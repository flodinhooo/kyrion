package dev.kyrion.core.home

import org.springframework.dao.DuplicateKeyException
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import java.sql.Timestamp
import java.util.UUID

@Repository
class JdbcRoomRepository(private val jdbc: JdbcClient) : RoomRepository {
    override fun all(ownerId: UUID): List<Room> = jdbc.sql("SELECT * FROM owner_room WHERE owner_id = :ownerId ORDER BY lower(name)")
        .param("ownerId", ownerId).query { rs, _ -> mapRoom(rs) }.list()
    override fun find(ownerId: UUID, id: UUID): Room? = jdbc.sql("SELECT * FROM owner_room WHERE owner_id = :ownerId AND id = :id")
        .param("ownerId", ownerId).param("id", id).query { rs, _ -> mapRoom(rs) }.optional().orElse(null)
    override fun create(ownerId: UUID, room: Room): Room = try {
        jdbc.sql("INSERT INTO owner_room (id, owner_id, name, room_type, created_at, updated_at) VALUES (:id, :ownerId, :name, :roomType, :createdAt, :updatedAt)")
            .param("id", room.id).param("ownerId", ownerId).param("name", room.name).param("roomType", room.roomType.value).param("createdAt", Timestamp.from(room.createdAt)).param("updatedAt", Timestamp.from(room.updatedAt)).update()
        room
    } catch (_: DuplicateKeyException) { throw RoomConflictException() }
    override fun changeType(ownerId: UUID, id: UUID, roomType: RoomType, updatedAt: java.time.Instant): Room? {
        val count = jdbc.sql("UPDATE owner_room SET room_type = :roomType, updated_at = :updatedAt WHERE owner_id = :ownerId AND id = :id")
            .param("roomType", roomType.value).param("updatedAt", Timestamp.from(updatedAt)).param("ownerId", ownerId).param("id", id).update()
        return if (count == 1) find(ownerId, id) else null
    }
    override fun update(ownerId: UUID, id: UUID, name: String, roomType: RoomType, updatedAt: java.time.Instant): Room? = try {
        val count = jdbc.sql("UPDATE owner_room SET name = :name, room_type = :roomType, updated_at = :updatedAt WHERE owner_id = :ownerId AND id = :id")
            .param("name", name).param("roomType", roomType.value).param("updatedAt", Timestamp.from(updatedAt))
            .param("ownerId", ownerId).param("id", id).update()
        if (count == 1) find(ownerId, id) else null
    } catch (_: DuplicateKeyException) { throw RoomConflictException() }
    override fun rename(ownerId: UUID, id: UUID, name: String, updatedAt: java.time.Instant): Room? = try {
        val count = jdbc.sql("UPDATE owner_room SET name = :name, updated_at = :updatedAt WHERE owner_id = :ownerId AND id = :id")
            .param("name", name).param("updatedAt", Timestamp.from(updatedAt)).param("ownerId", ownerId).param("id", id).update()
        if (count == 1) find(ownerId, id) else null
    } catch (_: DuplicateKeyException) { throw RoomConflictException() }
    override fun delete(ownerId: UUID, id: UUID) = jdbc.sql("DELETE FROM owner_room WHERE owner_id = :ownerId AND id = :id").param("ownerId", ownerId).param("id", id).update() == 1
    override fun assignConnection(ownerId: UUID, connectionId: UUID, roomId: UUID?): Boolean = jdbc.sql(
        """UPDATE integration_connection SET room_id = :roomId, updated_at = CURRENT_TIMESTAMP
           WHERE owner_id = :ownerId AND id = :connectionId
             AND (:roomId IS NULL OR EXISTS (SELECT 1 FROM owner_room WHERE id = :roomId AND owner_id = :ownerId))""",
    ).param("roomId", roomId).param("ownerId", ownerId).param("connectionId", connectionId).update() == 1

    private fun mapRoom(rs: java.sql.ResultSet) = Room(rs.getObject("id", UUID::class.java), rs.getString("name"), rs.getTimestamp("created_at").toInstant(), rs.getTimestamp("updated_at").toInstant(), RoomType.entries.single { it.value == rs.getString("room_type") })
}
