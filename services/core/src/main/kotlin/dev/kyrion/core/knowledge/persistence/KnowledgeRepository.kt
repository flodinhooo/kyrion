package dev.kyrion.core.knowledge.persistence

import dev.kyrion.core.knowledge.domain.*
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.transaction.support.TransactionTemplate
import java.sql.ResultSet
import java.util.UUID

@Repository
class KnowledgeRepository(private val jdbc: JdbcClient, private val tx: TransactionTemplate) {
    fun spaces(actor: UUID): List<KnowledgeSpace> =
        jdbc.sql("SELECT id,name FROM knowledge_spaces WHERE owner_user_id=:actor AND owner_type='PERSONAL'")
            .param("actor", actor).query { r, _ ->
                KnowledgeSpace(
                    r.getObject("id", UUID::class.java),
                    KnowledgeOwnerType.PERSONAL,
                    r.getString("name")
                )
            }.list()

    fun createSpace(actor: UUID): KnowledgeSpace {
        jdbc.sql("INSERT INTO knowledge_spaces(id,owner_user_id,name) VALUES(:id,:actor,'Personal') ON CONFLICT(owner_user_id) DO NOTHING")
            .param("id", UUID.randomUUID()).param("actor", actor).update()
        return spaces(actor).single()
    }

    fun requireSpace(actor: UUID, space: UUID) {
        if (!jdbc.sql("SELECT EXISTS(SELECT 1 FROM knowledge_spaces WHERE id=:space AND owner_user_id=:actor AND owner_type='PERSONAL')")
                .param("space", space).param("actor", actor).query(Boolean::class.java).single()
        ) missing()
    }

    fun list(actor: UUID, space: UUID, limit: Int, offset: Int): List<KnowledgeDocument> {
        requireSpace(actor, space)
        return jdbc.sql("SELECT d.* FROM knowledge_documents d JOIN knowledge_spaces s ON s.id=d.space_id WHERE s.owner_user_id=:actor AND s.owner_type='PERSONAL' AND s.id=:space AND d.deleted_at IS NULL ORDER BY d.created_at DESC,d.id LIMIT :limit OFFSET :offset")
            .param("actor", actor).param("space", space).param("limit", limit).param("offset", offset)
            .query { r, _ -> document(r) }.list()
    }

    fun find(actor: UUID, id: UUID): KnowledgeDocument =
        jdbc.sql("SELECT d.* FROM knowledge_documents d JOIN knowledge_spaces s ON s.id=d.space_id WHERE d.id=:id AND s.owner_user_id=:actor AND s.owner_type='PERSONAL' AND d.deleted_at IS NULL")
            .param("actor", actor).param("id", id).query { r, _ -> document(r) }.optional().orElse(null) ?: missing()

    fun key(actor: UUID, id: UUID): UUID =
        jdbc.sql("SELECT d.storage_key FROM knowledge_documents d JOIN knowledge_spaces s ON s.id=d.space_id WHERE d.id=:id AND s.owner_user_id=:actor AND s.owner_type='PERSONAL' AND d.deleted_at IS NULL")
            .param("actor", actor).param("id", id).query(UUID::class.java).optional().orElse(null) ?: missing()

    fun insert(actor: UUID, space: UUID, id: UUID, filename: String, type: String, key: UUID, size: Long, sha: String) {
        tx.executeWithoutResult {
            requireSpace(actor, space)
            // Bound personal storage and exact-search workload; serialize uploads per space.
            jdbc.sql("SELECT id FROM knowledge_spaces WHERE id=:space FOR UPDATE").param("space", space)
                .query(UUID::class.java).single()
            if (jdbc.sql("SELECT count(*) FROM knowledge_documents WHERE space_id=:space AND deleted_at IS NULL")
                    .param("space", space).query(Long::class.java).single() >= 100
            ) throw KnowledgeFailure("KNOWLEDGE_QUOTA", 409)
            jdbc.sql("INSERT INTO knowledge_documents(id,space_id,uploaded_by_user_id,original_filename,media_type,storage_key,byte_size,content_sha256,status) VALUES(:id,:space,:actor,:name,:type,:key,:size,:sha,'PENDING')")
                .param("id", id).param("space", space).param("actor", actor).param("name", filename).param("type", type)
                .param("key", key).param("size", size).param("sha", sha).update()
            jdbc.sql("INSERT INTO knowledge_ingestion_jobs(id,document_id,requested_revision,status) VALUES(:job,:id,1,'PENDING')")
                .param("job", UUID.randomUUID()).param("id", id).update()
        }
    }

