# Static Assets

`am-core` owns the custom static assets used by Django templates.

The retired `am-front` project should not be used for new work. Its custom SCSS
and JavaScript source now lives in `frontend/src/`, and the webpack build writes
compiled assets to `core/posts/static/posts/` so existing `{% static %}` paths
continue to work.

## Workflow

Run these commands from the `am-core` folder with the parent Docker Compose
stack available:

```bash
just static-install
just static-build
just collectstatic
```

Use `just static-watch` while editing SCSS or JavaScript.

`collectstatic` remains the Django step that copies app/package static files
into the shared `/static` Docker volume served by nginx.

## Ownership

- Custom source: `frontend/src/`.
- Frontend build config and lockfile: `frontend/package.json`,
  `frontend/package-lock.json`, and `frontend/webpack.config.js`.
- Compiled Django-owned post assets: `core/posts/static/posts/`.
- PWA/root files: `pwa/`.
- Third-party package static files: installed Python packages such as
  `django-ckeditor`, `django-autocomplete-light`, `django-mptt`, `django-silk`,
  and `django-comments-dab`.
- Forum static assets: the sibling `../forum_instance` project.

## Production Cache Policy

Public static URLs are release-versioned by `VersionedS3StaticStorage`, so
objects under `static/` must be served with:

```text
Cache-Control: public, max-age=31536000, immutable
```

`settings/live.py` applies this metadata to newly uploaded static objects. A
settings change does not update metadata on objects that already exist in
Spaces. After changing the policy, rewrite the metadata for the existing
`static/` prefix or force those objects to be uploaded again, then purge the
CDN's `static/*` cache once.

The Spaces CDN treats URLs with different query strings as different cache
entries. Keep `MEDIA_VERSION` unique for every release that changes public
static files. Do not use `immutable` for user media unless the media URL also
changes whenever its content changes.

For DigitalOcean Spaces:

- Enable the CDN endpoint or its TLS-backed custom hostname.
- Keep a moderate bucket default edge TTL for mixed media, such as one day.
- Override the `static/` prefix to one year (`31536000` seconds), or rely on
  each static object's one-year cache metadata.
- Purge `static/*` after correcting old metadata; normal versioned releases do
  not require full-bucket purges.
- Verify both origin and edge responses with
  `curl -I 'https://<cdn-host>/static/posts/site.css?v=<release>'`.

DigitalOcean's current cache-management instructions are documented at
<https://docs.digitalocean.com/products/spaces/how-to/manage-cdn-cache/>.

## Nginx Delivery Baseline

When nginx serves collected files directly, the relevant locations should use
the following baseline. Media deliberately receives a shorter lifetime than
versioned static assets.

```nginx
location /static/ {
    alias /static/;
    try_files $uri =404;
    add_header Cache-Control "public, max-age=31536000, immutable" always;
    access_log off;
}

location /media/ {
    alias /var/www/media/;
    try_files $uri =404;
    add_header Cache-Control "public, max-age=86400" always;
}
```

Enable gzip for HTML, CSS, JavaScript, JSON, XML, and SVG. Do not spend CPU
recompressing JPEG, PNG, WebP, or WOFF2 files, which are already compressed.
At the public TLS terminator, enable HTTP/2 (`http2 on;` on current nginx, or
`listen 443 ssl http2;` on older supported releases). The application origin
can remain HTTP/1.1 behind that terminator.

## Dependency Rules

Use Dart Sass through the maintained `sass` npm package. Do not reintroduce
`node-sass`.

Python dependencies continue to use uv through `pyproject.toml` and `uv.lock`.
Frontend build dependencies for custom Django static assets use npm through
`frontend/package.json` and `frontend/package-lock.json`.

`frontend/src/scss/main.scss` is the shared Bootstrap foundation imported by
route entries. Import Bootstrap configuration, components, helpers, and the
utilities API there once. Do not also import aggregate entries such as
`bootstrap-grid` or repeat `mixins`, `utilities`, `helpers`, `reboot`, or
`type`; Sass evaluates those imports again and duplicates generated CSS in
every route bundle.
