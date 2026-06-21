# Plan: Legal Flatpages Seed

- Date: 2026-06-21
- Status: Draft
- Owner: Codex
- Related domain: Site trust, user-generated content, advertising marketplace, companies and events
- Related decisions: 2026-06-21-knowledge-base-and-planning

## Goal

Seed baseline AgroMega informational and legal flatpages so a fresh database has the required public content without manual admin setup.

## Non-Goals

- Implement the cookie consent banner or Google CMP integration.
- Provide lawyer-approved final legal text.
- Change form consent checkboxes or moderation workflows.

## Current Understanding

- The project uses `django.contrib.flatpages`.
- Public footer links already reference `/page/about/` and `/page/privacy_policy/`.
- AgroMega includes user-generated or user-submitted content through forum, adverts, companies, events, comments, and contact forms.
- AdSense and analytics will need a separate consent implementation before non-essential tracking is loaded for EU/UK/Swiss users.

## Assumptions

- Flatpages are an acceptable temporary content store for policy text.
- Seeded text should be practical and conservative, with placeholders for the final operator/legal contact details.
- Admins may edit these pages later, so the seed should avoid overwriting existing flatpage content.

## Proposed Approach

- Add a `RunPython` data migration in `core.services` because that app already customizes flatpage admin and owns service/contact content.
- Seed About, Privacy Policy, Cookie Policy, Terms of Use, Publication and Moderation Rules, and Classified Ads Rules.
- Attach seeded pages to existing `Site` records, creating a default site only when none exists.
- Update the footer so the new legal pages are discoverable.

## Risks And Unknowns

- Legal text still needs review by the business/legal owner before being treated as final.
- Cookie and AdSense behavior must later match the Cookie Policy; text alone is not enough for compliance.
- Exact controller identity, address, and privacy email still need confirmation.

## Test Strategy

- Add a focused test that asserts the seeded flatpages exist with expected titles and site assignments.
- Run the targeted services tests if the local Docker/test database is available.

## Documentation Updates

- Add this plan.
- Add a result artifact after implementation and verification.
- Update durable domain notes if content rules become confirmed business policy.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
