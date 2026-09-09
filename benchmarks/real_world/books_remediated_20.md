# Brand AI-Readiness Audit Report: books.toscrape.com

## Executive Summary

- **Target URL**: https://books.toscrape.com
- **Audited At**: 2026-09-08T19:38:45.114012Z
- **AI Readiness Score**: `26/100`
- **Overall Journey Score**: `62/100`
- **Findings Summary**: 8 total (0 critical, 7 high, 1 medium, 0 low)

## Agent Journey Scorecard

| Pillar | Score | Status | Description |
|---|:---:|:---:|---|
| **Reach** | `47/100` | At Risk | Crawlability, robots compliance, and indexability without barriers |
| **Read** | `70/100` | Attention Needed | Clean text and heading extractability without JavaScript traps |
| **Understand** | `25/100` | At Risk | Rich, valid Schema.org structured data and entity identity |
| **Trust** | `70/100` | Attention Needed | Freshness, provenance, and factual consistency across pages |
| **Navigate** | `77/100` | Attention Needed | Traversable internal link architecture without dead ends |
| **Act** | `85/100` | Attention Needed | Clear calls-to-action and machine-discoverable contact channels |
| **Overall Journey** | `62/100` | - | Unweighted average across all 6 pillars |

## Crawl Coverage Summary

- **Pages Discovered**: 97
- **Pages Crawled**: 20 / 20 cap
- **Pages Skipped**: 0
- **Crawl Duration**: 15.4s
- **Robots.txt Status**: `404`
- **JS Rendering**: `disabled`

## Top Priorities

| Rank | Finding ID | Title | Severity | Confidence | Affected Pages | Priority Score | Suggested Action |
|:---:|:---:|---|:---:|:---:|:---:|:---:|---|
| 1 | `F-001` | Important pages lack machine-readable summary metadata (1 page(s)) | `high` | `high` | 5 | `64.7` | Ensure every important page has a descriptive <title> (10-70 chars) and <meta name='description'> (50-160 chars) capturing the page's core value. |
| 2 | `F-002` | Important pages missing agent-actionable structured data (1 page(s)) | `high` | `high` | 5 | `61.9` | Add appropriate Schema.org JSON-LD to important pages: Product/Offer on product pages, Event on event pages, Organization/WebSite on the homepage. Focus on pages with highest importance scores first. |
| 3 | `F-003` | No canonical tags on any crawled page | `high` | `high` | 5 | `56.2` | Add <link rel='canonical'> to every page pointing to its preferred URL. |
| 4 | `F-005` | Conflicting pricing information detected across 17 crawled pages | `high` | `high` | 5 | `41.2` | Reconcile product pricing across product pages, pricing tables, and structured data. |
| 5 | `F-006` | No structured data on 18/18 product/service pages | `high` | `high` | 5 | `41.2` | Add Product/Offer/Service JSON-LD to every product and service page. |

## Agent Answerability

| Question | Status | Confidence | Evidence & Citation |
|---|:---:|:---:|---|
| **What does this company do?** | `Conflicting` | `low` | Contradictory entity identity or company descriptions detected across crawled pages.<br>*Sources: https://books.toscrape.com/* |
| **What products/services does it offer?** | `Supported` | `high` | Found 18 product/service page(s): All products | Books to Scrape - Sandbox, A Light in the Attic | Books to Scrape - Sandbox.<br>*Sources: https://books.toscrape.com/catalogue/page-2.html, https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html, https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html* |
| **Where is it located?** | `Not found` | `low` | No physical address or geographic location declared in JSON-LD or contact text. |
| **What does the product cost?** | `Conflicting` | `low` | Conflicting pricing found between visible content and structured data.<br>*Sources: https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html, https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html* |
| **How can users contact it?** | `Not found` | `low` | No email, telephone number, or dedicated contact page discovered. |

## Strengths

- **[Discoverability]** No noindex directives on any crawled page
- **[Discoverability]** Homepage returns HTTP 200
- **[Discoverability]** All crawled pages return HTTP 200
- **[Discoverability]** All crawled pages have content without JS rendering
- **[Discoverability]** All images have alt text across crawled pages
- **[Discoverability]** Contact information accessible
- **[Discoverability]** All crawled pages have date signals
- **[Engagement]** Homepage has a clear primary call-to-action
- **[Engagement]** Site navigation has descriptive text labels
- **[Engagement]** No dead-end pages found — all pages have onward navigation
- **[Discoverability]** All high-importance pages are reachable from homepage within 3 hops
- **[Discoverability]** All important pages use canonical URL patterns

