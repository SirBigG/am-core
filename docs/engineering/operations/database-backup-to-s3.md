# PostgreSQL Backups To DigitalOcean Spaces

The repository provides `bin/backup-db-to-s3.sh` to create a compressed,
custom-format PostgreSQL dump from the Docker Compose `db` service and upload it
to DigitalOcean Spaces. The dump and its SHA-256 sidecar are private and use
SSE-C (server-side encryption with a customer-provided AES-256 key).

This covers the PostgreSQL database only. Media volumes and other state require
their own backup policy.

## Security Model

- A raw 32-byte SSE-C encryption key is mandatory. DigitalOcean uses it to
  encrypt and decrypt the object but does not retain the key.
- The encryption key and credentials file are mounted read-only into the
  short-lived uploader container; their values do not appear in command-line
  arguments or logs.
- Use a dedicated, bucket-scoped Spaces access key instead of a full-access key.
- The temporary dump directory is mode `0700`, files are mode `0600`, and the
  files are removed on exit.
- The endpoint must use HTTPS, and each object is uploaded with a private ACL.
- A SHA-256 value is stored as object metadata and uploaded as a sidecar file.

Losing the SSE-C key makes every backup encrypted with it unrecoverable. Store
the key in a secret manager or offline password vault, separately from Spaces,
and include it in a controlled disaster-recovery procedure.

## Create The Keys

In the DigitalOcean Control Panel, create a dedicated **limited-access Spaces
key** scoped to the backup Space. Record the access key and secret once, then
store them in the deployment platform's secret manager.

The script accepts an AWS-compatible credentials file:

```ini
[default]
aws_access_key_id = YOUR_SPACES_ACCESS_KEY
aws_secret_access_key = YOUR_SPACES_SECRET_KEY
```

Keep it outside the repository with mode `0600`. Alternatively, inject
`SPACES_ACCESS_KEY_ID` and `SPACES_SECRET_ACCESS_KEY` as runtime secrets; the
script converts them to a temporary credentials file and deletes it on exit.

Generate the SSE-C key once on a trusted host:

```bash
umask 077
openssl rand -out /secure/path/agromega-spaces-backup.key 32
```

Do not base64-encode this file. Back it up securely outside DigitalOcean Spaces,
and never commit it or the credentials file.

## Required Configuration

Use the regional origin endpoint, not a CDN endpoint or custom domain:

```bash
export SPACES_DESTINATION_URI=s3://agromega-backups/database
export SPACES_ENDPOINT=https://fra1.digitaloceanspaces.com
export SPACES_REGION=fra1
export SPACES_SSE_C_KEY_FILE=/run/secrets/agromega-spaces-backup.key
export SPACES_CREDENTIALS_FILE=/run/secrets/spaces-backup-credentials
```

For scheduled or repeatable runs, copy the tracked safe template and edit the
ignored local file:

```bash
cp database-backup.env.example database-backup.env
chmod 600 database-backup.env
```

The template has this structure:

```dotenv
SPACES_DESTINATION_URI=s3://agromega-backups/database
SPACES_ENDPOINT=https://fra1.digitaloceanspaces.com
SPACES_REGION=fra1
SPACES_SSE_C_KEY_FILE=/run/secrets/agromega-spaces-backup.key
SPACES_ACCESS_KEY_ID=YOUR_SPACES_ACCESS_KEY
SPACES_SECRET_ACCESS_KEY=YOUR_SPACES_SECRET_KEY
```

The script first looks for `compose.yaml`, `compose.yml`, `docker-compose.yaml`,
or `docker-compose.yml` in the directory where it is run. It then falls back to
the repository's parent directory. To select a different file explicitly, add:

```dotenv
COMPOSE_FILE=/absolute/path/to/docker-compose.yml
```

`database-backup.env` is ignored by Git, but production credentials should
preferably live outside the working tree in a deployment secret store. Restrict
the file to its owner and load it with:

```bash
BACKUP_ENV_FILE=database-backup.env just backup-db-to-s3
```

The equivalent direct form is:

```bash
./bin/backup-db-to-s3.sh --env-file /run/secrets/agromega-spaces-backup.env
```

The parser accepts blank lines, comments, optional `export`, and quoted or
unquoted literal values. It accepts only the documented backup variable names
and does not perform shell expansion or execute commands. Explicit variables in
the process environment override values from the file. Keep the binary SSE-C
key in its separate file; an env file cannot safely represent arbitrary raw
bytes.

The uploader uses the immutable `amazon/aws-cli:2.36.10` tag by default because
Spaces exposes an S3-compatible API. Change the pinned version explicitly with
`AWS_CLI_IMAGE` after validating a newer release.

## Run A Backup

Validate the destination and local secret files without connecting to Docker or
Spaces:

```bash
BACKUP_DRY_RUN=1 just backup-db-to-s3
```

Create and upload the backup:

```bash
just backup-db-to-s3
```

The object name contains a UTC timestamp, for example:

```text
s3://agromega-backups/database/am-core-2026-08-16T12-30-00Z.dump
```

The script validates that `pg_restore` can read the archive before uploading it.
It prints the final object URI and SHA-256 digest but never prints credentials or
the encryption key.

## Space Controls

Configure the backup Space as operational data storage, not as a public asset
bucket:

1. Keep file listing restricted and all backup objects private.
2. Do not enable the CDN for backups.
3. Use a dedicated limited-access key scoped only to this Space; rotate it on a
   defined schedule and immediately after suspected exposure.
4. Enable object versioning and a time-based lifecycle policy through the
   S3-compatible API when they fit the recovery and retention requirements.
5. Enable access logging to a different Space when audit requirements justify
   it.
6. Restrict who can retrieve the SSE-C key and Spaces credentials.

DigitalOcean documents an important trade-off: limited-access keys and bucket
policies cannot be used on the same Space. Prefer a limited-access key for this
script unless a reviewed bucket policy and full-access-key design provides
better controls for the deployment.

## Recovery Verification

An uploaded object is not a proven backup until it has been restored. On a
schedule appropriate to the data, download a backup with the same endpoint and
SSE-C key, verify its SHA-256 digest, restore it with `pg_restore` into an
isolated database, run application checks, and record the restore duration and
result. Never test a restore over the live database.

SSE-C requires the same key file for every `HEAD`, download, or copy operation.
A later restore script should therefore mount the key exactly as this uploader
does rather than passing the key value on the command line.
