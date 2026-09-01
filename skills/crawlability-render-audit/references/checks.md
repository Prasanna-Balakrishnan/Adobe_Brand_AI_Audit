# Crawlability & Render Audit — Check Definitions

All checks use only data from `snapshot.json`. No live network calls.
Check IDs use prefix `CRA`. Thresholds are from `severity-rules.md`.

---

## CRA-001 — robots.txt blocks all crawling (CRITICAL)

**Category:** discoverability
**Confidence:** high (deterministic: parsed robots.txt)

**Trigger:** `crawl_meta.disallowed_paths` contains `"/"` AND `crawl_meta.pages_crawled <= 1`.

**Evidence:** List the disallowed paths found. State the robots.txt URL.

**Suggested action:** Review robots.txt and ensure crawlers can access public pages.
Use `Allow:` directives for specific paths if a broad `Disallow: /` is needed for
non-public sections.

---

## CRA-002 — noindex on all crawled pages (CRITICAL)

**Category:** discoverability
**Confidence:** high (deterministic: string match in meta_robots / x_robots_tag)

**Trigger:** `noindex` appears in `meta_robots` or `x_robots_tag` for **all** crawled
pages (`pages_crawled > 0` and 100% of pages have noindex).

**Evidence:** Count of pages with noindex / total pages crawled.

**Suggested action:** Remove `noindex` from public-facing pages; reserve it for
duplicate, thin, or administrative pages.

---

## CRA-003 — Homepage HTTP error (CRITICAL)

**Category:** discoverability
**Confidence:** high

**Trigger:** The first page in `pages[]` (the start_url page) has `status_code >= 400`.

**Evidence:** The URL and its HTTP status code.

**Suggested action:** Fix the server error. If a redirect is intended, ensure it
resolves to a 200 with appropriate content.

---

## CRA-004 — Redirect loop detected (HIGH)

**Category:** discoverability
**Confidence:** high

**Trigger:** Any page has `status_code == 310` (our sentinel for too-many-redirects)
OR `len(redirect_chain) > 5`.

**Evidence:** URLs with loop/excessive redirects; their redirect chains.

**Suggested action:** Audit the redirect rules; ensure each URL has at most one
canonical redirect destination.

---

## CRA-005 — noindex on majority of pages (HIGH)

**Category:** discoverability
**Confidence:** high

**Trigger:** >50% of crawled pages have `noindex` in `meta_robots` or `x_robots_tag`,
but NOT 100% (CRA-002 covers that case).

**Evidence:** Count of noindex pages / total. List affected URLs (up to 5 examples).

**Suggested action:** Audit which pages truly warrant noindex vs. which should be
indexable. Consider using `noindex` only on duplicate, staging, or utility pages.

---

## CRA-006 — Missing canonical on all pages (HIGH)

**Category:** discoverability
**Confidence:** high

**Trigger:** `canonical` is `null` or empty for 100% of crawled pages.

**Evidence:** Number of pages without canonical / total pages.

**Suggested action:** Add `<link rel="canonical">` to every page pointing to the
preferred URL. This is critical for preventing duplicate-content dilution.

---

## CRA-007 — Broken internal links (HIGH / MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:**
- HIGH: Pages with `status_code >= 400` that were reached via internal links AND
  represent >30% of crawled pages.
- MEDIUM: 10–30% of crawled pages are broken.
- LOW: <10% are broken (deduplicated by affected_urls overlap with other findings).

**Evidence:** Count of broken pages; list of broken URLs (up to 10).

**Suggested action:** Fix or remove broken internal links. Use a redirect for URLs
that have moved permanently.

---

## CRA-008 — JS-only content detected (HIGH)

**Category:** discoverability
**Confidence:** medium (heuristic: text length + SPA markers)

**Trigger:** Any page was `crawled_with_js: false` AND `visible_text_length < 300`
AND the raw HTML contains SPA root markers (`<div id="root">`, `<div id="app">`,
`data-reactroot`, `__NEXT_DATA__`).

**Evidence:** URLs with low text length; mention the SPA markers found; note whether
JS render was attempted.

**Suggested action:** Implement server-side rendering (SSR) or static site generation
(SSG) so crawlers receive fully-rendered HTML without executing JavaScript.

---

## CRA-009 — Missing canonical on some pages (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** 25–99% of crawled pages are missing canonical tags (CRA-006 covers 100%).

**Evidence:** Count missing / total. List up to 5 URLs missing canonical.

**Suggested action:** Systematically add canonical tags; prioritise high-traffic and
product/service pages.

---

## CRA-010 — Conflicting canonical (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** Any page where `canonical != final_url` AND `canonical` is not null AND
the canonical URL is not in `pages[]` (i.e. it points somewhere not crawled — could
be an error or cross-domain canonical).

**Evidence:** List pages where `canonical` differs unexpectedly from `final_url`.

**Suggested action:** Ensure each page's canonical tag points to its correct preferred
URL. Cross-domain canonicals require careful verification.

---

## CRA-011 — Missing title or meta description (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** >25% of pages have an empty `title` OR empty `meta_description`.

**Evidence:** Count of affected pages / total; list up to 5 examples.

**Suggested action:** Add descriptive, unique `<title>` and `<meta name="description">`
to every page. These are primary signals for AI assistants and search engines.

---

## CRA-012 — Thin content pages (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** >25% of pages have `visible_text_length < 200`.

**Evidence:** Count of thin pages / total; list URLs with their word counts.

**Suggested action:** Expand thin pages with meaningful content or consolidate them
into richer pages. Pages with < 200 characters of text provide little for AI
assistants to cite.

---

## Strengths to Detect

| Condition | Strength title | Category |
|-----------|---------------|----------|
| 0% of pages have noindex | "No noindex directives on any crawled page" | discoverability |
| 100% of pages have canonical | "Consistent canonical tags across all crawled pages" | discoverability |
| 0 pages have status >= 400 | "All crawled pages return HTTP 200" | discoverability |
| 0 pages show JS-only content | "All crawled pages have substantial content without JS rendering" | discoverability |
| robots.txt is accessible and allows crawling | "robots.txt present and permits crawling" | discoverability |
