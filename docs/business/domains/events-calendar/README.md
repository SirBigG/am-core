# Domain: Events Calendar

## Purpose

Events calendar lets anyone share events with other people. It is the shared calendar for agricultural or community events.

## Actors

- Users or organizers who create and share events.
- Users who browse events.
- Administrators or moderators who may review, edit, hide, or remove events.

## Core Workflows

- A person creates an event.
- Other people discover the event through the calendar.
- Event information is updated as details change.

## Business Rules

- Anyone can share an event, subject to permissions and moderation rules that still need confirmation.
- Event information should be understandable to people who may attend or follow the event.
- Date and calendar accuracy are central to the domain.

## States And Lifecycle

The confirmed lifecycle is still unknown. Likely states to clarify include draft, published, updated, cancelled, completed, hidden, or archived.

## Neighboring Domains

- Classification and taxonomy, if events are categorized.
- Companies and shops, if organizations host or sponsor events.
- Authentication and identity, if event ownership or editing rights depend on the creator.

## Implementation Map

- Django app: `core/events`.

## Open Questions

- Does event creation require login?
- Is moderation required before publication?
- Are event organizers modeled separately from creators?
- Are recurring events, locations, registration, or attendance tracked?
- What happens after an event date passes?
