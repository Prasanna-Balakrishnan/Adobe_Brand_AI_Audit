# Brand AI-Readiness Audit Report: www.curl.com

## Executive Summary

- **Target URL**: https://www.curl.com
- **Audited At**: 2026-09-08T19:40:17.015649Z
- **AI Readiness Score**: `49/100`
- **Overall Journey Score**: `73/100`
- **Findings Summary**: 6 total (1 critical, 1 high, 4 medium, 0 low)

## Agent Journey Scorecard

| Pillar | Score | Status | Description |
|---|:---:|:---:|---|
| **Reach** | `60/100` | At Risk | Crawlability, robots compliance, and indexability without barriers |
| **Read** | `67/100` | At Risk | Clean text and heading extractability without JavaScript traps |
| **Understand** | `51/100` | At Risk | Rich, valid Schema.org structured data and entity identity |
| **Trust** | `92/100` | Optimal | Freshness, provenance, and factual consistency across pages |
| **Navigate** | `67/100` | At Risk | Traversable internal link architecture without dead ends |
| **Act** | `100/100` | Optimal | Clear calls-to-action and machine-discoverable contact channels |
| **Overall Journey** | `73/100` | - | Unweighted average across all 6 pillars |

## Crawl Coverage Summary

- **Pages Discovered**: 56
- **Pages Crawled**: 5 / 5 cap
- **Pages Skipped**: 41
- **Crawl Duration**: 20.9s
- **Robots.txt Status**: `200`
- **JS Rendering**: `disabled`

## Top Priorities

| Rank | Finding ID | Title | Severity | Confidence | Affected Pages | Priority Score | Suggested Action |
|:---:|:---:|---|:---:|:---:|:---:|:---:|---|
| 1 | `F-001` | noindex directive on primary brand/orientation page (Homepage) | `critical` | `high` | 5 | `100.0` | Remove noindex headers and meta tags from primary brand and orientation pages. |
| 2 | `F-002` | No canonical tags on any crawled page | `high` | `high` | 5 | `56.2` | Add <link rel='canonical'> to every page pointing to its preferred URL. |
| 3 | `F-006` | Duplicate page titles detected across 2 crawled pages | `medium` | `high` | 2 | `17.6` | Provide unique, topic-specific <title> tags for each distinct URL. |
| 4 | `F-004` | Inconsistent organization identity across key page elements (2 variations) | `medium` | `high` | 1 | `17.3` | Align organization name consistently across Title, H1 headings, and JSON-LD schema. |
| 5 | `F-005` | Missing H1 heading on 1 core content page(s) | `medium` | `high` | 1 | `15.4` | Add a descriptive <h1> heading identifying the core topic or entity on each content page. |

## Agent Answerability

| Question | Status | Confidence | Evidence & Citation |
|---|:---:|:---:|---|
| **What does this company do?** | `Conflicting` | `low` | Contradictory entity identity or company descriptions detected across crawled pages.<br>*Sources: https://www.curl.com/, https://www.curl.com/company/* |
| **What products/services does it offer?** | `Not found` | `low` | No dedicated Product or Service pages discovered in snapshot. |
| **Where is it located?** | `Not found` | `low` | No physical address or geographic location declared in JSON-LD or contact text. |
| **What does the product cost?** | `Not found` | `low` | No clear pricing, price tiers, or pricing model mentioned in crawled pages. |
| **How can users contact it?** | `Weakly supported` | `medium` | Contact page detected at https://www.curl.com/support/ (form or support portal).<br>*Sources: https://www.curl.com/support/* |

## Strengths

- **[Discoverability]** Homepage returns HTTP 200
- **[Discoverability]** All crawled pages return HTTP 200
- **[Discoverability]** All crawled pages have content without JS rendering
- **[Discoverability]** About page present for entity context
- **[Discoverability]** Contact information accessible
- **[Engagement]** Homepage has a clear primary call-to-action
- **[Engagement]** Site navigation has descriptive text labels
- **[Engagement]** No dead-end pages found — all pages have onward navigation
- **[Discoverability]** All important pages have title and meta description for agent readability
- **[Discoverability]** Sitemap signal detected — bulk agent discovery is supported
- **[Discoverability]** All important pages use canonical URL patterns

## Proactive Opportunities

| ID | Title | Category | Priority | Rationale |
|:---:|---|:---:|:---:|---|
| `PRO-001` | Add VideoObject JSON-LD to pages featuring video content | `discoverability` | `medium` | 5 page(s) appear to feature video content based on text signals, but no VideoObject schema was detected. VideoObject markup with transcript or description dramatically increases AI discoverability of multimedia content. |
| `PRO-002` | Complete OpenGraph tags for richer social sharing previews | `engagement` | `low` | 4 of 5 pages (80%) are missing og:title, og:description, or og:image. Complete OpenGraph tags improve how content appears when shared on social media and in AI-powered link previews, driving referral traffic. |

## Detailed Audit Findings

### `F-001`: noindex directive on primary brand/orientation page (Homepage)

