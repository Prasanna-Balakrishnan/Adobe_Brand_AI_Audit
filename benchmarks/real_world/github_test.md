# Brand AI-Readiness Audit Report: github

## Executive Summary

- **Target URL**: https://github
- **Audited At**: 2026-09-08T19:07:38.480216Z
- **AI Readiness Score**: `8/100`
- **Overall Journey Score**: `64/100`
- **Findings Summary**: 11 total (0 critical, 8 high, 3 medium, 0 low)

## Agent Journey Scorecard

| Pillar | Score | Status | Description |
|---|:---:|:---:|---|
| **Reach** | `69/100` | At Risk | Crawlability, robots compliance, and indexability without barriers |
| **Read** | `84/100` | Attention Needed | Clean text and heading extractability without JavaScript traps |
| **Understand** | `24/100` | At Risk | Rich, valid Schema.org structured data and entity identity |
| **Trust** | `100/100` | Optimal | Freshness, provenance, and factual consistency across pages |
| **Navigate** | `62/100` | At Risk | Traversable internal link architecture without dead ends |
| **Act** | `47/100` | At Risk | Clear calls-to-action and machine-discoverable contact channels |
| **Overall Journey** | `64/100` | - | Unweighted average across all 6 pillars |

## Crawl Coverage Summary

- **Pages Discovered**: 2
- **Pages Crawled**: 1 / 5 cap
- **Pages Skipped**: 0
- **Crawl Duration**: 10.6s
- **Robots.txt Status**: `0`
- **JS Rendering**: `disabled`

## Top Priorities

| Rank | Finding ID | Title | Severity | Confidence | Affected Pages | Priority Score | Suggested Action |
|:---:|:---:|---|:---:|:---:|:---:|:---:|---|
| 1 | `F-001` | No canonical tags on any crawled page | `high` | `high` | 1 | `20.6` | Add <link rel='canonical'> to every page pointing to its preferred URL. |
| 2 | `F-006` | No date signals found on any crawled page | `high` | `high` | 1 | `20.6` | Add Last-Modified headers and datePublished/dateModified to JSON-LD on all content pages. |
| 3 | `F-007` | Missing Organization or WebSite schema on homepage | `high` | `high` | 1 | `20.6` | Add Organization and WebSite JSON-LD to the homepage with name, url, logo, description, and sameAs properties. |
| 4 | `F-008` | Homepage has no H1 heading | `high` | `high` | 1 | `20.6` | Add a single, descriptive H1 to the homepage stating the brand name and value proposition. |
| 5 | `F-005` | No contact page or contact information found | `high` | `medium` | 1 | `18.2` | Add a Contact page with email, phone, and/or address. |

## Agent Answerability

| Question | Status | Confidence | Evidence & Citation |
|---|:---:|:---:|---|
| **What does this company do?** | `Not found` | `low` | No clear company summary or description found across crawled pages. |
| **What products/services does it offer?** | `Not found` | `low` | No dedicated Product or Service pages discovered in snapshot. |
| **Where is it located?** | `Not found` | `low` | No physical address or geographic location declared in JSON-LD or contact text. |
| **What does the product cost?** | `Not found` | `low` | No clear pricing, price tiers, or pricing model mentioned in crawled pages. |
| **How can users contact it?** | `Not found` | `low` | No email, telephone number, or dedicated contact page discovered. |

## Strengths

- **[Discoverability]** No noindex directives on any crawled page
- **[Discoverability]** All crawled pages return HTTP 200
- **[Discoverability]** All crawled pages have content without JS rendering
- **[Engagement]** No dead-end pages found — all pages have onward navigation
- **[Discoverability]** All important pages have title and meta description for agent readability

## Proactive Opportunities

| ID | Title | Category | Priority | Rationale |
|:---:|---|:---:|:---:|---|
| `PRO-001` | Complete OpenGraph tags for richer social sharing previews | `engagement` | `low` | 1 of 1 pages (100%) are missing og:title, og:description, or og:image. Complete OpenGraph tags improve how content appears when shared on social media and in AI-powered link previews, driving referral traffic. |

## Detailed Audit Findings

### `F-001`: No canonical tags on any crawled page

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `canonical, crawlability`
- **Evidence**: 0 of 1 crawled pages contain a <link rel='canonical'> tag. Without canonicals, duplicate content dilutes AI citation quality.
- **Affected URLs** (1): https://github/
- **Suggested Action**: Add <link rel='canonical'> to every page pointing to its preferred URL. *(Priority: high, Effort: medium)*

### `F-002`: No primary call-to-action found on homepage

