# Security Docs

Use this folder for security investigations, threat-model notes, security decisions, audit results, and rollout plans for security-sensitive changes.

Create dated notes for work that affects authentication, authorization, CSP, data protection, dependency vulnerabilities, file handling, external integrations, or operational recovery.

Example:

```text
YYYY-MM-DD-csp-enforcement-plan.md
```

## Public Static Origins And PWA Manifests

Production sets Content Security Policy in report-only mode. When static files
are hosted on a different origin, include that exact HTTPS origin in
`CSP_STATIC_ORIGINS`. The setting is shared by `script-src`, `style-src`,
`font-src`, and `manifest-src`; without the last directive, browsers fall back
to `default-src 'self'` and reject a CDN-hosted `site.webmanifest`.

Before enforcing CSP, verify a representative anonymous page, authenticated
page, article page, form, and PWA installation flow without report-only
violations.
