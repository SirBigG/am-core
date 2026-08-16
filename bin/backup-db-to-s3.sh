#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
    cat <<'EOF'
Create a PostgreSQL dump from Docker Compose and upload it to DigitalOcean Spaces.

Required environment variables:
  SPACES_DESTINATION_URI   Destination, for example s3://my-space/database
  SPACES_ENDPOINT          Regional endpoint, for example https://fra1.digitaloceanspaces.com
  SPACES_REGION            Spaces region, for example fra1
  SPACES_SSE_C_KEY_FILE    Path to a raw 32-byte AES-256 key file

Authentication (choose one):
  SPACES_CREDENTIALS_FILE  AWS-format credentials file containing a [default] profile

  Or both:
  SPACES_ACCESS_KEY_ID
  SPACES_SECRET_ACCESS_KEY

Optional environment variables:
  COMPOSE_FILE             Explicit Docker Compose file path
  BACKUP_ENV_FILE          Load configuration from this env file
  BACKUP_DRY_RUN           Set to 1 to validate configuration only
  BACKUP_PREFIX            Filename prefix (default: am-core)
  AWS_CLI_IMAGE            Uploader image (default: amazon/aws-cli:2.36.10)

The env file uses simple KEY=VALUE lines. You can also pass it with:
  ./bin/backup-db-to-s3.sh --env-file /run/secrets/spaces-backup.env

The encryption key and credentials file are mounted read-only into the uploader
container. Never store either file in this repository.

Example:
  SPACES_DESTINATION_URI=s3://agromega-backups/database \
  SPACES_ENDPOINT=https://fra1.digitaloceanspaces.com \
  SPACES_REGION=fra1 \
  SPACES_SSE_C_KEY_FILE=/run/secrets/spaces-backup-aes.key \
  SPACES_CREDENTIALS_FILE=/run/secrets/spaces-backup-credentials \
  ./bin/backup-db-to-s3.sh
EOF
}

log() {
    printf '[database-backup] %s\n' "$*" >&2
}

die() {
    log "ERROR: $*"
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

absolute_file_path() {
    local source_path="$1"
    local source_dir
    source_dir="$(cd "$(dirname "$source_path")" && pwd)"
    printf '%s/%s\n' "$source_dir" "$(basename "$source_path")"
}

trim_whitespace() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s\n' "$value"
}

is_allowed_env_name() {
    case "$1" in
        SPACES_DESTINATION_URI | \
        SPACES_ENDPOINT | \
        SPACES_REGION | \
        SPACES_SSE_C_KEY_FILE | \
        SPACES_CREDENTIALS_FILE | \
        SPACES_ACCESS_KEY_ID | \
        SPACES_SECRET_ACCESS_KEY | \
        COMPOSE_FILE | \
        BACKUP_DRY_RUN | \
        BACKUP_PREFIX | \
        AWS_CLI_IMAGE)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

