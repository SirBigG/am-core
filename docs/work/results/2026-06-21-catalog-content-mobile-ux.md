# Result: Catalog Content Mobile UX

- Date: 2026-06-21
- Plan: `docs/work/plans/2026-06-21-catalog-content-mobile-ux.md`
- Branch: `adverts-pages-update`

## Completed

- Added shared catalog/article UI primitives in `templates/base.html` for mobile intro panels, stats chips, alphabet rails, alphabet sections, variety rows, segmented controls, article heroes, content sections, source lists, and table overflow wrappers.
- Improved registry root and registry category templates with a catalog intro panel, summary chips, and mobile-friendly category link grids.
- Improved registry variety-list templates with alphabet navigation, grouped section panels, linked and reference-only variety rows, country flags, and counts derived in the view.
- Improved post/category base, A-Z, and list pages with the same catalog shell so variety-like public URLs such as `/cybulevi/sorty-cybuli/` get the new mobile experience.
- Improved publication detail pages with a structured article hero, metadata chips, readable body section, named registry-data panel, source section, action/share section, feedback panel, comments section, products, related posts, adverts, and random posts in separated blocks.
- Updated catalog domain notes to document that some public variety-style URLs are served through `core/posts` templates while registry browsing also exists in `core/registry`.

## Verification

- `djlint` on changed shared, registry, and post templates.
- `uv tool run black --check core/registry/views.py core/posts/views.py`
- `just test-target core.registry`
- `just test-target core.posts`
- `just test-target core.utils.tests.test_csp_pages`
- Manual mobile browser checks at `390px` width:
  - `/registry/`
  - `/cybulevi/`
  - `/cybulevi/sorty-cybuli/`
  - `/cybulevi/sorty-cybuli/ibis-2779.html`
- Browser checks confirmed no page-level horizontal overflow, 48px list row targets on the example variety list, alphabet navigation rendering, sectioned publication detail rendering, and table containment.

## Follow-Ups

- Decide whether registry-specific URLs should become the canonical source for variety lists, or whether the current `core/posts` route remains the public catalog surface.
- Consider adding richer per-variety metadata to list rows if the view can safely expose registration year, applicant, or recommended zone without heavy queries.
- Consider hiding the "Сорт у реєстрі" section on non-variety publication pages if future checks show many ordinary articles use the same detail template.
