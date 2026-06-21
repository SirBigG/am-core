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

## Business Rules

- Diary information is personalized to the user.
- Diary records may relate to plants, fields, journals, or other agricultural tracking needs.
- Privacy and ownership are central to this domain.

## States And Lifecycle

The confirmed lifecycle is still unknown. Likely states to clarify include active, completed, archived, deleted, or shared.

## Neighboring Domains

- Catalog information, if diary entries reference varieties, diseases, or other catalog records.
- Authentication and identity, because diary ownership and privacy depend on users.
- Classification and taxonomy, if diary entries use categories.

## Implementation Map

- Django app: `core/diary`.

## Open Questions

- Are diary records private by default?
- Can users share diaries with advisors, companies, or other users?
- What exact journal types exist today: plant, field, treatment, observation, harvest, or others?
- Are reminders, tasks, photos, or measurements part of the domain?
