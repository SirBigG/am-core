# Decision: Database-Free NGINX Analytics In Django Admin

- Date: 2026-08-15
- Status: Accepted
- Owners: AgroMega engineering

## Context

AgroMega needs private operational visibility into requests handled by the shared
NGINX gateway and into gateway errors affecting the Django site or community.
The gateway already produces the source data. Running a separate third-party
dashboard would add another application, dependency tree, authorization
boundary, and operational failure mode.

Request and error logs may contain personal or sensitive operational data.
Query strings are particularly risky because they can contain search terms,
email addresses, tokens, or other identifiers. Reading an unlimited history in
a Django request could also monopolize an application worker.

## Decision

- NGINX remains the sole owner and writer of two current files in a private
  named volume:
  - `/var/log/nginx/traffic.log`;
  - `/var/log/nginx/application-error.log`.
- Access entries use JSON Lines with JSON escaping. Request paths and referrers
  are stripped at the first `?` before being written. Cookies, authorization
  headers, request bodies, and query strings are not logged.
- Error logging uses the native open-source NGINX text format at `warn` level.
- The existing NGINX container runs a daily UTC logrotate job at 00:05. It
  retains 60 daily rotations, removes files older than 60 days, compresses old
  files, and signals NGINX to reopen logs without `copytruncate`.
- Rotation state and the last-success marker live in the same private volume.
  The NGINX health check fails when the marker is older than 25 hours or the
  volume reaches 90% usage.
- Django mounts the log volume read-only. It has no route that returns a log
  file and the volume is outside static and media roots.
- Django discovers only strict current/dated access and error filenames,
  rejects symlinks and non-regular files, streams plain or gzip files line by
  line, applies independent selected-byte, decompressed-byte, line-length,
  line-count, and aggregation-cardinality limits, sanitizes displayed content,
  and returns aggregate report structures held only in memory.
- Report results use a short process-local cache and a process-local lock. Its
  live-file identity is stable for the cache TTL, so appends may be visible up
  to 180 seconds later without causing a cold rescan on every request. No raw
  entry, offset, aggregate, cache result, or report is persisted in PostgreSQL
  or another analytics datastore.
- A normal Django content type and permission may exist solely to authorize the
  admin page. This is authentication metadata, not analytics storage.
- The report does not expose raw client addresses and does not present client
  addresses as unique visitors until trusted production proxy ranges are
  configured.
- The report is available only below the configured Django admin path to active
  staff with the dedicated permission; superusers retain normal permission
  behavior.

## Consequences

The deployment has no permanent analytics service and no analytics datastore.
The report is easy to revoke through Django permissions and its source files
remain private at the server boundary.

Cold report requests consume a Django worker while selected files are parsed.
The implementation therefore favors bounded operational summaries over large
or interactive reports. Process-local caching can duplicate work across Django
workers, which is accepted to preserve the no-shared-state requirement.

The initial release ceiling is 100 MiB decompressed per cold report with a
reference budget of 5 seconds and 128 MiB peak process RSS. The 2026-08-15 local
container profile completed at 4.03 seconds and 96,044 KiB for 599,187 lines.
These figures are a deployment guardrail, not a guarantee across hardware.

Daily rotation is part of the NGINX container rather than a separate service.
Operators must treat a stale rotation marker, an unhealthy NGINX container, or
high log-volume usage as an operational incident.

## Alternatives Considered

- A separate Next.js NGINX analytics dashboard was rejected because it added a
  service, third-party security surface, base-path patch, and duplicate UI.
- Parsing all history on every page load was rejected because it is unbounded.
- Persisting daily aggregates in PostgreSQL was rejected by the explicit
  no-analytics-datastore requirement.
- `copytruncate` was rejected because concurrent writes can be lost or
  duplicated. NGINX log reopen is the supported rotation mechanism.
- Giving Django write access to the log volume was rejected to preserve log
  ownership and reduce the impact of an application compromise.

## Release Requirements

- Validate query strings are absent from stored access paths and referrers.
- Validate rotation, compression, NGINX reopen, 60-day removal, and health
  marker behavior in the built container.
- Validate no public NGINX or Django URL can retrieve the source files.
- Validate admin authorization, scan limits, redaction, gzip parsing, malformed
  line handling, and absence of analytics database writes.
- Configure trusted edge proxy ranges before enabling any IP-derived statistic;
  otherwise keep those statistics disabled.
- Measure representative cold and warm report latency and keep scan limits
  below the documented worker-time and memory budgets.
