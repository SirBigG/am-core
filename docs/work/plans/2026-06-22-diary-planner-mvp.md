# Plan: Diary Planner MVP

- Date: 2026-06-22
- Status: First implementation block complete
- Owner: Product and engineering
- Related domain: Diary And Journals
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`

## Goal

Add a visual garden planner to the authenticated diary workspace. A user should be able to create a real-size planning canvas, add growing zones, move and resize them, and connect a zone to an existing diary without duplicating diary or plant data.

## Non-Goals

- A full CAD or GIS editor.
- Satellite maps, GPS boundaries, collaboration, or public sharing.
- Automatic agronomic spacing recommendations in the first implementation block.
- Representing every seed as an individual `Plant` record.
- Replacing existing diary and plant pages.

## Current Understanding

- `Diary` is the activity history and currently owns a many-to-many relationship with `Plant`.
- `Plant` may represent an individual plant or a group planting; the current model does not require one record per physical seed.
- The planner must be another view over the same user-owned diary data.
- A physical planner zone may optionally link to one diary. The diary remains the journal; the zone represents physical space.

## Assumptions

- The first release supports multiple planners per user in the data model, while the UI opens the most recently updated planner.
- Canvas and zone dimensions are stored in metres.
- A planner is never silently created with fixed dimensions; the user confirms the initial width and length.
- Zones are axis-aligned rectangles in the MVP.
- One diary can be connected to at most one zone to avoid ambiguous physical placement.
- Plant layout supports exact quantity, approximate quantity, rows, occupied area, broadcast sowing, and intentionally unknown quantity.

## Proposed Approach

### Data model

- `Planner`: user-owned canvas with a title, width, height, and grid step.
- `PlannerArea`: a bed, greenhouse, field, garden, or other physical zone. Stores type, title, colour, real-size position and dimensions, plus an optional one-to-one diary link.
- `PlannerPlanting` connects existing plants to a planner area and stores layout mode, approximate quantity, rows, occupied area, and notes.

### UI

- Add `Мій планер` beside diary and plant navigation.
- Render a responsive workspace with a toolbar, scaled grid canvas, zone library, inspector, and summary metrics.
- Support pointer-based drag and resize with grid snapping.
- Support relative drag and resize for crop placements inside each area.
- Persist every completed drag/resize through authenticated Django endpoints.
- Show linked diary plants inside each zone as the first shared-data visualization.

### API

- Keep endpoints private to the authenticated profile namespace.
- Scope all reads and writes by `request.user`.
- Validate dimensions server-side and keep areas within planner bounds.
- Use CSRF-protected POST requests for creation, update, and deletion.

## Risks And Unknowns

- Existing diary semantics are broader than physical zones, so linking remains optional.
- Nested structures, for example beds inside a greenhouse, need a later product decision.
- Mobile editing requires a minimum canvas width and horizontal panning to avoid unusably small controls.
- Existing `Plant` records do not yet contain placement density or planting layout.

## Test Strategy

- Model ownership and optional diary linking.
- Profile page visibility and user data isolation.
- Area creation, bounds clamping, update, deletion, and cross-user protection.
- Navigation rendering.
- Desktop and mobile browser verification for drag, resize, overflow, and inspector layout.

## Documentation Updates

- Update the Diary And Journals domain note once planner terminology and lifecycle are confirmed through implementation.
- Create a result artifact after the MVP verification pass.

## Implementation Checklist

- [x] Confirm initial scope and assumptions.
- [x] Add models and migration.
- [x] Add authenticated planner endpoints.
- [x] Add profile navigation and editor UI.
- [x] Implement drag, resize, create, and delete interactions.
- [x] Add tests and run verification.
- [x] Update domain and result documentation.
