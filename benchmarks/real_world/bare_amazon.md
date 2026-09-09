# Brand AI-Readiness Audit Report: www.amazon.com

## Executive Summary

- **Target URL**: https://www.amazon.com
- **Audited At**: 2026-09-08T19:40:38.163696Z
- **AI Readiness Score**: `0/100`
- **Overall Journey Score**: `57/100`
- **Findings Summary**: 12 total (1 critical, 6 high, 4 medium, 1 low)

## Agent Journey Scorecard

| Pillar | Score | Status | Description |
|---|:---:|:---:|---|
| **Reach** | `29/100` | At Risk | Crawlability, robots compliance, and indexability without barriers |
| **Read** | `84/100` | Attention Needed | Clean text and heading extractability without JavaScript traps |
| **Understand** | `36/100` | At Risk | Rich, valid Schema.org structured data and entity identity |
| **Trust** | `75/100` | Attention Needed | Freshness, provenance, and factual consistency across pages |
| **Navigate** | `59/100` | At Risk | Traversable internal link architecture without dead ends |
| **Act** | `59/100` | At Risk | Clear calls-to-action and machine-discoverable contact channels |
| **Overall Journey** | `57/100` | - | Unweighted average across all 6 pillars |

## Crawl Coverage Summary

- **Pages Discovered**: 2
- **Pages Crawled**: 1 / 5 cap
- **Pages Skipped**: 0
- **Crawl Duration**: 2.9s
- **Robots.txt Status**: `200`
- **JS Rendering**: `disabled`

## Top Priorities

| Rank | Finding ID | Title | Severity | Confidence | Affected Pages | Priority Score | Suggested Action |
|:---:|:---:|---|:---:|:---:|:---:|:---:|---|
| 1 | `F-001` | Homepage returns HTTP 503 | `critical` | `high` | 1 | `48.4` | Fix the server error on the homepage immediately. |
| 2 | `F-003` | High rate of broken internal links (1/1 pages) | `high` | `high` | 1 | `28.9` | Fix or redirect broken URLs. Audit internal links site-wide. |
| 3 | `F-002` | No canonical tags on any crawled page | `high` | `high` | 1 | `27.5` | Add <link rel='canonical'> to every page pointing to its preferred URL. |
| 4 | `F-007` | No date signals found on any crawled page | `high` | `high` | 1 | `27.5` | Add Last-Modified headers and datePublished/dateModified to JSON-LD on all content pages. |
| 5 | `F-004` | No primary call-to-action found on homepage | `high` | `medium` | 1 | `22.0` | Add a prominent primary CTA button above the fold (e.g. 'Get Started', 'Try Free'). |

## Agent Answerability

| Question | Status | Confidence | Evidence & Citation |
|---|:---:|:---:|---|
| **What does this company do?** | `Conflicting` | `low` | Contradictory entity identity or company descriptions detected across crawled pages.<br>*Sources: https://www.amazon.com/* |
| **What products/services does it offer?** | `Not found` | `low` | No dedicated Product or Service pages discovered in snapshot. |
| **Where is it located?** | `Not found` | `low` | No physical address or geographic location declared in JSON-LD or contact text. |
| **What does the product cost?** | `Not found` | `low` | No clear pricing, price tiers, or pricing model mentioned in crawled pages. |
| **How can users contact it?** | `Not found` | `low` | No email, telephone number, or dedicated contact page discovered. |

## Strengths

- **[Discoverability]** No noindex directives on any crawled page
- **[Discoverability]** All crawled pages have content without JS rendering
- **[Discoverability]** robots.txt present and permits crawling
- **[Discoverability]** Contact information accessible
- **[Engagement]** No dead-end pages found — all pages have onward navigation
- **[Discoverability]** All important pages have title and meta description for agent readability

## Proactive Opportunities

| ID | Title | Category | Priority | Rationale |
|:---:|---|:---:|:---:|---|
| `PRO-001` | Complete OpenGraph tags for richer social sharing previews | `engagement` | `low` | 1 of 1 pages (100%) are missing og:title, og:description, or og:image. Complete OpenGraph tags improve how content appears when shared on social media and in AI-powered link previews, driving referral traffic. |

## Detailed Audit Findings

### `F-001`: Homepage returns HTTP 503

- **Severity**: `CRITICAL` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `crawlability, json-ld, schema-org, entity-identity, heading-structure, entity-name, identity-drift`
- **Evidence**: The homepage at https://www.amazon.com/ returned HTTP 503. Crawlers and AI agents cannot retrieve any content. [Also: structured-data-content-audit: Homepage (https://www.amazon.com/) has no JSON-LD with an Organization, WebSite, or brand entity type. Found types: none. AI assistants cannot reliably identify and describe this brand.] [Also: structured-data-content-audit: Homepage (https://www.amazon.com/) has h1: []. No primary topic signal for crawlers.] [Also: entity-identity-audit: Disparate identity signals detected vs canonical 'www': homepage_title ('Amazon.com'). AI search agents cross-reference title, H1, and JSON-LD to ground entity identity.]
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Fix the server error on the homepage immediately. *(Priority: critical, Effort: high)*

### `F-002`: No canonical tags on any crawled page

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `canonical, crawlability`
- **Evidence**: 0 of 1 crawled pages contain a <link rel='canonical'> tag. Without canonicals, duplicate content dilutes AI citation quality.
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Add <link rel='canonical'> to every page pointing to its preferred URL. *(Priority: high, Effort: medium)*

