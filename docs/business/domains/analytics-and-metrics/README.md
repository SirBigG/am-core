# Domain: Analytics And Metrics

## Purpose

Give AgroMega operators enough private evidence to understand gateway traffic
and operational failures without turning infrastructure logs into a permanent
user-tracking datastore.

## Actors

- Authorized staff investigate traffic patterns and gateway errors.
- Superusers grant or revoke the dedicated Django permission.
- Server operators own log rotation, retention, disk health, and incident
  recovery.

## Core Workflows

- An authorized operator selects a bounded date range in Django admin.
- Django reads only approved NGINX access and error files from a read-only
  volume, builds aggregates in memory, and renders a private report.
- NGINX rotates and compresses the source files daily and removes expired
  rotations after approximately 60 days.
- An operator investigates stale rotation or high disk usage through container
  health and the documented recovery commands.

## Business Rules

- Operational analytics is distinct from consent-gated product, advertising,
  and conversion analytics.
- No raw event, parsed log row, report aggregate, or parser offset is stored in
  the application database or another analytics datastore.
- Raw log files are never downloadable through the application.
- Query strings are excluded from access-log paths and referrers.
- Raw client addresses are not displayed, and IP-derived visitor claims remain
  disabled until trusted edge forwarding is configured.
- Only active authorized staff can view reports.
- Reports are bounded by retention, date range, compressed/decompressed bytes,
  physical lines, line length, and aggregation cardinality.

## States And Lifecycle

The current files are append-only inputs owned by NGINX. Each day they become a
dated rotation, older rotations are compressed, and rotations expire after the
retention window. Django report objects exist only for the duration of a request
or short process-local cache entry.

## Neighboring Domains

- Authentication and identity owns staff sessions and permissions.
- The public Django site and community generate requests observed at the shared
  gateway but do not own the analytics files.
- Operations owns Docker volumes, NGINX configuration, rotation, and storage
  health.

## Implementation Map

- Gateway logging and rotation: parent `nginx/` deployment configuration.
- Private report parsing and presentation: `core/analytics`.
- Admin navigation and styling: Django admin templates and static assets.

## Open Questions

- Which trusted edge proxy ranges should provide the canonical client address?
- What cold-report latency and byte budget remain acceptable as traffic grows?
- Does the operational retention policy need to vary by environment?
