import gzip
import hashlib
import json
import re
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings

ACCESS_BASENAME = "traffic.log"
ERROR_BASENAME = "application-error.log"
ROTATED_RE = re.compile(r"^(?P<kind>traffic|application-error)\.log-(?P<date>\d{4}-\d{2}-\d{2})(?P<gzip>\.gz)?$")
ERROR_RE = re.compile(
    r"^(?P<timestamp>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[(?P<severity>\w+)\] .*?: (?P<message>.*)$"
)
SENSITIVE_HEADER_RE = re.compile(
    r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie)(\s*[:=]\s*)(?:\"[^\"]*\"|[^,\r\n]*)"
)
SECRET_RE = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)(\s*[:=]\s*)([^\s,;]+)")
SYSTEM_PATH_RE = re.compile(r"(?<![\w])/(?:etc|var|srv|home|root|usr|opt|tmp|app|am-core|proc|sys|dev)(?:/[\w.@+-]+)+")
PATH_RE = re.compile(r"(?<![\w])/(?:[\w.@+-]+/){2,}[\w.@+-]*")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_RE = re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(?![\w:])")
WHITESPACE_RE = re.compile(r"\s+")


class AnalyticsLogError(Exception):
    pass


class InvalidDateRange(AnalyticsLogError):
    pass


class LogDirectoryUnavailable(AnalyticsLogError):
    pass


class ScanLimitExceeded(AnalyticsLogError):
    pass


@dataclass(frozen=True)
class LogFile:
    path: Path
    kind: str
    day: date
    size: int
    mtime_ns: int


_CACHE = {}
_CACHE_LOCK = threading.Lock()


def validate_date_range(start, end):
    if start > end:
        raise InvalidDateRange("The start date must not be after the end date.")
    days = (end - start).days + 1
    if days > settings.NGINX_ANALYTICS_MAX_DAYS:
        raise InvalidDateRange(f"The report range cannot exceed {settings.NGINX_ANALYTICS_MAX_DAYS} days.")


def discover_log_files(start, end, today=None):
    validate_date_range(start, end)
    root = Path(settings.NGINX_ANALYTICS_LOG_DIR)
    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LogDirectoryUnavailable("The NGINX log directory is unavailable.") from exc
    if not root.is_dir():
        raise LogDirectoryUnavailable("The NGINX log directory is unavailable.")

    today = today or date.today()
    selected = []
    try:
        entries = list(root.iterdir())
    except OSError as exc:
        raise LogDirectoryUnavailable("The NGINX log directory cannot be read.") from exc

    for path in entries:
        if path.is_symlink():
            continue
        match = ROTATED_RE.fullmatch(path.name)
        if match:
            try:
                file_day = date.fromisoformat(match.group("date"))
            except ValueError:
                continue
            kind = "access" if match.group("kind") == "traffic" else "error"
        elif path.name in (ACCESS_BASENAME, ERROR_BASENAME):
            file_day = today
            kind = "access" if path.name == ACCESS_BASENAME else "error"
        else:
            continue
        if not start <= file_day <= end:
            continue
        try:
            resolved = path.resolve(strict=True)
            stat = path.stat()
        except OSError:
            continue
        if resolved.parent != root or not path.is_file():
            continue
        selected.append(LogFile(path, kind, file_day, stat.st_size, stat.st_mtime_ns))

    selected.sort(key=lambda item: (item.day, item.path.name))
    total_bytes = sum(item.size for item in selected)
    if total_bytes > settings.NGINX_ANALYTICS_MAX_SCAN_BYTES:
        raise ScanLimitExceeded(
            f"Selected logs are {total_bytes:,} bytes; the scan limit is "
            f"{settings.NGINX_ANALYTICS_MAX_SCAN_BYTES:,} bytes. Choose a shorter range."
        )
    return selected


def _open_binary(path):
    opener = gzip.open if path.suffix == ".gz" else open
    return opener(path, mode="rb")


def _safe_text(value, limit=300):
    return WHITESPACE_RE.sub(" ", str(value or "-")).strip()[:limit]


def _without_query(value):
    value = _safe_text(value)
    try:
        parts = urlsplit(value)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")) or "-"
    except ValueError:
        return value.split("?", 1)[0]


