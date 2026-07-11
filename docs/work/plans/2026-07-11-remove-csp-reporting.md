# Plan: Remove CSP Violation Reporting

- Date: 2026-07-11
- Status: Implemented
- Owner: Codex
- Related domain: Application security
- Related decisions: None

## Goal

Keep the existing report-only Content Security Policy while stopping browsers and arbitrary clients from sending CSP reports to the application.

## Non-Goals

- Enforcing the CSP.
- Tightening the current source directives.
- Replacing the endpoint with another reporting service.

## Current Understanding

The report-only policy advertises `/csp/report/`. That public, CSRF-exempt endpoint logs every submitted payload and is producing high-volume, low-value log traffic.

## Proposed Approach

Remove the `report-uri` directive, URL route, ingestion view, and endpoint-specific tests. Keep tests proving that the report-only CSP header remains active and does not advertise a reporting destination.

## Risks And Unknowns

Production CSP violations will no longer be collected. The report-only policy will remain visible in browser developer tools and can be inspected manually while it is refined.

## Test Strategy

Run the targeted security-header tests and lint checks for the edited Python files.

## Documentation Updates

This plan records why reporting was removed. Historical upgrade records remain unchanged.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
