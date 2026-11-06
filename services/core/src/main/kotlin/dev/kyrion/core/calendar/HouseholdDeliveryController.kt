package dev.kyrion.core.calendar

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.security.authenticatedUserId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import java.util.UUID

@RestController
@RequestMapping("/v1/calendar")
class HouseholdDeliveryController(private val service: HouseholdCalendarDelivery) {
    @ModelAttribute fun noStore(response: jakarta.servlet.http.HttpServletResponse) { response.setHeader("Cache-Control", "no-store") }
    @GetMapping("/household-destination") fun setting(request: HttpServletRequest) = service.setting(request.authenticatedUserId())
    @PutMapping("/household-destination")
    fun change(request: HttpServletRequest, @RequestBody raw: String): HouseholdDestinationSetting {
        val root = parse(raw, setOf("calendarId", "revision"))
        if (!root.path("calendarId").isNull && !root.path("calendarId").isTextual) invalid()
        return service.change(request.authenticatedUserId(), HouseholdDestinationChange(
            if (root.path("calendarId").isNull) null else root.path("calendarId").asText(), revision(root)))
    }
    @GetMapping("/household-events/{id}/deliveries")
    fun view(request: HttpServletRequest, @PathVariable id: UUID) = service.view(request.authenticatedUserId(), id)
    @PostMapping("/household-events/{id}/deliveries")
    fun deliver(request: HttpServletRequest, @PathVariable id: UUID, @RequestBody raw: String): HouseholdDeliveryView {
        val root = parse(raw, setOf("targetId", "revision"))
        if (!root.path("targetId").isTextual) invalid()
        val target = runCatching { UUID.fromString(root.path("targetId").asText()) }.getOrElse { invalid() }
        return service.deliver(request.authenticatedUserId(), id, HouseholdDeliveryRequest(target, revision(root)))
    }
    private fun parse(raw: String, fields: Set<String>): JsonNode = try {
        if (raw.length > 4000) invalid()
        val mapper = jacksonObjectMapper().enable(com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
        val root = mapper.readTree(raw)
        if (!root.isObject || root.fieldNames().asSequence().toSet() != fields) invalid()
        root
    } catch (_: Exception) { invalid() }
    private fun revision(root: JsonNode): Long {
        if (!root.path("revision").isIntegralNumber || !root.path("revision").canConvertToLong() || root.path("revision").asLong() < 0) invalid()
        return root.path("revision").asLong()
    }
    private fun invalid(): Nothing = throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_INVALID", HttpStatus.BAD_REQUEST)
}

@RestControllerAdvice
class HouseholdDeliveryErrors {
    @ExceptionHandler(HouseholdDeliveryFailure::class)
    fun failure(error: HouseholdDeliveryFailure) = ResponseEntity.status(error.status).body(mapOf("code" to error.code))
}
@RestControllerAdvice(assignableTypes = [HouseholdDeliveryController::class])
class HouseholdDeliveryInputErrors {
    @ExceptionHandler(org.springframework.web.bind.MissingServletRequestParameterException::class,
        org.springframework.web.method.annotation.MethodArgumentTypeMismatchException::class,
        org.springframework.http.converter.HttpMessageNotReadableException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST) fun invalid() = mapOf("code" to "CALENDAR_DELIVERY_INVALID")
}