## Proactive Opportunities

| ID | Title | Category | Priority | Rationale |
|:---:|---|:---:|:---:|---|
| `PRO-001` | Add BreadcrumbList structured data to reflect site hierarchy | `discoverability` | `low` | 17 crawled pages are at depth > 2, suggesting a hierarchical structure, but no BreadcrumbList JSON-LD was found. Breadcrumbs help AI agents understand content context and navigation paths. |
| `PRO-002` | Add VideoObject JSON-LD to pages featuring video content | `discoverability` | `medium` | 17 page(s) appear to feature video content based on text signals, but no VideoObject schema was detected. VideoObject markup with transcript or description dramatically increases AI discoverability of multimedia content. |
| `PRO-003` | Add HowTo structured data to guide and tutorial pages | `discoverability` | `medium` | 1 page(s) have headings suggesting step-by-step guides, but no HowTo JSON-LD was found. HowTo schema is among the highest-ROI types for 'how do I' AI assistant queries. |
| `PRO-004` | Complete OpenGraph tags for richer social sharing previews | `engagement` | `low` | 20 of 20 pages (100%) are missing og:title, og:description, or og:image. Complete OpenGraph tags improve how content appears when shared on social media and in AI-powered link previews, driving referral traffic. |

## Detailed Audit Findings

### `F-001`: Important pages lack machine-readable summary metadata (1 page(s))

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `meta-description, page-title, machine-readable, discoverability, stale-content, freshness, duplicate-content, seo-hygiene, heading-structure`
- **Evidence**: 1 of 1 important page(s) (importance >= 60) are missing title or meta description. Sample: https://books.toscrape.com/index.html (no meta description). AI agents use these signals to determine page relevance without full rendering. [Also: freshness-corroboration-audit: 20 of 20 pages with date signals contain stale time-sensitive content (older than 365 days). Oldest page: https://books.toscrape.com/ (2023-02-08).] [Also: structured-data-content-audit: Identical title 'All products | Books to Scrape - Sandbox' is shared across 3 distinct pages (https://books.toscrape.com/, https://books.toscrape.com/index.html, https://books.toscrape.com/catalogue/p] [Also: structured-data-content-audit: 3 page(s) skip heading levels (e.g. H1 → H3 without H2). Example: https://books.toscrape.com/ headings: ['H1', 'H3', 'H3', 'H3', 'H3']] [Also: structured-data-content-audit: Identical title 'All products | Books to Scrape - Sandbox' is shared across 3 distinct pages (https://books.toscrape.com/, https://books.toscrape.com/index.html, https://books.toscrape.com/catalogue/p]
- **Affected URLs** (5): https://books.toscrape.com/, https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html, https://books.toscrape.com/catalogue/page-2.html, https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html, https://books.toscrape.com/index.html
- **Suggested Action**: Ensure every important page has a descriptive <title> (10-70 chars) and <meta name='description'> (50-160 chars) capturing the page's core value. *(Priority: high, Effort: low)*

### `F-002`: Important pages missing agent-actionable structured data (1 page(s))

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `json-ld, schema-org, structured-data, discoverability, machine-readable`
- **Evidence**: 1 important page(s) of types that benefit from structured data have no actionable JSON-LD: 1 Homepage. Without structured data, AI agents cannot reliably extract offers, schedules, or entity details. [Also: structured-data-content-audit: Crawled 20 pages; 0/20 contain JSON-LD structured data. AI assistants cannot extract machine-readable facts about this site.]
- **Affected URLs** (5): https://books.toscrape.com/, https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html, https://books.toscrape.com/catalogue/page-2.html, https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html, https://books.toscrape.com/index.html
- **Suggested Action**: Add appropriate Schema.org JSON-LD to important pages: Product/Offer on product pages, Event on event pages, Organization/WebSite on the homepage. Focus on pages with highest importance scores first. *(Priority: high, Effort: medium)*

### `F-003`: No canonical tags on any crawled page

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `canonical, crawlability`
- **Evidence**: 0 of 20 crawled pages contain a <link rel='canonical'> tag. Without canonicals, duplicate content dilutes AI citation quality.
- **Affected URLs** (5): https://books.toscrape.com/, https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html, https://books.toscrape.com/catalogue/page-2.html, https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html, https://books.toscrape.com/index.html
- **Suggested Action**: Add <link rel='canonical'> to every page pointing to its preferred URL. *(Priority: high, Effort: medium)*

