package dev.kyrion.core.knowledge.persistence

import dev.kyrion.core.knowledge.domain.KnowledgeSource
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import java.util.UUID

data class AnswerSource(val messageId: UUID, val source: KnowledgeSource)

@Repository
class KnowledgeAnswerSources(private val jdbc: JdbcClient) {
    fun save(actor: UUID, conversation: UUID, message: UUID, sources: List<KnowledgeSource>) {
        sources.forEach { source ->
            jdbc.sql("INSERT INTO knowledge_answer_sources(conversation_id,user_id,message_id,document_id,reference,source_page,start_offset,end_offset) SELECT c.id,:actor,:message,d.id,:reference,:page,:start,:end FROM conversation c,knowledge_documents d JOIN knowledge_spaces s ON s.id=d.space_id WHERE c.id=:conversation AND c.owner_id=:actor AND d.id=:document AND d.deleted_at IS NULL AND s.owner_user_id=:actor ON CONFLICT DO NOTHING")
                .param("actor", actor).param("message", message).param("reference", source.reference)
                .param("page", source.page, java.sql.Types.INTEGER).param("start", source.startOffset)
                .param("end", source.endOffset)
                .param("conversation", conversation).param("document", source.documentId).update()
        }
    }

    fun list(actor: UUID, conversation: UUID): List<AnswerSource> =
        jdbc.sql("SELECT a.*,d.original_filename FROM knowledge_answer_sources a JOIN knowledge_documents d ON d.id=a.document_id JOIN knowledge_spaces s ON s.id=d.space_id JOIN conversation c ON c.id=a.conversation_id WHERE a.user_id=:actor AND s.owner_user_id=:actor AND c.owner_id=:actor AND a.conversation_id=:conversation AND d.deleted_at IS NULL ORDER BY a.message_id,a.reference")
            .param("actor", actor).param("conversation", conversation).query { r, _ ->
                AnswerSource(
                    r.getObject("message_id", UUID::class.java), KnowledgeSource(
                        r.getObject("document_id", UUID::class.java),
                        r.getString("original_filename"),
                        "",
                        r.getInt("source_page").let { if (r.wasNull()) null else it },
                        r.getInt("start_offset"),
                        r.getInt("end_offset"),
                        r.getString("reference")
                    )
                )
            }.list()
}
