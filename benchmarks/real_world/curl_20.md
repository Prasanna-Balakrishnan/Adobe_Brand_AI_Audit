# Brand AI-Readiness Audit Report: curl.se

## Executive Summary

- **Target URL**: https://curl.se
- **Audited At**: 2026-09-08T19:10:13.995458Z
- **AI Readiness Score**: `28/100`
- **Overall Journey Score**: `68/100`
- **Findings Summary**: 9 total (0 critical, 6 high, 3 medium, 0 low)

## Agent Journey Scorecard

| Pillar | Score | Status | Description |
|---|:---:|:---:|---|
| **Reach** | `47/100` | At Risk | Crawlability, robots compliance, and indexability without barriers |
| **Read** | `62/100` | At Risk | Clean text and heading extractability without JavaScript traps |
| **Understand** | `17/100` | At Risk | Rich, valid Schema.org structured data and entity identity |
| **Trust** | `92/100` | Optimal | Freshness, provenance, and factual consistency across pages |
| **Navigate** | `92/100` | Optimal | Traversable internal link architecture without dead ends |
| **Act** | `100/100` | Optimal | Clear calls-to-action and machine-discoverable contact channels |
| **Overall Journey** | `68/100` | - | Unweighted average across all 6 pillars |

## Crawl Coverage Summary

- **Pages Discovered**: 931
- **Pages Crawled**: 20 / 20 cap
- **Pages Skipped**: 0
- **Crawl Duration**: 16.2s
- **Robots.txt Status**: `200`
- **JS Rendering**: `disabled`

## Top Priorities

| Rank | Finding ID | Title | Severity | Confidence | Affected Pages | Priority Score | Suggested Action |
|:---:|:---:|---|:---:|:---:|:---:|:---:|---|
| 1 | `F-001` | Important pages lack machine-readable summary metadata (17 page(s)) | `high` | `high` | 9 | `74.2` | Ensure every important page has a descriptive <title> (10-70 chars) and <meta name='description'> (50-160 chars) capturing the page's core value. |
| 2 | `F-002` | Important pages missing agent-actionable structured data (17 page(s)) | `high` | `high` | 9 | `74.2` | Add appropriate Schema.org JSON-LD to important pages: Product/Offer on product pages, Event on event pages, Organization/WebSite on the homepage. Focus on pages with highest importance scores first. |
| 3 | `F-003` | No canonical tags on any crawled page | `high` | `high` | 5 | `56.2` | Add <link rel='canonical'> to every page pointing to its preferred URL. |
| 4 | `F-005` | Missing Organization or WebSite schema on homepage | `high` | `high` | 1 | `41.3` | Add Organization and WebSite JSON-LD to the homepage with name, url, logo, description, and sameAs properties. |
| 5 | `F-006` | Homepage has no H1 heading | `high` | `high` | 1 | `41.3` | Add a single, descriptive H1 to the homepage stating the brand name and value proposition. |

## Agent Answerability

| Question | Status | Confidence | Evidence & Citation |
|---|:---:|:---:|---|
| **What does this company do?** | `Conflicting` | `low` | Contradictory entity identity or company descriptions detected across crawled pages.<br>*Sources: https://curl.se/* |
| **What products/services does it offer?** | `Supported` | `high` | Found 1 product/service page(s): libcurl - What Makes It Special.<br>*Sources: https://curl.se/libcurl/features.html* |
| **Where is it located?** | `Not found` | `low` | No physical address or geographic location declared in JSON-LD or contact text. |
| **What does the product cost?** | `Not found` | `low` | No clear pricing, price tiers, or pricing model mentioned in crawled pages. |
| **How can users contact it?** | `Weakly supported` | `medium` | Contact page detected at https://curl.se/support.html (form or support portal).<br>*Sources: https://curl.se/support.html* |

## Strengths

