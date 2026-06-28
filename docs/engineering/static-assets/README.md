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

## Dependency Rules

Use Dart Sass through the maintained `sass` npm package. Do not reintroduce
`node-sass`.

Python dependencies continue to use uv through `pyproject.toml` and `uv.lock`.
Frontend build dependencies for custom Django static assets use npm through
`frontend/package.json` and `frontend/package-lock.json`.