def redact_error_message(message):
    message = SENSITIVE_HEADER_RE.sub(r"\1\2[redacted]", message)
    message = SECRET_RE.sub(r"\1\2[redacted]", message)
    message = re.sub(r"(https?://[^\s?]+)\?[^\s,]*", r"\1?[redacted]", message)
    message = re.sub(r"(request: \"\w+ [^?\s]+)\?[^\s\"]*", r"\1?[redacted]", message, flags=re.I)
    message = SYSTEM_PATH_RE.sub("[path]", message)
    message = PATH_RE.sub("[path]", message)
    message = IP_RE.sub("[ip]", message)
    message = IPV6_RE.sub("[ip]", message)
    return _safe_text(message, 500)


def _error_category(message):
    lowered = message.lower()
    if "upstream" in lowered and ("connect" in lowered or "premature" in lowered):
        return "upstream connection"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "ssl" in lowered or "tls" in lowered or "certificate" in lowered:
        return "TLS"
    if "permission denied" in lowered or "no such file" in lowered or "open()" in lowered:
        return "filesystem"
    return "other"


def _empty_report(start, end, files):
    return {
        "start": start,
        "end": end,
        "files_scanned": len(files),
        "bytes_scanned": sum(item.size for item in files),
        "decompressed_bytes": 0,
        "lines_scanned": 0,
        "oversized_lines": 0,
        "cardinality_limited": 0,
        "truncated": False,
        "truncation_reason": "",
        "access": {
            "total_requests": 0,
            "response_bytes": 0,
            "by_day": Counter(),
            "methods": Counter(),
            "status_classes": Counter(),
            "statuses": Counter(),
            "paths": Counter(),
            "referrers": Counter(),
            "user_agents": Counter(),
            "duration_bands": Counter(),
            "path_duration": {},
            "malformed": 0,
        },
        "errors": {
            "total": 0,
            "by_day": Counter(),
            "severities": Counter(),
            "categories": Counter(),
            "messages": Counter(),
            "recent": deque(maxlen=settings.NGINX_ANALYTICS_ERROR_SAMPLE_LIMIT),
            "malformed": 0,
        },
    }


def _count_bounded(counter, key, report):
    if key in counter or len(counter) < settings.NGINX_ANALYTICS_MAX_UNIQUE_VALUES:
        counter[key] += 1
    else:
        report["cardinality_limited"] += 1


def _parse_access_line(line, report, status_filter):
    access = report["access"]
    try:
        row = json.loads(line)
        status = int(row["status"])
        timestamp = datetime.fromisoformat(str(row["time"]).replace("Z", "+00:00"))
        duration = max(float(row.get("request_time", 0)), 0)
        response_bytes = max(int(row.get("bytes", 0)), 0)
    except KeyError, TypeError, ValueError, json.JSONDecodeError:
        access["malformed"] += 1
        return
    status_class = f"{status // 100}xx"
    if status_filter != "all" and status_filter not in (str(status), status_class):
        return
    path = _without_query(row.get("path", "-"))
    access["total_requests"] += 1
    access["response_bytes"] += response_bytes
    _count_bounded(access["by_day"], timestamp.date().isoformat(), report)
    _count_bounded(access["methods"], _safe_text(row.get("method"), 16), report)
    _count_bounded(access["status_classes"], status_class, report)
    _count_bounded(access["statuses"], str(status), report)
    _count_bounded(access["paths"], path, report)
    _count_bounded(access["referrers"], _without_query(row.get("referrer", "-")), report)
    _count_bounded(access["user_agents"], _safe_text(row.get("user_agent"), 200), report)
    band = "<100ms" if duration < 0.1 else "100–499ms" if duration < 0.5 else "500ms–1.99s" if duration < 2 else "≥2s"
    _count_bounded(access["duration_bands"], band, report)
    if path in access["path_duration"]:
        stats = access["path_duration"][path]
    elif len(access["path_duration"]) < settings.NGINX_ANALYTICS_MAX_UNIQUE_VALUES:
        stats = access["path_duration"].setdefault(path, [0.0, 0])
    else:
        stats = None
        report["cardinality_limited"] += 1
    if stats is not None:
        stats[0] += duration
        stats[1] += 1


