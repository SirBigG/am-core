# Asynchronous Random Post Recommendations

- Date: 2026-07-16
- Status: Complete
- Related plan: `docs/work/plans/2026-07-16-async-random-recommendations.md`
- Related domain: `docs/business/domains/catalog-information/README.md`

## Outcome

The public “Цікавинки на додачу” block now loads as an independent HTMX fragment on post, advert, company, and news detail pages. It no longer adds recommendation selection and photo queries to the initial page response.

Each fragment request:

- selects four posts with `SystemRandom` rather than `ORDER BY RANDOM()`;
- uses only active posts with a non-empty image;
- prefers one post from each broad MPTT category tree;
- excludes the current post when supplied;
- excludes the four visible IDs on refresh, falling back to repeats only when the eligible pool is too small;
- returns `Cache-Control: no-store` so a selected set cannot become sticky in browser or proxy caches.

The eligible `(post_id, category_tree_id)` pool is cached for five minutes per cache process. Selection itself is shuffled independently on every request. Selected posts and ordered photos are then loaded in the chosen random order.

## User Experience

- The initial page displays a four-card loading skeleton while HTMX retrieves the fragment.
- “Інші варіанти” replaces the complete block with a fresh non-overlapping set.
- The refresh control disables itself while its request is running.
- Reduced-motion preferences disable the skeleton animation.
- Without JavaScript, primary content remains available and the block displays a short fallback message.

## Performance Evidence

Measured locally with the existing PostgreSQL data, Silk excluded, and LocMemCache enabled:

| Request | SQL queries | Local elapsed |
| --- | ---: | ---: |
| Initial post detail | 16 | 136 ms |
| Recommendation fragment, cold candidate cache | 3 | 9 ms |
| Recommendation fragment, warm candidate cache | 2 | 4 ms |

The previous cold post-detail measurement was 20 queries with synchronous global recommendations. Exact elapsed values are directional; bounded query counts and removal of recommendation work from the initial response are the release signals.

## Verification

- Browser verification confirmed that the initial HTMX request loaded four posts and the refresh action returned four different posts.
- 11 focused recommendation and post-detail tests passed.
- 86 affected public-page tests passed across posts, companies, adverts, news, and CSP coverage.
- The full Django suite ran 418 tests and retained only two unrelated baseline failures in untouched profile-copy and feedback success-template behavior.
- Targeted Flake8 passed for the new service, view, URL, template tag, and tests.
- Both new Django templates passed targeted djLint.
- The frontend production build completed; its existing Sass deprecation warnings remain unchanged.
- `git diff --check` passed.

## Operational Notes

- No migration or new service is required.
- HTMX 2.0.10 is loaded only on pages that render this recommendation loader.
- LocMemCache is per Daphne process, but only the eligible pool is cached; displayed selections remain random per request.
- Deployment should continue changing `MEDIA_VERSION` so browsers receive the rebuilt stylesheet immediately.
