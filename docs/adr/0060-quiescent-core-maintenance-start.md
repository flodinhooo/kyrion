# ADR 0060: Quiescent Core maintenance start

Status: Accepted

## Decision

Update health/migration checks must not enable device control, cloud work or
calendar synchronization before the update transaction authorizes activation.
Core therefore supports a host-controlled maintenance start property,
`KYRION_OPERATIONAL_MAINTENANCE=true`, default false. It is not an HTTP setting,
new account privilege or an authorization bypass.

In this mode, a highest-priority servlet filter rejects application requests with
HTTP 503 and the stable `OPERATIONAL_MAINTENANCE` code. Only exact GET/HEAD
health routes are allowed. Existing authentication/authorization remains intact
when normal mode is selected. Global `@Scheduled` registration is disabled for
maintenance starts, covering Home Assistant, calendar, knowledge and account
directory work. The existing sealed `core.started` audit event is retained;
maintenance must not suppress audit to appear read-only. Flyway and startup
security invariant checks still run. This does not
make archived SQL trustworthy or permit arbitrary schema downgrades.

Scheduling configuration belongs to Core operational configuration, rather than
the Home Assistant integration. The existing global scheduling enablement is
moved there and made conditional; ordinary startup retains the same scheduling.
The installed update transaction must separately fence service startup, keep
public frontends stopped, verify schema/health and control the activation point.
This mode alone is not an implemented update coordinator or rollback guarantee.

## Verification

Use real Spring filter/configuration tests and isolated real Core/PostgreSQL
process checks. Check both denied application requests and continued health,
and prove scheduling is absent in maintenance mode and restored in normal mode.
No household device action or productive service startup is needed.