load_env_file() {
    local env_file="$1"
    local line
    local line_number=0
    local name
    local value

    [[ -f "$env_file" ]] || die "env file not found: $env_file"
    [[ -r "$env_file" ]] || die "env file is not readable: $env_file"

    while IFS= read -r line || [[ -n "$line" ]]; do
        line_number=$((line_number + 1))
        line="${line%$'\r'}"

        [[ "$line" =~ ^[[:space:]]*$ ]] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue

        if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            name="${BASH_REMATCH[2]}"
            value="$(trim_whitespace "${BASH_REMATCH[3]}")"
        else
            die "invalid env-file syntax at $env_file:$line_number"
        fi

        is_allowed_env_name "$name" || \
            die "unsupported variable '$name' at $env_file:$line_number"

        if [[ ${#value} -ge 2 ]]; then
            if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]] || \
                [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
                value="${value:1:${#value}-2}"
            fi
        fi

        if [[ -z "${!name+x}" ]]; then
            printf -v "$name" '%s' "$value"
            export "$name"
        fi
    done <"$env_file"
}

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        die "sha256sum or shasum is required"
    fi
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

env_file="${BACKUP_ENV_FILE:-}"
if [[ "${1:-}" == "--env-file" ]]; then
    [[ $# -ge 2 ]] || die "--env-file requires a path"
    env_file="$2"
    shift 2
fi

[[ $# -eq 0 ]] || die "unexpected argument: $1 (use --help)"

if [[ -n "$env_file" ]]; then
    load_env_file "$env_file"
fi

: "${SPACES_DESTINATION_URI:?SPACES_DESTINATION_URI is required}"
: "${SPACES_ENDPOINT:?SPACES_ENDPOINT is required}"
: "${SPACES_REGION:?SPACES_REGION is required}"
: "${SPACES_SSE_C_KEY_FILE:?SPACES_SSE_C_KEY_FILE is required}"

[[ "$SPACES_DESTINATION_URI" == s3://* ]] || \
    die "SPACES_DESTINATION_URI must start with s3://"
[[ "$SPACES_DESTINATION_URI" != *[[:space:]]* ]] || \
    die "SPACES_DESTINATION_URI must not contain whitespace"
[[ "$SPACES_ENDPOINT" == https://*.digitaloceanspaces.com ]] || \
    die "SPACES_ENDPOINT must be an HTTPS digitaloceanspaces.com endpoint"
[[ "$SPACES_REGION" =~ ^[a-z0-9-]+$ ]] || die "invalid SPACES_REGION"
[[ -f "$SPACES_SSE_C_KEY_FILE" ]] || \
    die "SSE-C key file not found: $SPACES_SSE_C_KEY_FILE"
[[ "$(wc -c <"$SPACES_SSE_C_KEY_FILE" | tr -d '[:space:]')" == "32" ]] || \
    die "SPACES_SSE_C_KEY_FILE must contain exactly 32 raw bytes"
SPACES_SSE_C_KEY_FILE="$(absolute_file_path "$SPACES_SSE_C_KEY_FILE")"

if [[ -n "${SPACES_CREDENTIALS_FILE:-}" ]]; then
    [[ -f "$SPACES_CREDENTIALS_FILE" ]] || \
        die "credentials file not found: $SPACES_CREDENTIALS_FILE"
    SPACES_CREDENTIALS_FILE="$(absolute_file_path "$SPACES_CREDENTIALS_FILE")"
elif [[ -z "${SPACES_ACCESS_KEY_ID:-}" || -z "${SPACES_SECRET_ACCESS_KEY:-}" ]]; then
    die "set SPACES_CREDENTIALS_FILE or both Spaces access-key variables"
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
destination="${SPACES_DESTINATION_URI%/}"
backup_prefix="${BACKUP_PREFIX:-am-core}"
aws_cli_image="${AWS_CLI_IMAGE:-amazon/aws-cli:2.36.10}"
timestamp="$(date -u +'%Y-%m-%dT%H-%M-%SZ')"
archive_name="${backup_prefix}-${timestamp}.dump"
checksum_name="${archive_name}.sha256"
archive_uri="${destination}/${archive_name}"
checksum_uri="${destination}/${checksum_name}"

[[ "$backup_prefix" =~ ^[A-Za-z0-9._-]+$ ]] || \
    die "BACKUP_PREFIX may contain only letters, numbers, dots, underscores, and hyphens"

require_command docker

if [[ -n "${COMPOSE_FILE:-}" ]]; then
    [[ -f "$COMPOSE_FILE" ]] || die "Docker Compose file not found: $COMPOSE_FILE"
    compose_file="$(absolute_file_path "$COMPOSE_FILE")"
else
    compose_file=""
    for compose_candidate in \
        "$PWD/compose.yaml" \
        "$PWD/compose.yml" \
        "$PWD/docker-compose.yaml" \
        "$PWD/docker-compose.yml" \
        "$repo_dir/../compose.yaml" \
        "$repo_dir/../compose.yml" \
        "$repo_dir/../docker-compose.yaml" \
        "$repo_dir/../docker-compose.yml"; do
        if [[ -f "$compose_candidate" ]]; then
            compose_file="$(absolute_file_path "$compose_candidate")"
            break
        fi
    done
    [[ -n "$compose_file" ]] || \
        die "no Compose file found; set COMPOSE_FILE to its path"
fi

compose_dir="$(dirname "$compose_file")"
log "using Docker Compose file: $compose_file"

compose_args=(
    compose
    --project-directory "$compose_dir"
    --file "$compose_file"
)

if [[ "${BACKUP_DRY_RUN:-0}" == "1" ]]; then
    log "configuration is valid"
    log "would upload private SSE-C archive to: $archive_uri"
    log "would upload private SSE-C checksum to: $checksum_uri"
    exit 0
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/am-core-db-backup.XXXXXX")"
data_dir="$tmp_dir/data"
mkdir -m 700 "$data_dir"
chmod 700 "$tmp_dir"
archive_path="$data_dir/$archive_name"
checksum_path="$data_dir/$checksum_name"
generated_credentials_path=""

cleanup() {
    local exit_status=$?
    rm -f "$archive_path" "$checksum_path"
    if [[ -n "$generated_credentials_path" ]]; then
        rm -f "$generated_credentials_path"
    fi
    rmdir "$data_dir" "$tmp_dir" 2>/dev/null || true
    return "$exit_status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ -n "${SPACES_CREDENTIALS_FILE:-}" ]]; then
    credentials_path="$SPACES_CREDENTIALS_FILE"
else
    generated_credentials_path="$tmp_dir/credentials"
    umask 077
    printf '[default]\naws_access_key_id = %s\naws_secret_access_key = %s\n' \
        "$SPACES_ACCESS_KEY_ID" "$SPACES_SECRET_ACCESS_KEY" \
        >"$generated_credentials_path"
    credentials_path="$generated_credentials_path"
fi

log "creating compressed PostgreSQL archive from Compose service 'db'"
docker "${compose_args[@]}" exec -T db sh -eu -c '
    : "${POSTGRES_USER:?POSTGRES_USER is not set in the db container}"
    database=${POSTGRES_DB:-$POSTGRES_USER}
    export PGPASSWORD=${POSTGRES_PASSWORD:-}
    exec pg_dump \
        --username="$POSTGRES_USER" \
        --dbname="$database" \
        --format=custom \
        --compress=9 \
        --no-owner \
        --no-acl
' >"$archive_path"

[[ -s "$archive_path" ]] || die "pg_dump produced an empty archive"

log "validating archive structure with pg_restore"
docker "${compose_args[@]}" exec -T db \
    pg_restore --list <"$archive_path" >/dev/null

checksum="$(sha256_file "$archive_path")"
printf '%s  %s\n' "$checksum" "$archive_name" >"$checksum_path"
chmod 600 "$archive_path" "$checksum_path"

upload_object() {
    local source_name="$1"
    local target_uri="$2"
    shift 2

    docker run --rm \
        --volume "$data_dir:/backup:ro" \
        --volume "$credentials_path:/root/.aws/credentials:ro" \
        --volume "$SPACES_SSE_C_KEY_FILE:/run/secrets/spaces-sse-c.key:ro" \
        "$aws_cli_image" \
        s3 cp "/backup/$source_name" "$target_uri" \
        --endpoint-url "$SPACES_ENDPOINT" \
        --region "$SPACES_REGION" \
        --acl private \
        --sse-c AES256 \
        --sse-c-key fileb:///run/secrets/spaces-sse-c.key \
        --only-show-errors \
        "$@"
}

log "uploading private archive with SSE-C encryption"
upload_object "$archive_name" "$archive_uri" \
    --metadata "sha256=$checksum,format=postgresql-custom"

log "uploading private checksum sidecar with SSE-C encryption"
upload_object "$checksum_name" "$checksum_uri"

log "backup completed: $archive_uri"
log "SHA-256: $checksum"
