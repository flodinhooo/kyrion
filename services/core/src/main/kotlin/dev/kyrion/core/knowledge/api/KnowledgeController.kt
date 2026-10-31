package dev.kyrion.core.knowledge.api

import dev.kyrion.core.knowledge.application.KnowledgeService
import dev.kyrion.core.knowledge.domain.KnowledgeFailure
import dev.kyrion.core.security.authenticatedUserId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.core.io.FileSystemResource
import org.springframework.http.*
import org.springframework.web.bind.annotation.*
import org.springframework.web.multipart.MultipartFile
import org.springframework.web.multipart.MaxUploadSizeExceededException
import java.nio.charset.StandardCharsets
import java.util.UUID

data class KnowledgeSearchRequest(val spaceIds: List<UUID>, val query: String, val limit: Int = 3)

@RestController
@RequestMapping("/v1/knowledge")
class KnowledgeController(
    private val service: KnowledgeService,
    private val answers: dev.kyrion.core.knowledge.persistence.KnowledgeAnswerSources,
    private val rbac: dev.kyrion.core.security.RbacService
) {
    @GetMapping("/answers/{id}")
    fun sources(
        @PathVariable id: UUID,
        request: HttpServletRequest
    ): List<dev.kyrion.core.knowledge.persistence.AnswerSource> {
        val actor = request.authenticatedUserId()
        rbac.require(actor, "knowledge:read")
        return answers.list(actor, id)
    }
    @GetMapping("/spaces")
    fun spaces(request: HttpServletRequest) = service.spaces(request.authenticatedUserId())
    @PostMapping("/spaces")
    fun create(request: HttpServletRequest) = service.createSpace(request.authenticatedUserId())
    @GetMapping("/spaces/{id}/documents")
    fun documents(
        @PathVariable id: UUID,
        @RequestParam(defaultValue = "50") limit: Int, @RequestParam(defaultValue = "0") offset: Int,
        request: HttpServletRequest
    ) = service.documents(request.authenticatedUserId(), id, limit, offset)

    @PostMapping("/spaces/{id}/documents", consumes = [MediaType.MULTIPART_FORM_DATA_VALUE])
    fun upload(@PathVariable id: UUID, @RequestPart("file") file: MultipartFile, request: HttpServletRequest) =
        file.inputStream.use {
            service.upload(
                request.authenticatedUserId(),
                id,
                file.originalFilename ?: "",
                file.contentType ?: "",
                it
            )
        }

    @GetMapping("/documents/{id}")
    fun document(@PathVariable id: UUID, request: HttpServletRequest) =
        service.document(request.authenticatedUserId(), id)

    @GetMapping("/documents/{id}/content")
    fun content(@PathVariable id: UUID, request: HttpServletRequest): ResponseEntity<FileSystemResource> {
        val (document, path) = service.content(request.authenticatedUserId(), id)
        return ResponseEntity.ok().contentType(MediaType.parseMediaType(document.mediaType))
            .header(
                HttpHeaders.CONTENT_DISPOSITION,
                ContentDisposition.attachment().filename(document.originalFilename, StandardCharsets.UTF_8).build()
                    .toString()
            )
            .header(HttpHeaders.CACHE_CONTROL, "no-store").header("X-Content-Type-Options", "nosniff")
            .body(FileSystemResource(path))
    }

    @DeleteMapping("/documents/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun delete(@PathVariable id: UUID, request: HttpServletRequest) = service.delete(request.authenticatedUserId(), id)
    @PostMapping("/documents/{id}/reindex")
    fun reindex(@PathVariable id: UUID, request: HttpServletRequest) =
        service.reindex(request.authenticatedUserId(), id)
    @PostMapping("/search")
    fun search(@RequestBody raw: String, request: HttpServletRequest): List<dev.kyrion.core.knowledge.domain.KnowledgeSource> {
        if (raw.length > 16000) throw KnowledgeFailure("INVALID_REQUEST")
        val body = try { dev.kyrion.core.ai.strictAiJson.readValue(raw, KnowledgeSearchRequest::class.java) }
            catch (_: Exception) { throw KnowledgeFailure("INVALID_REQUEST") }
        return service.search(request.authenticatedUserId(), body.spaceIds, body.query, body.limit)
    }
}

@RestControllerAdvice
class KnowledgeErrorHandler {
    @ExceptionHandler(KnowledgeFailure::class)
    fun failure(failure: KnowledgeFailure) = ResponseEntity.status(failure.status).body(mapOf("code" to failure.code))

    @ExceptionHandler(MaxUploadSizeExceededException::class)
    fun oversized() = ResponseEntity.status(413).body(mapOf("code" to "KNOWLEDGE_TOO_LARGE"))
}
