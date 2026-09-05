# Reading navigation verification

The main base template loads `j-reading-navigation.js`; editable code lives in
`frontend/src/js/reading-navigation.js`, with shared styles in `site.scss`.
Rebuild with the existing static build and collectstatic workflow when changing
these assets, and update their template URL versions to avoid stale browser CSS.

Verified locally on the Sokilska sheep publication (post 4081) through Nginx:

- 1440 × 900: three body headings produce a side TOC without narrowing the article
  or creating horizontal overflow. The active link follows the selected section.
- 390 × 844: sticky disclosure closes after selection. The target heading landed
  at approximately 144px, below the disclosure's bottom at approximately 134px.
- A fragment reload returns to the selected heading below the category menu.
- After scrolling beyond two viewport heights the back-to-top button appears;
  on mobile its bottom stays 16px above the bottom navigation. Clicking returns
  to scrollY 0 and hides the button.
- Static production build passed (existing Sass deprecation warnings).
- Existing publication-actions Node suite: 6 passing tests. `git diff --check`
  and JavaScript syntax check passed.

Native smooth scrolling stalled in the test browser. The shared helper therefore
uses a short requestAnimationFrame animation with immediate scroll steps. It
respects reduced motion and cancels on keyboard, pointer, wheel or touch input.
No database changes, dependency changes, or community-app template changes.