- **Severity**: `HIGH` | **Confidence**: `medium` | **Category**: `engagement`
- **Tags**: `cta, value-proposition`
- **Evidence**: Homepage (https://github/) has no link text matching CTA patterns. Actual link texts found: [].
- **Affected URLs** (1): https://github/
- **Suggested Action**: Add a prominent primary CTA button above the fold (e.g. 'Get Started', 'Try Free'). *(Priority: high, Effort: low)*

### `F-003`: Homepage lacks a clear value proposition

- **Severity**: `HIGH` | **Confidence**: `medium` | **Category**: `engagement`
- **Tags**: `value-proposition`
- **Evidence**: Homepage heading text: 'none'. Visible text sample: 'empty'. No clear statement of who the product/service is for or what it does.
- **Affected URLs** (1): https://github/
- **Suggested Action**: Add an H1 stating who you help and how; add a sub-headline with one key benefit. *(Priority: high, Effort: low)*

### `F-004`: Navigation has fewer than 3 meaningful text labels

- **Severity**: `HIGH` | **Confidence**: `medium` | **Category**: `engagement`
- **Tags**: `navigation`
- **Evidence**: Homepage has only 0 meaningful internal link text(s): []. Navigation may be icon-only or unlabelled.
- **Affected URLs** (1): https://github/
- **Suggested Action**: Add visible text labels to all navigation items; avoid icon-only navigation. *(Priority: high, Effort: medium)*

### `F-005`: No contact page or contact information found

- **Severity**: `HIGH` | **Confidence**: `medium` | **Category**: `discoverability`
- **Tags**: `contact-page, entity-identity, navigation, cta`
- **Evidence**: No URL matches contact-page patterns and no email, phone, or address detected in visible text samples across 1 crawled pages. [Also: engagement-audit: No link text across 1 crawled pages matches contact/support patterns (contact, support, help, chat, ...).]
- **Affected URLs** (1): https://github/
- **Suggested Action**: Add a Contact page with email, phone, and/or address. *(Priority: high, Effort: low)*

### `F-006`: No date signals found on any crawled page

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `stale-content, json-ld, schema-org, structured-data`
- **Evidence**: Checked 1 pages: no Last-Modified headers, no datePublished, and no dateModified in any JSON-LD block. AI assistants cannot assess content currency. [Also: structured-data-content-audit: Crawled 1 pages; 0/1 contain JSON-LD structured data. AI assistants cannot extract machine-readable facts about this site.]
- **Affected URLs** (1): https://github/
- **Suggested Action**: Add Last-Modified headers and datePublished/dateModified to JSON-LD on all content pages. *(Priority: high, Effort: medium)*

### `F-007`: Missing Organization or WebSite schema on homepage

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `json-ld, schema-org, entity-identity`
- **Evidence**: Homepage (https://github/) has no JSON-LD with an Organization, WebSite, or brand entity type. Found types: none. AI assistants cannot reliably identify and describe this brand.
- **Affected URLs** (1): https://github/
- **Suggested Action**: Add Organization and WebSite JSON-LD to the homepage with name, url, logo, description, and sameAs properties. *(Priority: high, Effort: low)*

### `F-008`: Homepage has no H1 heading

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `heading-structure`
- **Evidence**: Homepage (https://github/) has h1: []. No primary topic signal for crawlers.
- **Affected URLs** (1): https://github/
- **Suggested Action**: Add a single, descriptive H1 to the homepage stating the brand name and value proposition. *(Priority: high, Effort: low)*

### `F-009`: Missing title or meta description on 1/1 pages

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `page-title, meta-description, crawlability, seo-hygiene`
- **Evidence**: 1 of 1 pages (100%) are missing a <title> and/or <meta name='description'>. [Also: crawlability-render-audit: 1 page(s) declare an empty or whitespace-only <title> tag (e.g. https://github/). Empty titles prevent search engines and AI crawlers from indexing page identity and relevance.] [Also: structured-data-content-audit: 1 pages have titles shorter than 10 characters or empty. Examples: [''].]
- **Affected URLs** (1): https://github/
- **Suggested Action**: Add unique, descriptive title tags and meta descriptions to every page. *(Priority: medium, Effort: medium)*

### `F-010`: Thin content on 1/1 pages (<200 characters)

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `thin-content, crawlability`
- **Evidence**: 1 of 1 pages (100%) have fewer than 200 visible characters. AI assistants have little content to cite.
- **Affected URLs** (1): https://github/
- **Suggested Action**: Expand thin pages with substantive content or consolidate them. *(Priority: medium, Effort: high)*

### `F-011`: No About or team page detected

- **Severity**: `MEDIUM` | **Confidence**: `medium` | **Category**: `engagement`
- **Tags**: `about-page, navigation, value-proposition, entity-identity, entity-disambiguation`
- **Evidence**: None of 1 crawled URLs match about/team page patterns, and no title contains 'About' or 'Our Team'. First-time visitors cannot learn who is behind the site. [Also: entity-identity-audit: None of 1 crawled URLs match about-page patterns (/about, /who-we-are, /our-story, ...) and no page title contains 'About'.]
- **Affected URLs** (1): https://github/
- **Suggested Action**: Create an About page introducing the team/company and mission. *(Priority: medium, Effort: medium)*

## Methodology & Limitations

- **Scope**: Evaluates technical AI discoverability, content extractability, structured data completeness, and citation readiness based on an observable crawl snapshot.
- **Scoring Principles**: All scoring formulas and journey deductions are 100% deterministic and rule-grounded, measuring concrete technical readiness rather than subjective or volatile LLM search rankings.
- **Execution Guarantee**: This audit operates purely in read-only analysis mode without modifying site infrastructure, publishing changes, or executing non-idempotent operations.
- **Known Boundaries & Constraints**:
  - Crawl depth is capped at 20 pages per run under standard execution parameters.
  - Dynamic Single-Page Application (SPA) content requires headless rendering with Playwright fallback when JavaScript rendering is enabled.
  - Content behind authentication, paywalls, or strict CAPTCHA barriers is outside audit scope.