    fun tombstone(actor: UUID, id: UUID) {
        if (jdbc.sql("UPDATE knowledge_documents d SET status='DELETING',deleted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=:id AND deleted_at IS NULL AND EXISTS(SELECT 1 FROM knowledge_spaces s WHERE s.id=d.space_id AND s.owner_user_id=:actor AND s.owner_type='PERSONAL')")
                .param("id", id).param("actor", actor).update() != 1
        ) missing()
    }

    fun claim(): KnowledgeJob? = tx.execute {
        // Exhausted leases become explicit failures even after the last worker crashes.
        jdbc.sql("UPDATE knowledge_documents d SET status='FAILED',error_code='KNOWLEDGE_RETRY_EXHAUSTED',updated_at=CURRENT_TIMESTAMP FROM knowledge_ingestion_jobs j WHERE j.document_id=d.id AND d.deleted_at IS NULL AND j.status='PROCESSING' AND j.attempt_count>=3 AND j.lease_expires_at<CURRENT_TIMESTAMP")
            .update()
        jdbc.sql("UPDATE knowledge_ingestion_jobs SET status='FAILED',error_code='KNOWLEDGE_RETRY_EXHAUSTED' WHERE status='PROCESSING' AND attempt_count>=3 AND lease_expires_at<CURRENT_TIMESTAMP")
            .update()
        val lease = UUID.randomUUID()
        val job = jdbc.sql(
            """
            WITH candidate AS (
              SELECT j.id FROM knowledge_ingestion_jobs j JOIN knowledge_documents d ON d.id=j.document_id
              JOIN knowledge_spaces s ON s.id=d.space_id JOIN user_account u ON u.id=s.owner_user_id
              WHERE d.deleted_at IS NULL AND s.owner_type='PERSONAL' AND u.enabled AND j.attempt_count<3
              AND ((j.status='PENDING' AND j.next_attempt_at<=CURRENT_TIMESTAMP) OR
                   (j.status='PROCESSING' AND j.lease_expires_at<CURRENT_TIMESTAMP))
              ORDER BY j.created_at FOR UPDATE OF j SKIP LOCKED LIMIT 1
            ) UPDATE knowledge_ingestion_jobs j SET status='PROCESSING',attempt_count=attempt_count+1,
              lease_owner=:lease,lease_expires_at=CURRENT_TIMESTAMP+INTERVAL '10 minutes',updated_at=CURRENT_TIMESTAMP
              FROM candidate c WHERE j.id=c.id RETURNING j.*
        """
        ).param("lease", lease).query { r, _ ->
            Triple(
                r.getObject("id", UUID::class.java),
                r.getObject("document_id", UUID::class.java),
                r.getInt("requested_revision")
            )
        }.optional().orElse(null)
            ?: return@execute null
        jdbc.sql("UPDATE knowledge_documents SET status='PROCESSING',updated_at=CURRENT_TIMESTAMP WHERE id=:id AND deleted_at IS NULL")
            .param("id", job.second).update()
        jdbc.sql("SELECT d.storage_key,d.media_type,s.owner_user_id FROM knowledge_documents d JOIN knowledge_spaces s ON s.id=d.space_id WHERE d.id=:id AND d.deleted_at IS NULL")
            .param("id", job.second).query { r, _ ->
                KnowledgeJob(
                    job.first, job.second, job.third, lease,
                    r.getObject(1, UUID::class.java), r.getString(2), r.getObject(3, UUID::class.java)
                )
            }.optional().orElse(null)
    }