def _parse_error_line(line, report):
    errors = report["errors"]
    match = ERROR_RE.match(line.rstrip("\n"))
    if not match:
        errors["malformed"] += 1
        return
    try:
        timestamp = datetime.strptime(match.group("timestamp"), "%Y/%m/%d %H:%M:%S")
    except ValueError:
        errors["malformed"] += 1
        return
    message = redact_error_message(match.group("message"))
    normalized = IP_RE.sub("[ip]", re.sub(r"\b\d+\b", "#", message))
    severity = match.group("severity").lower()
    errors["total"] += 1
    _count_bounded(errors["by_day"], timestamp.date().isoformat(), report)
    _count_bounded(errors["severities"], severity, report)
    _count_bounded(errors["categories"], _error_category(message), report)
    _count_bounded(errors["messages"], normalized, report)
    errors["recent"].append({"time": timestamp, "severity": severity, "message": message})


def _finalize(report):
    limit = settings.NGINX_ANALYTICS_TOP_LIMIT
    access = report["access"]
    errors = report["errors"]
    for key in (
        "by_day",
        "methods",
        "status_classes",
        "statuses",
        "paths",
        "referrers",
        "user_agents",
        "duration_bands",
    ):
        access[key] = access[key].most_common(limit)
    slow_paths = [
        (path, round(total / count, 3), count) for path, (total, count) in access.pop("path_duration").items()
    ]
    access["slow_paths"] = sorted(slow_paths, key=lambda item: item[1], reverse=True)[:limit]
    for key in ("by_day", "severities", "categories", "messages"):
        errors[key] = errors[key].most_common(limit)
    errors["recent"] = sorted(errors["recent"], key=lambda item: item["time"], reverse=True)[
        : settings.NGINX_ANALYTICS_ERROR_SAMPLE_LIMIT
    ]
    return report


def _build_report(files, start, end, status_filter):
    report = _empty_report(start, end, files)
    started = time.monotonic()
    for item in files:
        try:
            with _open_binary(item.path) as stream:
                while True:
                    if report["lines_scanned"] >= settings.NGINX_ANALYTICS_MAX_LINES:
                        report["truncated"] = True
                        report["truncation_reason"] = "line limit"
                        break
                    raw_line = stream.readline(settings.NGINX_ANALYTICS_MAX_LINE_BYTES + 1)
                    if not raw_line:
                        break
                    report["lines_scanned"] += 1
                    report["decompressed_bytes"] += len(raw_line)
                    if report["decompressed_bytes"] > settings.NGINX_ANALYTICS_MAX_DECOMPRESSED_BYTES:
                        report["truncated"] = True
                        report["truncation_reason"] = "decompressed byte limit"
                        break
                    if len(raw_line) > settings.NGINX_ANALYTICS_MAX_LINE_BYTES:
                        report["oversized_lines"] += 1
                        target = report["access"] if item.kind == "access" else report["errors"]
                        target["malformed"] += 1
                        while raw_line and not raw_line.endswith(b"\n"):
                            raw_line = stream.readline(settings.NGINX_ANALYTICS_MAX_LINE_BYTES + 1)
                            report["decompressed_bytes"] += len(raw_line)
                            if report["decompressed_bytes"] > settings.NGINX_ANALYTICS_MAX_DECOMPRESSED_BYTES:
                                report["truncated"] = True
                                report["truncation_reason"] = "decompressed byte limit"
                                break
                        if report["truncated"]:
                            break
                        continue
                    line = raw_line.decode("utf-8", errors="replace")
                    if item.kind == "access":
                        _parse_access_line(line, report, status_filter)
                    else:
                        _parse_error_line(line, report)
                if report["truncated"]:
                    break
        except OSError, EOFError, gzip.BadGzipFile:
            target = report["access"] if item.kind == "access" else report["errors"]
            target["malformed"] += 1
        if report["truncated"]:
            break
    report["scan_seconds"] = round(time.monotonic() - started, 3)
    return _finalize(report)


def get_report(start, end, status_filter="all"):
    if not re.fullmatch(r"all|[1-5]xx|[1-5]\d\d", status_filter):
        status_filter = "all"
    files = discover_log_files(start, end)
    # Live files change on every request. Their stable identities make the TTL
    # an actual upper bound on report staleness instead of forcing cold rescans.
    fingerprint = tuple((item.path.name, item.kind, item.day.isoformat()) for item in files)
    key = hashlib.sha256(repr((start, end, status_filter, fingerprint)).encode()).hexdigest()
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] > now:
            return cached[1]
        report = _build_report(files, start, end, status_filter)
        _CACHE.clear()
        _CACHE[key] = (now + settings.NGINX_ANALYTICS_CACHE_TTL, report)
        return report


def clear_report_cache():
    with _CACHE_LOCK:
        _CACHE.clear()