- **[Discoverability]** No noindex directives on any crawled page
- **[Discoverability]** Homepage returns HTTP 200
- **[Discoverability]** All crawled pages return HTTP 200
- **[Discoverability]** All crawled pages have content without JS rendering
- **[Discoverability]** robots.txt present and permits crawling
- **[Discoverability]** Contact information accessible
- **[Discoverability]** Content appears fresh (recent modification dates on time-sensitive pages)
- **[Discoverability]** All crawled pages have date signals
- **[Engagement]** Homepage has a clear primary call-to-action
- **[Engagement]** Site navigation has descriptive text labels
- **[Engagement]** No dead-end pages found — all pages have onward navigation
- **[Discoverability]** All high-importance pages are reachable from homepage within 3 hops
- **[Discoverability]** All important pages use canonical URL patterns

## Proactive Opportunities

| ID | Title | Category | Priority | Rationale |
|:---:|---|:---:|:---:|---|
| `PRO-001` | Add VideoObject JSON-LD to pages featuring video content | `discoverability` | `medium` | 3 page(s) appear to feature video content based on text signals, but no VideoObject schema was detected. VideoObject markup with transcript or description dramatically increases AI discoverability of multimedia content. |
| `PRO-002` | Add HowTo structured data to guide and tutorial pages | `discoverability` | `medium` | 2 page(s) have headings suggesting step-by-step guides, but no HowTo JSON-LD was found. HowTo schema is among the highest-ROI types for 'how do I' AI assistant queries. |
| `PRO-003` | Complete OpenGraph tags for richer social sharing previews | `engagement` | `low` | 20 of 20 pages (100%) are missing og:title, og:description, or og:image. Complete OpenGraph tags improve how content appears when shared on social media and in AI-powered link previews, driving referral traffic. |

## Detailed Audit Findings

### `F-001`: Important pages lack machine-readable summary metadata (17 page(s))

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `meta-description, page-title, machine-readable, discoverability, crawlability`
- **Evidence**: 17 of 17 important page(s) (importance >= 60) are missing title or meta description. Sample: https://curl.se/ (no title, no meta description); https://curl.se/docs/features.html (no meta description). AI agents use these signals to determine page relevance without full rendering. [Also: crawlability-render-audit: 20 of 20 pages (100%) are missing a <title> and/or <meta name='description'> (including 17 high-importance page(s)).]
- **Affected URLs** (9): https://curl.se/docs/security.html, https://curl.se/docs/releases.html, https://curl.se/docs/, https://curl.se/docs/projdocs.html, https://curl.se/docs/faq.html *(and 4 more)*
- **Suggested Action**: Ensure every important page has a descriptive <title> (10-70 chars) and <meta name='description'> (50-160 chars) capturing the page's core value. *(Priority: high, Effort: low)*

### `F-002`: Important pages missing agent-actionable structured data (17 page(s))

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `json-ld, schema-org, structured-data, discoverability, machine-readable`
- **Evidence**: 17 important page(s) of types that benefit from structured data have no actionable JSON-LD: 16 Documentation, 1 Homepage. Without structured data, AI agents cannot reliably extract offers, schedules, or entity details. [Also: structured-data-content-audit: Crawled 20 pages; 0/20 contain JSON-LD structured data. AI assistants cannot extract machine-readable facts about this site.]
- **Affected URLs** (9): https://curl.se/docs/security.html, https://curl.se/docs/releases.html, https://curl.se/docs/, https://curl.se/docs/projdocs.html, https://curl.se/docs/faq.html *(and 4 more)*
- **Suggested Action**: Add appropriate Schema.org JSON-LD to important pages: Product/Offer on product pages, Event on event pages, Organization/WebSite on the homepage. Focus on pages with highest importance scores first. *(Priority: high, Effort: medium)*

### `F-003`: No canonical tags on any crawled page

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `canonical, crawlability`
- **Evidence**: 0 of 20 crawled pages contain a <link rel='canonical'> tag. Without canonicals, duplicate content dilutes AI citation quality.
- **Affected URLs** (5): https://curl.se/, https://curl.se/support.html, https://curl.se/libcurl/features.html, https://curl.se/docs/features.html, https://curl.se/docs/releases.html
- **Suggested Action**: Add <link rel='canonical'> to every page pointing to its preferred URL. *(Priority: high, Effort: medium)*