### `F-004`: No About page detected

- **Severity**: `HIGH` | **Confidence**: `medium` | **Category**: `discoverability`
- **Tags**: `about-page, entity-identity, entity-disambiguation, navigation, value-proposition`
- **Evidence**: None of 20 crawled URLs match about-page patterns (/about, /who-we-are, /our-story, ...) and no page title contains 'About'. [Also: engagement-audit: None of 20 crawled URLs match about/team page patterns, and no title contains 'About' or 'Our Team'. First-time visitors cannot learn who is behind the site.]
- **Affected URLs** (1): https://books.toscrape.com/
- **Suggested Action**: Consider creating an About page with org name, description, founding year, and mission. *(Priority: high, Effort: medium)*

### `F-005`: Conflicting pricing information detected across 17 crawled pages

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `pricing, corroboration, contradiction`
- **Evidence**: Contradicting price figures discovered: https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html declares $51.77 while https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html declares $53.74 for 'A Light in the Attic'. Discrepancies in published pricing confuse AI assistants and undermine transactional trust.
- **Affected URLs** (5): https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html, https://books.toscrape.com/catalogue/olio_984/index.html, https://books.toscrape.com/catalogue/our-band-could-be-your-life-scenes-from-the-american-indie-underground-1981-1991_985/index.html, https://books.toscrape.com/catalogue/rip-it-up-and-start-again_986/index.html, https://books.toscrape.com/catalogue/sapiens-a-brief-history-of-humankind_996/index.html
- **Suggested Action**: Reconcile product pricing across product pages, pricing tables, and structured data. *(Priority: high, Effort: low)*

### `F-006`: No structured data on 18/18 product/service pages

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `json-ld, schema-org, structured-data`
- **Evidence**: 18 of 18 product/service pages contain no JSON-LD. AI cannot extract product details, prices, or specs.
- **Affected URLs** (5): https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html, https://books.toscrape.com/catalogue/page-2.html, https://books.toscrape.com/catalogue/sharp-objects_997/index.html, https://books.toscrape.com/catalogue/soumission_998/index.html, https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html
- **Suggested Action**: Add Product/Offer/Service JSON-LD to every product and service page. *(Priority: high, Effort: medium)*

### `F-007`: Missing Organization or WebSite schema on homepage

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `json-ld, schema-org, entity-identity`
- **Evidence**: Homepage (https://books.toscrape.com/) has no JSON-LD with an Organization, WebSite, or brand entity type. Found types: none. AI assistants cannot reliably identify and describe this brand.
- **Affected URLs** (1): https://books.toscrape.com/
- **Suggested Action**: Add Organization and WebSite JSON-LD to the homepage with name, url, logo, description, and sameAs properties. *(Priority: high, Effort: low)*

### `F-008`: No sitemap signal detected — bulk agent discovery may be impaired

- **Severity**: `MEDIUM` | **Confidence**: `medium` | **Category**: `discoverability`
- **Tags**: `discoverability, crawlability, indexability, sitemap`
- **Evidence**: No sitemap.xml reference found in robots.txt, crawl metadata, or any of the 20 crawled pages. AI indexing systems rely on sitemaps for efficient bulk content discovery, especially for sites with many pages.
- **Affected URLs** (1): https://books.toscrape.com/
- **Suggested Action**: Consider publishing an XML sitemap at /sitemap.xml and referencing it in robots.txt (Sitemap: https://yourdomain.com/sitemap.xml). Include all important pages with <lastmod> dates. *(Priority: medium, Effort: low)*

## Methodology & Limitations

- **Scope**: Evaluates technical AI discoverability, content extractability, structured data completeness, and citation readiness based on an observable crawl snapshot.
- **Scoring Principles**: All scoring formulas and journey deductions are 100% deterministic and rule-grounded, measuring concrete technical readiness rather than subjective or volatile LLM search rankings.
- **Execution Guarantee**: This audit operates purely in read-only analysis mode without modifying site infrastructure, publishing changes, or executing non-idempotent operations.
- **Known Boundaries & Constraints**:
  - Crawl depth is capped at 20 pages per run under standard execution parameters.
  - Dynamic Single-Page Application (SPA) content requires headless rendering with Playwright fallback when JavaScript rendering is enabled.
  - Content behind authentication, paywalls, or strict CAPTCHA barriers is outside audit scope.
