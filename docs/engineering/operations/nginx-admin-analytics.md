# NGINX Admin Analytics Operations

## Runtime Layout

NGINX writes the current files in the private `am-nginx-logs` Docker volume:

- `/var/log/nginx/traffic.log`;
- `/var/log/nginx/application-error.log`.

The `core` container mounts this volume read-only. It must never be mounted
below `/static`, `/media`, or another NGINX-served directory.

Daily rotation runs at 00:05 UTC in the existing NGINX container. Rotated files
use the previous day's date, for example:

```text
traffic.log-2026-08-14
traffic.log-2026-08-13.gz
application-error.log-2026-08-14
application-error.log-2026-08-13.gz
```

Sixty rotations are retained and files older than 60 days are eligible for
removal. The newest rotation is left uncompressed for one cycle to avoid
interfering with a recently reopened descriptor.

The first scheduled invocation force-rotates when no persisted rotation state
exists. This bootstraps the volume without allowing the first dated file to
combine two calendar days. Later invocations use normal daily eligibility.

## Routine Checks

Inspect the containers and NGINX health:

```bash
docker compose ps nginx
docker inspect --format '{{json .State.Health}}' am-nginx
```

Inspect private log size and rotation state without copying logs out:

```bash
docker exec am-nginx du -sh /var/log/nginx
docker exec am-nginx ls -lah /var/log/nginx
docker exec am-nginx stat /var/log/nginx/.logrotate-last-success
```

The health check fails when volume usage reaches 90%, the rotation-success
marker is missing, or its age exceeds 25 hours. Investigate before restarting;
restarts refresh the initial marker and should not be used to hide a failed
rotation job.

## Manual Rotation

Run the same idempotent command used by cron:

```bash
docker exec am-nginx /usr/local/sbin/rotate-nginx-logs
```

For a deliberate forced rotation during verification:

```bash
docker exec am-nginx logrotate --force \
  --state /var/log/nginx/.logrotate.status \
  /etc/agromega-nginx-logrotate.conf
docker exec am-nginx nginx -s reopen
```

Do not rename current logs without immediately asking NGINX to reopen them. Do
not use `copytruncate`.

## Recovery

If NGINX continues writing to a renamed file:

1. Run `docker exec am-nginx nginx -s reopen`.
2. Confirm new requests appear in the current `traffic.log`.
3. Confirm the old file stops growing.
4. Run `/usr/local/sbin/check-nginx-logs`.

If the volume approaches capacity:

1. Preserve only files required for an active incident.
2. Run the normal rotation command.
3. Remove only dated files older than the approved retention period from inside
   the NGINX container.
4. Confirm current files still exist and NGINX is healthy.
5. Investigate unexpected traffic or error growth before increasing storage.

If Django reports an unreadable directory, verify the read-only Compose mount,
file permissions, and `NGINX_ANALYTICS_LOG_DIR`. Do not solve the problem by
making the log directory publicly readable or writable by Django.

## Report Resource Limits

The parser has independent limits for selected on-disk bytes, decompressed
bytes, physical lines, bytes per line, and distinct aggregation values. The
defaults are 100 MiB selected, 100 MiB decompressed, 1,000,000 lines, 16 KiB per
line, and 5,000 distinct values per dimension. The page reports truncation,
oversized lines, malformed lines, and skipped high-cardinality values instead
of silently exceeding those bounds.

Reports are cached in each Django process for up to 180 seconds. Appends to the
current file can therefore take that long to appear. Rotated-file additions or
date/status filter changes use a different cache key. This bounded staleness is
intentional and prevents every live request from forcing a cold scan.

The release reference budget is at most 5 seconds and 128 MiB peak process RSS
for a cold scan at the 100 MiB decompressed ceiling. On 2026-08-15, the local
Linux application container scanned 599,187 lines / 100 MiB in 4.03 seconds;
whole-process peak RSS was 96,044 KiB. Re-run this profile on materially slower
production hardware and lower `NGINX_ANALYTICS_MAX_DECOMPRESSED_BYTES` if the
budget is missed. Normal seven-day reports should remain well below the ceiling.

## Privacy

The admin report shows aggregates, not raw files or raw client addresses. Error
snippets are bounded and redacted before rendering. Server operators can still
read the underlying files and must treat the volume as sensitive operational
data.

Access-log paths and referrers are written without query strings. Native error
messages can still contain request details, so the report must sanitize them and
the source files remain subject to the 60-day retention policy.
