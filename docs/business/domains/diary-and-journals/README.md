# Domain: Diary And Journals

## Purpose

Diary supports personalized user plant, field, and related journals. It is a private or user-centered workspace for tracking agricultural activity and observations.

## Actors

- Users who create and maintain their diaries.
- Possible advisors, administrators, or collaborators if sharing exists.

## Core Workflows

- A user creates personal diary or journal records.
- A user tracks plant, field, or agricultural activity over time.
- A user reviews their own history and observations.
- A user creates a visual planner and arranges physical growing zones in real-world metres.
- A user explicitly chooses the planner width, length, and grid precision before the first canvas is created.
- A user may keep multiple plans for different seasons or locations and switch between them from the planner header.
- A user may duplicate a plan for a new season. The copy preserves the canvas and physical zones but never copies diary links or plant placements.
- Planner progress is derived from existing data rather than stored separately: plan created, zones added, plants placed, and at least one planting moved beyond the planned state.
- Planner tasks represent future seasonal work. They may target the entire plan or one physical zone and do not create diary history automatically.
- Users can update task scope and due date, and filter the planner task list without changing task history.
- A non-empty task list prevents planner deletion just like physical zones do.
- A planner zone may connect to an existing diary so physical layout, plants, and activity history remain one data set.

## Business Rules

- Diary information is personalized to the user.
- Diary records may relate to plants, fields, journals, or other agricultural tracking needs.
- Privacy and ownership are central to this domain.
- A diary represents activity history; a planner area represents physical growing space.
- Connecting a diary to a planner area is optional.
- Removing a planner area must not delete its linked diary or plants.
- A planner can only be deleted while it has no physical zones.
- A planner placement connects one existing active plant or planting group to one physical area.
- Placement quantity may be exact, approximate, expressed as rows or occupied area, broadcast sowing, or intentionally unknown.
- A placement also has relative geometry inside its physical area so crop groups can be moved and resized without changing real plant records.
- A user may create a new plant directly from the planner. It becomes a regular `Plant` and, when the area has a diary, is attached to that diary with a planted history item.
- Planner planting lifecycle states are planned, planted, growing, harvest, and completed.
- Completing a planner planting completes the shared plant and records completion in its linked diary; returning it to an active state restores the plant.
- Spacing guidance may only use measurement-bearing lines from a Ready and AI-enabled category profile.

## States And Lifecycle

The confirmed lifecycle is still unknown. Likely states to clarify include active, completed, archived, deleted, or shared.

## Neighboring Domains

- Catalog information, if diary entries reference varieties, diseases, or other catalog records.
- Authentication and identity, because diary ownership and privacy depend on users.
- Classification and taxonomy, if diary entries use categories.

## Implementation Map

- Django app: `core/diary`.
- Planner models: `Planner`, `PlannerArea`, `PlannerPlanting`.
- Authenticated planner route: `/profile/planner`.

## Open Questions

- Are diary records private by default?
- Can users share diaries with advisors, companies, or other users?
- What exact journal types exist today: plant, field, treatment, observation, harvest, or others?
- Are reminders, tasks, photos, or measurements part of the domain?
- Should planners support nested areas, such as beds inside a greenhouse?
- Should users be able to split one existing plant group across multiple physical areas?
