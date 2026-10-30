package dev.kyrion.core.calendar

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class CalendarScheduleTest {
    @Test fun `revoked permissions suspend an opted in schedule without retry storms`() {
        val repository=org.mockito.Mockito.mock(CalendarScheduleRepository::class.java)
        val runner=org.mockito.Mockito.mock(CalendarSyncRunner::class.java)
        val actor=java.util.UUID.randomUUID()
        org.mockito.Mockito.`when`(repository.due()).thenReturn(listOf(actor))
        org.mockito.Mockito.doThrow(dev.kyrion.core.security.ForbiddenException()).`when`(runner).run(actor,true)
        CalendarSyncScheduler(repository,runner).tick()
        org.mockito.Mockito.verify(repository).suspend(actor)
    }

    @Test fun `retry interval increases is bounded and honors provider retry after`() {
        assertEquals(60, calendarRetrySeconds(1))
        assertEquals(120, calendarRetrySeconds(2))
        assertEquals(3600, calendarRetrySeconds(100))
        assertEquals(600, calendarRetrySeconds(1,600))
        assertEquals(86400, calendarRetrySeconds(1,Long.MAX_VALUE))
    }
}
