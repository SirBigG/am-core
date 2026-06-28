# am-core Static Assets

This workspace owns the custom SCSS and JavaScript that used to live in `am-front`.

## Commands

From the `am-core` repo, with the local Docker stack running:

```bash
just static-install
just static-build
just collectstatic
```

For active frontend work:

```bash
just static-watch
```

The webpack output target is `core/posts/static/posts/` so existing Django templates can keep using paths such as `posts/main.css` and `posts/j-index.js`.

## Notes

- Use Dart Sass through the `sass` package. Do not add `node-sass`.
- Keep forum-specific static assets in the sibling `forum_instance` project.
- `collectstatic` remains the step that copies app static files into the shared Docker `/static` volume served by nginx.