### `F-004`: No structured data on 1/1 product/service pages

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `json-ld, schema-org, structured-data`
- **Evidence**: 1 of 1 product/service pages contain no JSON-LD. AI cannot extract product details, prices, or specs.
- **Affected URLs** (1): https://curl.se/libcurl/features.html
- **Suggested Action**: Add Product/Offer/Service JSON-LD to every product and service page. *(Priority: high, Effort: medium)*

### `F-005`: Missing Organization or WebSite schema on homepage

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `json-ld, schema-org, entity-identity`
- **Evidence**: Homepage (https://curl.se/) has no JSON-LD with an Organization, WebSite, or brand entity type. Found types: none. AI assistants cannot reliably identify and describe this brand.
- **Affected URLs** (1): https://curl.se/
- **Suggested Action**: Add Organization and WebSite JSON-LD to the homepage with name, url, logo, description, and sameAs properties. *(Priority: high, Effort: low)*

### `F-006`: Homepage has no H1 heading

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `heading-structure`
- **Evidence**: Homepage (https://curl.se/) has h1: []. No primary topic signal for crawlers.
- **Affected URLs** (1): https://curl.se/
- **Suggested Action**: Add a single, descriptive H1 to the homepage stating the brand name and value proposition. *(Priority: high, Effort: low)*

### `F-007`: No sitemap signal detected — bulk agent discovery may be impaired

- **Severity**: `MEDIUM` | **Confidence**: `medium` | **Category**: `discoverability`
- **Tags**: `discoverability, crawlability, indexability, sitemap`
- **Evidence**: No sitemap.xml reference found in robots.txt, crawl metadata, or any of the 20 crawled pages. AI indexing systems rely on sitemaps for efficient bulk content discovery, especially for sites with many pages.
- **Affected URLs** (1): https://curl.se/
- **Suggested Action**: Consider publishing an XML sitemap at /sitemap.xml and referencing it in robots.txt (Sitemap: https://yourdomain.com/sitemap.xml). Include all important pages with <lastmod> dates. *(Priority: medium, Effort: low)*

### `F-008`: Inconsistent organization identity across key page elements (2 variations)

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `entity-name, entity-identity, identity-drift`
- **Evidence**: Disparate identity signals detected vs canonical 'libcurl': contact_h1 ('Commercial Support'). AI search agents cross-reference title, H1, and JSON-LD to ground entity identity.
- **Affected URLs** (1): https://curl.se/
- **Suggested Action**: Align organization name consistently across Title, H1 headings, and JSON-LD schema. *(Priority: high, Effort: low)*

### `F-009`: Alt text missing on 24/31 images (77%)

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `alt-text`
- **Evidence**: 24 of 31 images across 20 page(s) have empty alt attributes. Image content is invisible to AI crawlers.
- **Affected URLs** (5): https://curl.se/docs/caextract.html, https://curl.se/docs/knownbugs.html, https://curl.se/docs/, https://curl.se/docs/security.html, https://curl.se/docs/releases.html
- **Suggested Action**: Add descriptive alt text to all meaningful images. *(Priority: medium, Effort: medium)*

## Methodology & Limitations

- **Scope**: Evaluates technical AI discoverability, content extractability, structured data completeness, and citation readiness based on an observable crawl snapshot.
- **Scoring Principles**: All scoring formulas and journey deductions are 100% deterministic and rule-grounded, measuring concrete technical readiness rather than subjective or volatile LLM search rankings.
- **Execution Guarantee**: This audit operates purely in read-only analysis mode without modifying site infrastructure, publishing changes, or executing non-idempotent operations.
- **Known Boundaries & Constraints**:
  - Crawl depth is capped at 20 pages per run under standard execution parameters.
  - Dynamic Single-Page Application (SPA) content requires headless rendering with Playwright fallback when JavaScript rendering is enabled.
  - Content behind authentication, paywalls, or strict CAPTCHA barriers is outside audit scope.
