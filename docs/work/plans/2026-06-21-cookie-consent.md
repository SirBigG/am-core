# Plan: Cookie Consent

- Date: 2026-06-21
- Status: Draft
- Owner: Codex
- Related domain: Site trust, privacy, advertising
- Related decisions: 2026-06-21-knowledge-base-and-planning

## Goal

Add a first-party cookie consent layer that prevents optional Google Analytics and AdSense scripts from loading until the user grants the matching consent category.

## Non-Goals

- Replace Google AdSense Privacy & messaging / certified CMP account setup.
- Implement geo-targeting by jurisdiction.
- Build a full IAB TCF CMP in this repository.
- Change reCAPTCHA, social login, or third-party share link behavior.

## Current Understanding

- `templates/base.html` currently injects Google Analytics and AdSense directly when feature flags are enabled.
- The current footer now links Privacy and Cookie Policy pages.
- The site needs runtime behavior to match the new Cookie Policy.
- Google-certified CMP configuration may still be required on the AdSense side for EEA, UK, and Switzerland traffic.

## Assumptions

- A simple first-party consent banner is a useful baseline before full CMP integration.
- Analytics and advertising consent are separate categories.
- Necessary storage for the consent choice itself is acceptable.
- Existing plant diary banner localStorage is a functional preference and can remain necessary.

## Proposed Approach

- Replace direct GA and AdSense script tags with a configuration object.
- Add a cookie consent banner with accept all, reject optional, and customize actions.
- Store the user choice in localStorage with a versioned key.
- Load GA only after analytics consent.
- Load AdSense only after advertising consent.
- Add a footer control to reopen cookie settings.
- Update tests to prove direct third-party script `src` tags are absent before consent and consent UI/config is present.

## Risks And Unknowns

- This is not a Google-certified CMP or TCF implementation by itself.
- Users who reject advertising may see empty advert placements until a non-personalized or limited ads path is implemented.
- CSP is currently report-only; stricter future CSP may need nonce/hash or external static JS.

## Test Strategy

- Update feature flag tests for the new consent-gated script behavior.
- Run focused template/feature tests.
- Run `just check` and `just flake`.

## Documentation Updates

- Add a result artifact describing behavior and follow-up AdSense CMP work.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
