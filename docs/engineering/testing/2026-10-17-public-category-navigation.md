# Public category navigation

The desktop “Почитати” dropdown and mobile “Розділи” dropdown share
`templates/helpers/category_navigation.html`. Root categories with active
immediate children use native details/summary disclosures opening downwards.
Each disclosure includes an overview link to the existing root category page.
Roots without visible children remain direct links. Hidden roots and hidden
children are excluded. Deeper levels remain reachable through category pages.

`public_navigation` caches a serializable two-level payload for one hour under
`public_root_category_links_v2`; cold rendering uses one category query. The new
key prevents old flat payloads from hiding children after rollout. Taxonomy edits
remain subject to the existing one-hour navigation cache lifetime.

Bootstrap auto-close is set to outside for both category dropdowns so summary
activation does not close the containing menu. Native disclosure keyboard
behavior and Bootstrap Escape/outside-click closing remain available. Panels
scroll vertically and fit the viewport. The mobile dropdown uses static Bootstrap
positioning anchored to the whole bottom navigation, avoiding clipping caused
by positioning against its narrow first button.

Registry links are removed from shared header/mobile navigation. Registry URL
patterns, views, data, registry-internal breadcrumbs, sitemap rules and article
registry data tables are unchanged. Existing indexed registry URLs stay served.

## Local verification

- `docker compose exec -T core python manage.py test core.utils.tests.test_public_navigation core.registry --settings=settings.test_settings --noinput`: 24 tests passed.
- Production static build and collectstatic completed. Existing Sass deprecation
  warnings remain.
- Browser through local Nginx: desktop 1440×900 and mobile 390×844 / 320×740;
  tested downward disclosure, keyboard Enter, Escape and panel bounds. No
  horizontal page overflow; no registry links on the home page.
- The compiled site stylesheet is updated alongside its source; deployment must run
  the established static build and collectstatic workflow. The base template CSS
  URL version changes to invalidate browser caches.

This is local verification; production deployment is not part of this change.
