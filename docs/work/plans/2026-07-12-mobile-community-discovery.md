# Plan: Mobile Community Discovery

- Date: 2026-07-12
- Status: Approved
- Owner: AgroMega product and engineering
- Related domain: `docs/business/domains/community-content/README.md`
- Related decisions: `docs/engineering/decisions/2026-07-11-community-spirit-composition-and-publication-security.md`

## Goal

Make the AgroMega community reachable in one tap from the persistent mobile navigation on every main-site landing page, including pages entered directly from search engines.

## Non-Goals

- Redesigning the community application or its own navigation.
- Changing community routing, authentication, or publication behavior.
- Adding another bottom-navigation slot or changing desktop navigation.

## Current Understanding

Desktop navigation links directly to “Спільнота”. On mobile, the same destination is buried inside the long “Розділи” drop-up, so a visitor arriving on an article or catalog page is unlikely to discover it.

## Assumptions

- Community discovery is a higher-priority persistent destination than a dedicated news shortcut.
- News remains discoverable through site content, search, and section navigation.
- Five bottom-navigation destinations remain the practical mobile limit.

## Proposed Approach

Replace the direct mobile “Новини” item with a direct “Спільнота” item using the existing community SSO URL. Keep the existing community entry in “Розділи” as a secondary path.

## Risks And Unknowns

- Returning news readers lose the dedicated bottom shortcut, although no news route is removed.
- The community link must remain readable at narrow mobile widths and preserve the existing minimum touch target.

## Test Strategy

- Lint the changed template.
- Verify the five-item mobile navigation at a narrow viewport with no horizontal overflow.
- Confirm the community destination is visible without opening a menu and resolves to the canonical `/community/` route.
- Confirm desktop navigation remains unchanged.

## Documentation Updates

Record the persistent mobile community entry as a discovery rule in the community domain documentation.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Implement the navigation change.
- [x] Run targeted verification.
- [x] Update domain documentation with the discovery rule.