- **Severity**: `CRITICAL` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `noindex, indexability, crawlability, json-ld, schema-org, structured-data, discoverability, machine-readable, stale-content, entity-identity, heading-structure, meta-description, duplicate-content, seo-hygiene`
- **Evidence**: 1 key orientation page(s) specify 'noindex' in meta_robots or X-Robots-Tag: https://www.curl.com/ (Homepage). AI search engines will exclude these foundational brand pages from search indexes. [Also: agent-discoverability-audit: 1 important page(s) of types that benefit from structured data have no actionable JSON-LD: 1 Homepage. Without structured data, AI agents cannot reliably extract offers, schedules, or entity details.] [Also: freshness-corroboration-audit: Checked 5 pages: no Last-Modified headers, no datePublished, and no dateModified in any JSON-LD block. AI assistants cannot assess content currency.] [Also: structured-data-content-audit: Crawled 5 pages; 0/5 contain JSON-LD structured data. AI assistants cannot extract machine-readable facts about this site.] [Also: structured-data-content-audit: Homepage (https://www.curl.com/) has no JSON-LD with an Organization, WebSite, or brand entity type. Found types: none. AI assistants cannot reliably identify and describe this brand.] [Also: structured-data-content-audit: Homepage (https://www.curl.com/) has h1: []. No primary topic signal for crawlers.] [Also: structured-data-content-audit: Identical meta description is shared across 5 pages (https://www.curl.com/, https://www.curl.com/company/, https://www.curl.com/support/). Duplicate descriptions degrade search snippet distinctiveness] [Also: structured-data-content-audit: Identical meta description is shared across 5 pages (https://www.curl.com/, https://www.curl.com/company/, https://www.curl.com/support/). Duplicate descriptions degrade search snippet distinctiveness]
- **Affected URLs** (5): https://www.curl.com/, https://www.curl.com/company/, https://www.curl.com/contact/, https://www.curl.com/support/, https://www.curl.com/support/cve-info.html
- **Suggested Action**: Remove noindex headers and meta tags from primary brand and orientation pages. *(Priority: critical, Effort: low)*

### `F-002`: No canonical tags on any crawled page

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `canonical, crawlability`
- **Evidence**: 0 of 5 crawled pages contain a <link rel='canonical'> tag. Without canonicals, duplicate content dilutes AI citation quality.
- **Affected URLs** (5): https://www.curl.com/, https://www.curl.com/company/, https://www.curl.com/contact/, https://www.curl.com/support/, https://www.curl.com/support/cve-info.html
- **Suggested Action**: Add <link rel='canonical'> to every page pointing to its preferred URL. *(Priority: high, Effort: medium)*

### `F-003`: Core orientation page(s) isolated from homepage navigation (1 page(s))

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `engagement`
- **Tags**: `navigation, internal-linking`
- **Evidence**: 1 orientation page(s) exist in the site crawl but are not directly linked from the homepage: https://www.curl.com/support/cve-info.html (Contact). Key brand identity and contactability pages should be reachable from top-level site navigation.
- **Affected URLs** (1): https://www.curl.com/support/cve-info.html
- **Suggested Action**: Add clear header or footer navigation links on the homepage to all core orientation pages. *(Priority: medium, Effort: low)*

### `F-004`: Inconsistent organization identity across key page elements (2 variations)

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `entity-name, entity-identity, identity-drift`
- **Evidence**: Disparate identity signals detected vs canonical 'Contact': homepage_title ('Curl'). AI search agents cross-reference title, H1, and JSON-LD to ground entity identity.
- **Affected URLs** (1): https://www.curl.com/
- **Suggested Action**: Align organization name consistently across Title, H1 headings, and JSON-LD schema. *(Priority: high, Effort: low)*

### `F-005`: Missing H1 heading on 1 core content page(s)

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `heading-structure, h1-tag`
- **Evidence**: 1 content page(s) lack an <h1> heading: https://www.curl.com/company/ (type: About). The H1 heading is the primary topic signal for AI content extraction.
- **Affected URLs** (1): https://www.curl.com/company/
- **Suggested Action**: Add a descriptive <h1> heading identifying the core topic or entity on each content page. *(Priority: medium, Effort: low)*

### `F-006`: Duplicate page titles detected across 2 crawled pages

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `page-title, duplicate-content, seo-hygiene`
- **Evidence**: Identical title 'Curl - Download [SCSK Corporation]' is shared across 2 distinct pages (https://www.curl.com/support/, https://www.curl.com/support/cve-info.html). Duplicate title tags confuse search engines and AI agents when determining the authoritative page for a query.
- **Affected URLs** (2): https://www.curl.com/support/, https://www.curl.com/support/cve-info.html
- **Suggested Action**: Provide unique, topic-specific <title> tags for each distinct URL. *(Priority: medium, Effort: low)*

## Methodology & Limitations

- **Scope**: Evaluates technical AI discoverability, content extractability, structured data completeness, and citation readiness based on an observable crawl snapshot.
- **Scoring Principles**: All scoring formulas and journey deductions are 100% deterministic and rule-grounded, measuring concrete technical readiness rather than subjective or volatile LLM search rankings.
- **Execution Guarantee**: This audit operates purely in read-only analysis mode without modifying site infrastructure, publishing changes, or executing non-idempotent operations.
- **Known Boundaries & Constraints**:
  - Crawl depth is capped at 20 pages per run under standard execution parameters.
  - Dynamic Single-Page Application (SPA) content requires headless rendering with Playwright fallback when JavaScript rendering is enabled.
  - Content behind authentication, paywalls, or strict CAPTCHA barriers is outside audit scope.