### `F-003`: High rate of broken internal links (1/1 pages)

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `broken-link, crawlability`
- **Evidence**: 1 of 1 crawled pages returned HTTP 4xx/5xx errors (100%).
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Fix or redirect broken URLs. Audit internal links site-wide. *(Priority: high, Effort: medium)*

### `F-004`: No primary call-to-action found on homepage

- **Severity**: `HIGH` | **Confidence**: `medium` | **Category**: `engagement`
- **Tags**: `cta, value-proposition`
- **Evidence**: Homepage (https://www.amazon.com/) has no link text matching CTA patterns. Actual link texts found: ['Conditions of Use', 'Privacy Policy'].
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Add a prominent primary CTA button above the fold (e.g. 'Get Started', 'Try Free'). *(Priority: high, Effort: low)*

### `F-005`: Homepage lacks a clear value proposition

- **Severity**: `HIGH` | **Confidence**: `medium` | **Category**: `engagement`
- **Tags**: `value-proposition`
- **Evidence**: Homepage heading text: 'none'. Visible text sample: 'Click the button below to continue shopping Continue shopping Conditions of Use Privacy Policy © 1996-2025, Amazon.com, Inc. or its affiliates'. No clear statement of who the product/service is for or what it does.
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Add an H1 stating who you help and how; add a sub-headline with one key benefit. *(Priority: high, Effort: low)*

### `F-006`: Navigation has fewer than 3 meaningful text labels

- **Severity**: `HIGH` | **Confidence**: `medium` | **Category**: `engagement`
- **Tags**: `navigation`
- **Evidence**: Homepage has only 2 meaningful internal link text(s): ['Conditions of Use', 'Privacy Policy']. Navigation may be icon-only or unlabelled.
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Add visible text labels to all navigation items; avoid icon-only navigation. *(Priority: high, Effort: medium)*

### `F-007`: No date signals found on any crawled page

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `stale-content, json-ld, schema-org, structured-data`
- **Evidence**: Checked 1 pages: no Last-Modified headers, no datePublished, and no dateModified in any JSON-LD block. AI assistants cannot assess content currency. [Also: structured-data-content-audit: Crawled 1 pages; 0/1 contain JSON-LD structured data. AI assistants cannot extract machine-readable facts about this site.]
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Add Last-Modified headers and datePublished/dateModified to JSON-LD on all content pages. *(Priority: high, Effort: medium)*

### `F-008`: Missing title or meta description on 1/1 pages

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `page-title, meta-description, crawlability`
- **Evidence**: 1 of 1 pages (100%) are missing a <title> and/or <meta name='description'>.
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Add unique, descriptive title tags and meta descriptions to every page. *(Priority: medium, Effort: medium)*

### `F-009`: Thin content on 1/1 pages (<200 characters)

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `thin-content, crawlability`
- **Evidence**: 1 of 1 pages (100%) have fewer than 200 visible characters. AI assistants have little content to cite.
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Expand thin pages with substantive content or consolidate them. *(Priority: medium, Effort: high)*

### `F-010`: No About or team page detected

- **Severity**: `MEDIUM` | **Confidence**: `medium` | **Category**: `engagement`
- **Tags**: `about-page, navigation, value-proposition, entity-identity, entity-disambiguation`
- **Evidence**: None of 1 crawled URLs match about/team page patterns, and no title contains 'About' or 'Our Team'. First-time visitors cannot learn who is behind the site. [Also: entity-identity-audit: None of 1 crawled URLs match about-page patterns (/about, /who-we-are, /our-story, ...) and no page title contains 'About'.]
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Create an About page introducing the team/company and mission. *(Priority: medium, Effort: medium)*

### `F-011`: Brand name 'www' may be ambiguous or generic

- **Severity**: `MEDIUM` | **Confidence**: `low` | **Category**: `discoverability`
- **Tags**: `entity-disambiguation, entity-name`
- **Evidence**: Detected brand name 'www' is short (3 chars) or uses only common words, creating disambiguation risk for AI agents.
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Add disambiguatingDescription and sameAs to Organisation JSON-LD; use full legal name. *(Priority: high, Effort: low)*

### `F-012`: No contact or support link found across any crawled page

- **Severity**: `LOW` | **Confidence**: `medium` | **Category**: `engagement`
- **Tags**: `contact-page, navigation, cta`
- **Evidence**: No link text across 1 crawled pages matches contact/support patterns (contact, support, help, chat, ...).
- **Affected URLs** (1): https://www.amazon.com/
- **Suggested Action**: Add a 'Contact' or 'Support' link to the site header or footer. *(Priority: low, Effort: low)*

## Methodology & Limitations

- **Scope**: Evaluates technical AI discoverability, content extractability, structured data completeness, and citation readiness based on an observable crawl snapshot.
- **Scoring Principles**: All scoring formulas and journey deductions are 100% deterministic and rule-grounded, measuring concrete technical readiness rather than subjective or volatile LLM search rankings.
- **Execution Guarantee**: This audit operates purely in read-only analysis mode without modifying site infrastructure, publishing changes, or executing non-idempotent operations.
- **Known Boundaries & Constraints**:
  - Crawl depth is capped at 20 pages per run under standard execution parameters.
  - Dynamic Single-Page Application (SPA) content requires headless rendering with Playwright fallback when JavaScript rendering is enabled.
  - Content behind authentication, paywalls, or strict CAPTCHA barriers is outside audit scope.