    fun alive(job: KnowledgeJob): Boolean =
        jdbc.sql("SELECT EXISTS(SELECT 1 FROM knowledge_documents d JOIN knowledge_ingestion_jobs j ON j.document_id=d.id JOIN knowledge_spaces s ON s.id=d.space_id JOIN user_account u ON u.id=s.owner_user_id WHERE d.id=:doc AND d.deleted_at IS NULL AND u.enabled AND d.ingestion_revision=:rev AND j.id=:job AND j.lease_owner=:lease AND j.status='PROCESSING' AND j.lease_expires_at>CURRENT_TIMESTAMP)")
            .param("doc", job.documentId).param("rev", job.revision).param("job", job.id).param("lease", job.lease)
            .query(Boolean::class.java).single()

    fun renew(job: KnowledgeJob): Boolean {
        if (!alive(job)) return false
        return jdbc.sql("UPDATE knowledge_ingestion_jobs SET lease_expires_at=CURRENT_TIMESTAMP+INTERVAL '10 minutes' WHERE id=:id AND lease_owner=:lease AND status='PROCESSING' AND lease_expires_at>CURRENT_TIMESTAMP")
            .param("id", job.id).param("lease", job.lease).update() == 1
    }

    fun publish(
        job: KnowledgeJob,
        chunks: List<KnowledgeChunk>,
        vectors: List<List<Float>>,
        model: String,
        dimension: Int
    ): Boolean = tx.execute {
        jdbc.sql("SELECT id FROM knowledge_documents WHERE id=:id FOR UPDATE").param("id", job.documentId)
            .query(UUID::class.java).optional()
        if (!alive(job)) return@execute false
        require(chunks.isNotEmpty() && chunks.size == vectors.size && vectors.all { it.size == dimension && it.all(Float::isFinite) && it.any { n -> n != 0f } })
        jdbc.sql("DELETE FROM knowledge_chunks WHERE document_id=:id").param("id", job.documentId).update()
        chunks.zip(vectors).forEach { (chunk, vector) ->
            jdbc.sql("INSERT INTO knowledge_chunks(id,document_id,ingestion_revision,chunk_index,content,token_count,source_page,source_start_offset,source_end_offset,embedding_model_id,embedding_dimension,embedding) VALUES(:id,:doc,:rev,:idx,:content,:tokens,:page,:start,:end,:model,:dim,CAST(:vector AS real[]))")
                .param("id", UUID.randomUUID()).param("doc", job.documentId).param("rev", job.revision)
                .param("idx", chunk.index)
                .param("content", chunk.content).param("tokens", (chunk.content.length + 3) / 4)
                .param("page", chunk.page, java.sql.Types.INTEGER).param("start", chunk.start).param("end", chunk.end)
                .param("model", model).param("dim", dimension).param("vector", vector.joinToString(",", "{", "}"))
                .update()
        }
        jdbc.sql("UPDATE knowledge_documents SET status='READY',error_code=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=:id")
            .param("id", job.documentId).update()
        jdbc.sql("UPDATE knowledge_ingestion_jobs SET status='DONE',lease_owner=NULL,lease_expires_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=:id AND lease_owner=:lease")
            .param("id", job.id).param("lease", job.lease).update()
        true
    } ?: false

    fun fail(job: KnowledgeJob, code: String) {
        tx.executeWithoutResult {
            jdbc.sql("SELECT id FROM knowledge_documents WHERE id=:id FOR UPDATE").param("id", job.documentId)
                .query(UUID::class.java).optional()
            if (!alive(job)) return@executeWithoutResult
            val retry = code in setOf("KNOWLEDGE_EMBEDDING_BUSY", "KNOWLEDGE_EMBEDDING_UNAVAILABLE")
            val state =
                jdbc.sql("UPDATE knowledge_ingestion_jobs SET status=CASE WHEN :retry AND attempt_count<3 THEN 'PENDING' ELSE 'FAILED' END,error_code=:code,next_attempt_at=CURRENT_TIMESTAMP+INTERVAL '30 seconds',lease_owner=NULL,lease_expires_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=:id AND lease_owner=:lease RETURNING status")
                    .param("retry", retry).param("code", code).param("id", job.id).param("lease", job.lease)
                    .query(String::class.java).single()
            jdbc.sql("UPDATE knowledge_documents SET status=:status,error_code=:code,updated_at=CURRENT_TIMESTAMP WHERE id=:id AND deleted_at IS NULL")
                .param("status", if (state == "PENDING") "PENDING" else "FAILED").param("code", code)
                .param("id", job.documentId).update()
        }
    }

