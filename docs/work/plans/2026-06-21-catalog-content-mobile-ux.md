# Plan: Catalog Content Mobile UX

- Date: 2026-06-21
- Status: Draft
- Owner: AgroMega team
- Related domain: Catalog information; Classification and taxonomy
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`

## Goal

Improve the mobile user experience for catalog-style content pages so users can more easily browse plant variety lists, understand base/category pages, and read publication detail pages without getting lost in long unstructured link and content stacks.

The first target example is `/cybulevi/sorty-cybuli/`, and the same patterns should apply to similar registry variety-list pages, base category pages, post category pages, and final publication detail pages.

## Non-Goals

- Do not change registry/category data models in this pass.
- Do not hide local/test-looking content.
- Do not redesign desktop-first editorial workflows or admin screens.
- Do not change canonical URLs, routing, or SEO metadata behavior unless the current markup blocks the UX work.
- Do not move forum-owned pages or sibling `forum_instance` templates in this block.

## Current Understanding

- Registry category pages are rendered from:
  - `core/registry/templates/registry/index.html`
  - `core/registry/templates/registry/categories.html`
  - `core/registry/templates/registry/varieties.html`
- Catalog/post category and detail pages are rendered from:
  - `core/posts/templates/posts/parent_index.html`
  - `core/posts/templates/posts/list.html`
  - `core/posts/templates/posts/detail.html`
  - `core/posts/templates/posts/helpers/object_list.html`
- The mobile UX pass already introduced shared catalog/listing utilities such as `site-link-grid`, `site-category-card`, `site-detail-panel`, and mobile-safe bottom navigation in `templates/base.html`.
- Variety-list pages currently behave like a heading, breadcrumbs, optional meta text, and grouped lists. This is functional, but long pages are hard to scan on a phone.
- Publication detail pages still use older article markup with a stacked hero image, body content, variety table, dates, feedback, comments, products, related posts, and adverts. The content order is useful, but visual hierarchy is weak on mobile.

## Assumptions

- Users visiting variety/category pages are usually browsing or comparing, not reading a single narrative article.
- Variety names and country flags are useful signals and should remain visible.
- A variety with no linked publication should still remain visible, but should look like reference information rather than a broken link.
- Existing SEO title, meta description, breadcrumbs, and URL structure should be preserved.
- The mobile design should continue using the restrained AgroMega green/neutral style established in the previous mobile UX work.

## Proposed Approach

### 1. Registry Variety Lists

- Add a shared mobile-friendly registry/list page shell:
  - Compact intro panel with title, breadcrumb context, and optional meta text.
  - Count/summary row when the template can derive a useful count from existing context.
  - Clear distinction between linked varieties and unlinked reference-only varieties.
- Replace plain alphabet sections with structured cards or section panels:
  - Section header for each alphabet group.
  - Tappable rows with at least 44-48px target height.
  - Country flag aligned consistently without shrinking row text.
- Add a sticky or horizontally scrollable alphabet jump rail when many groups exist.
- Keep the long list visible and complete; do not collapse content behind hidden accordions by default.

### 2. Registry Base And Child Category Pages

- Reuse the same intro/page shell for registry index and category pages.
- Present child categories as cards or dense link tiles rather than a bare list.
- Keep category meta text readable in a panel with mobile-safe spacing.
- Preserve breadcrumbs and make them visually lighter so they help orientation without dominating the first viewport.

### 3. Post Category Pages

- Align post category pages with the new registry/category treatment:
  - Better first viewport: title, short category context, and primary browse controls.
  - Existing `A-Я` / `СПИСОК` mode controls should become full-width, readable mobile segmented controls.
  - Reuse existing listing-card styles where possible.
- Avoid creating a separate visual language for posts versus registry pages unless the content type requires it.

### 4. Publication Detail Pages

- Wrap article/detail content in a readable mobile detail layout:
  - Hero/media section with stable image dimensions.
  - Article body panel with comfortable line length and spacing.
  - Metadata section for author, publish date, update date, views, and share action.
- Move `variety_item_table` into a named panel such as "Сорт у реєстрі" so users understand why a table appears inside an article.
- Turn the "Публікація корисна?" controls into a compact feedback panel.
- Separate comments, products, related posts, adverts, and random posts into clearly titled sections with consistent spacing.
- Ensure long source URLs and tables do not create horizontal overflow.

## Risks And Unknowns

- Some category meta text may contain rich HTML that needs defensive styling.
- The registry variety context currently provides grouped `posts`, but not necessarily an explicit total count in the template. Count may need to be derived in the view or avoided if it creates complexity.
- Publication detail pages combine editorial content, registry details, comments, related posts, and ads; changing order could affect engagement or SEO if done too aggressively.
- Existing CSS from `posts/list.css` and `posts/detail.css` may override shared styles, so verification should inspect computed mobile rendering.
- Long Ukrainian titles and variety names may wrap awkwardly unless row/card dimensions are stable.

## Test Strategy

- Run targeted Django tests:
  - `just test-target core.registry`
  - `just test-target core.posts`
  - relevant CSP/template tests if template structure changes affect scripts/styles.
- Run targeted `djlint` on changed templates.
- Manual mobile browser checks at `390px` width:
  - `/registry/`
  - a registry base category page
  - `/cybulevi/sorty-cybuli/`
  - a post base category page
  - a post category list page
  - at least one publication detail page with a main photo and variety table
- Verify no page-level horizontal overflow, especially on tables, source URLs, flags, breadcrumbs, and long titles.
- Verify bottom navigation does not cover final page content or primary actions.

## Documentation Updates

- Update `docs/work/results/2026-06-21-mobile-ux-improvements.md` or create a dedicated result artifact after implementation.
- Update `docs/business/domains/catalog-information/README.md` if this work clarifies how registry varieties relate to post/publication content.
- Update `docs/business/domains/classification-and-taxonomy/README.md` if this work clarifies category navigation behavior or category page responsibilities.

## Implementation Checklist

- [ ] Confirm representative URLs for registry base category, child variety list, post category, and publication detail.
- [ ] Add or reuse shared CSS primitives for catalog intro panels, alphabet rails, grouped link cards, and detail sections.
- [ ] Improve registry variety-list template.
- [ ] Improve registry index/category templates.
- [ ] Improve post category/list templates and mode controls.
- [ ] Improve publication detail template sections.
- [ ] Run targeted template linting.
- [ ] Run targeted Django tests.
- [ ] Verify representative pages in the mobile browser.
- [ ] Record implementation results and remaining follow-ups.
