# Public website performance investigation

Date: 2026-09-07. Local source baseline: `7b74ba2`.

## Outcome

The reported PageSpeed Insights desktop scores of 66 for `/product` and 79 for
`/development` could not be reproduced. Both routes scored 100 in two fresh
desktop Lighthouse runs each against the deployed website. No failing metric
or route-specific rendering bottleneck was established. No application code,
component boundaries, metadata, dependencies or visual behavior was changed.
There is no measured or expected improvement from this documentation-only pass.

The original PSI report URLs/JSON were unavailable. An unauthenticated PSI API
request returned a daily-quota error. The measurements below are **local
Lighthouse CLI lab audits of production**, not new PSI results or CrUX data.
They cannot identify retrospectively which metric caused the original scores.

## Measurements

Lighthouse 13.4.1, installed temporarily with `pnpm dlx`; headless Chrome 152 on
Windows; desktop preset, simulated 40 ms RTT / 10,240 Kbps, CPU multiplier 1,
1350 × 940 viewport. Audits ran sequentially before builds and tests. Requests
used `https://kyrion.ch`, which redirects to `https://www.kyrion.ch`.

All timings below are milliseconds, rounded. Every run also scored 100 for
accessibility, best practices and SEO. Every report has no Lighthouse runtime
error. CLI cleanup sometimes exited with Windows `EPERM` after writing a
complete report; this is a runner cleanup limitation, not a page failure.

| Route / run      | Performance | FCP | LCP | Speed Index | TBT | CLS | Main-thread work |
| ---------------- | ----------- | --- | --- | ----------- | --- | --- | ---------------- |
| `/product` 1     | 100         | 474 | 634 | 474         | 0   | 0   | 156              |
| `/product` 2     | 100         | 473 | 633 | 473         | 0   | 0   | 162              |
| `/development` 1 | 100         | 483 | 655 | 483         | 0   | 0   | 164              |
| `/development` 2 | 100         | 477 | 638 | 477         | 0   | 0   | 168              |
| `/`              | 100         | 478 | 638 | 529         | 0   | 0   | 207              |
| `/about`         | 100         | 472 | 632 | 472         | 0   | 0   | 383              |
| `/docs`          | 100         | 476 | 638 | 476         | 0   | 0   | 152              |
| `/contact`       | 100         | 478 | 641 | 478         | 0   | 0   | 171              |

These are baseline observations, not before/after improvements. The desktop
results do not establish a mobile score improvement. Homepage mobile was left
alone because no obvious actionable regression was found.

## Route and component comparison

- Product and Development are Server Components selected by the same statically
  generated `[[...path]]` entry point as the other pages. Their static sections
  have no state, mount effects, scroll handlers or observers to hydrate.
- `PageHero` is also used by About, Docs and Contact. `StatusBadge`, `CTASection`
  and the other shared presentation helpers are server-rendered. There is no
  shared client animation wrapper, diagram or roadmap explaining the score gap.
- Product renders nine feature cards. Development renders nine capability rows,
  four status explanations and three roadmap entries. These small server-side
  array operations do not run as client rendering loops.
- A separate browser inspection counted 275 DOM elements / 17 inline SVGs on
  Product and 265 / 8 on Development, versus 380 / 28 on Home and 255 / 17 on
  About. Neither target has an unusually large component tree.
- The targets' LCP elements are their text headings. Fonts use the system stack;
  no font files are downloaded. Shared SVG logos have explicit dimensions.
  There are no route-specific large images or below-the-fold media to defer.
- Neither target uses animation libraries, IntersectionObserver, scroll effects,
  backdrop filters, large blurred layers or expensive animated properties.
  Development's decorative gradient is a static one-pixel line. Homepage has
  more decorative content yet scored 100 in the desktop audit.
- Header/menu, theme controls and the contact form are the existing interactive
  islands. Theme initialization, hover transitions and reduced-motion rules
  remain unchanged. No third-party resources were reported in the Product audit.

## Payloads and shared opportunities

All six routes loaded the **same ten JavaScript resources** in Lighthouse:
639,225 decoded bytes, approximately 197.5 kB transferred including response
overhead. Product and Development do not ship additional route-specific client
JavaScript relative to the comparison pages.

The local production build's HTML sizes are below; gzip values are calculated
with Node's default gzip settings, not measured Vercel transfers.

| Route          | HTML bytes | Gzip bytes |
| -------------- | ---------- | ---------- |
| `/`            | 78,577     | 14,069     |
| `/product`     | 57,055     | 8,933      |
| `/development` | 57,250     | 8,679      |
| `/about`       | 51,708     | 9,215      |
| `/docs`        | 36,908     | 7,125      |
| `/contact`     | 40,568     | 8,830      |

Next.js 16's build summary confirms prerendered public pages but does not print
per-route JavaScript sizes. Inspecting generated HTML and browser requests avoids
mistaking the legacy `nomodule` bundle for JavaScript loaded by modern browsers.

Two shared opportunities were identified, neither established as the cause of
the reported PSI difference:

1. The catch-all entry point statically imports every page, so the contact-form
   chunk is requested even on informational pages (25,232 decoded bytes in
   production, plus shared dependencies). A future focused bundle change could
   isolate this interaction and compare initial loads and navigation into Contact.
   No lazy-loading boundary was added here: all measured TBT values are zero,
   and changing form loading without a demonstrated bottleneck is speculative.
2. The apex-to-www redirect applies across the website. The first Product audit
   estimated 220 ms potential redirect savings. This is an audit estimate, not a
   measured improvement or an explanation for a route-only regression. Metadata
   currently names the apex host. Review the intended canonical host and Vercel
   domain configuration together in a separate deployment/SEO decision.

Both theme logo variants are preloaded globally, with about 4.2 kB combined
transfer in the Product audit. This is not a target-specific LCP image problem;
theme asset loading was preserved rather than traded for possible theme flashes.

## Validation and reproduction

Passed: `pnpm --filter website lint`, `typecheck`, `format:check`, `build` and
`test`. All 20 Playwright tests passed against the production build, including
both locales, metadata, theme persistence/system selection, mobile keyboard
navigation, reduced motion, narrow screens and contact behavior.

No permanent Lighthouse/bundle-analysis dependency was added. Reports and
investigation scripts were saved locally under the ignored directory
`.run/browser-review/website-performance/`.

Example command from the repository root (Chrome must be installed):

```sh
pnpm dlx lighthouse@13.4.1 https://www.kyrion.ch/product --preset=desktop --output=json --output-path=.run/browser-review/website-performance/product.json --chrome-flags=--headless
```

Before changing production code, rerun PSI desktop at least three times for
Product and Development plus a control page, on the same deployment and final
host. Save report links/JSON, timestamps, Lighthouse versions, FCP, LCP, Speed
Index, TBT, CLS and diagnostics. Test the apex redirect separately. If low scores
recur, use LCP breakdown, server response timing, render-blocking requests and
main-thread tasks to identify the responsible metric. Keep accessibility, best
practices and SEO at 100, and retain a homepage mobile regression check. There
is no runtime change from this pass to deploy or claim as a score improvement.