    fun deleting(): List<Pair<UUID, UUID>> =
        jdbc.sql("SELECT id,storage_key FROM knowledge_documents WHERE deleted_at IS NOT NULL LIMIT 100")
            .query { r, _ -> r.getObject(1, UUID::class.java) to r.getObject(2, UUID::class.java) }.list()

    fun remove(id: UUID) {
        jdbc.sql("DELETE FROM knowledge_documents WHERE id=:id AND deleted_at IS NOT NULL").param("id", id).update()
    }

    fun keys(): Set<UUID> =
        jdbc.sql("SELECT storage_key FROM knowledge_documents").query(UUID::class.java).list().toSet()

    /** Authorization and active model/revision are enforced before ranking, inside SQL. */
    fun search(
        actor: UUID,
        spaces: List<UUID>,
        vector: List<Float>,
        model: String,
        dimension: Int,
        limit: Int
    ): List<KnowledgeSource> {
        if (spaces.isEmpty()) return emptyList()
        return jdbc.sql(
            """
            WITH authorized AS MATERIALIZED (
              SELECT c.*,d.original_filename FROM knowledge_chunks c
              JOIN knowledge_documents d ON d.id=c.document_id JOIN knowledge_spaces s ON s.id=d.space_id
              WHERE s.owner_user_id=:actor AND s.owner_type='PERSONAL' AND s.id IN (:spaces)
              AND d.deleted_at IS NULL AND d.status='READY' AND c.ingestion_revision=d.ingestion_revision
              AND c.embedding_model_id=:model AND c.embedding_dimension=:dim
            ) SELECT a.*,score.similarity FROM authorized a CROSS JOIN LATERAL (
              SELECT sum(v.x::double precision*q.x)/NULLIF(sqrt(sum(v.x::double precision*v.x))*sqrt(sum(q.x::double precision*q.x)),0) AS similarity
              FROM unnest(a.embedding) WITH ORDINALITY v(x,i)
              JOIN unnest(CAST(:vector AS real[])) WITH ORDINALITY q(x,i) USING(i)
            ) score WHERE score.similarity>0 ORDER BY score.similarity DESC,document_id,chunk_index LIMIT :limit
        """
        ).param("actor", actor).param("spaces", spaces).param("model", model).param("dim", dimension)
            .param("vector", vector.joinToString(",", "{", "}")).param("limit", limit).query { r, _ ->
                val id = r.getObject("document_id", UUID::class.java)
                KnowledgeSource(
                    id,
                    r.getString("original_filename"),
                    r.getString("content"),
                    r.getInt("source_page").let { if (r.wasNull()) null else it },
                    r.getInt("source_start_offset"),
                    r.getInt("source_end_offset"),
                    "kd:$id:${r.getInt("ingestion_revision")}:${r.getInt("chunk_index")}"
                )
            }.list()
    }

    private fun document(r: ResultSet) = KnowledgeDocument(
        r.getObject("id", UUID::class.java),
        r.getObject("space_id", UUID::class.java),
        r.getString("original_filename"),
        r.getString("media_type"),
        r.getLong("byte_size"),
        r.getString("status"),
        r.getString("error_code"),
        r.getInt("ingestion_revision"),
        r.getTimestamp("created_at").toInstant()
    )

    private fun missing(): Nothing = throw KnowledgeFailure("KNOWLEDGE_NOT_FOUND", 404)
}
