# Brand AI-Readiness Audit Report: benchmark-acme.internal

## Executive Summary

- **Target URL**: https://benchmark-acme.internal/
- **Audited At**: 2026-09-08T18:27:08.773732Z
- **AI Readiness Score**: `68/100`
- **Overall Journey Score**: `88/100`
- **Findings Summary**: 5 total (0 critical, 2 high, 3 medium, 0 low)

## Agent Journey Scorecard

| Pillar | Score | Status | Description |
|---|:---:|:---:|---|
| **Reach** | `92/100` | Optimal | Crawlability, robots compliance, and indexability without barriers |
| **Read** | `100/100` | Optimal | Clean text and heading extractability without JavaScript traps |
| **Understand** | `69/100` | At Risk | Rich, valid Schema.org structured data and entity identity |
| **Trust** | `77/100` | Attention Needed | Freshness, provenance, and factual consistency across pages |
| **Navigate** | `92/100` | Optimal | Traversable internal link architecture without dead ends |
| **Act** | `100/100` | Optimal | Clear calls-to-action and machine-discoverable contact channels |
| **Overall Journey** | `88/100` | - | Unweighted average across all 6 pillars |

## Crawl Coverage Summary

- **Pages Discovered**: 50
- **Pages Crawled**: 50 / 20 cap
- **Pages Skipped**: 0
- **Crawl Duration**: 0.0s
- **Robots.txt Status**: `200`
- **JS Rendering**: `disabled`

## Top Priorities

| Rank | Finding ID | Title | Severity | Confidence | Affected Pages | Priority Score | Suggested Action |
|:---:|:---:|---|:---:|:---:|:---:|:---:|---|
| 1 | `F-001` | Conflicting pricing information detected across 11 crawled pages | `high` | `high` | 5 | `46.9` | Reconcile product pricing across product pages, pricing tables, and structured data. |
| 2 | `F-002` | No structured data on 3/29 product/service pages | `high` | `high` | 3 | `40.6` | Add Product/Offer/Service JSON-LD to every product and service page. |
| 3 | `F-005` | Semantic contradiction between Schema.org and visible headings on 15 page(s) | `medium` | `high` | 5 | `19.7` | Ensure Schema.org entity names and headlines correspond to the actual on-page title and headings. |
| 4 | `F-004` | Article JSON-LD missing datePublished/dateModified on 1 page(s) | `medium` | `high` | 1 | `13.8` | Add datePublished and dateModified to all Article JSON-LD blocks. |
| 5 | `F-003` | No sitemap signal detected — bulk agent discovery may be impaired | `medium` | `medium` | 1 | `11.6` | Consider publishing an XML sitemap at /sitemap.xml and referencing it in robots.txt (Sitemap: https://yourdomain.com/sitemap.xml). Include all important pages with <lastmod> dates. |

## Agent Answerability

| Question | Status | Confidence | Evidence & Citation |
|---|:---:|:---:|---|
| **What does this company do?** | `Conflicting` | `low` | Contradictory entity identity or company descriptions detected across crawled pages.<br>*Sources: https://benchmark-acme.internal/, https://benchmark-acme.internal/about* |
| **What products/services does it offer?** | `Supported` | `high` | Found 29 product/service page(s): Transparent Enterprise Pricing & Subscription Plans | Acme Global, Enterprise Solution 2 | Acme Global.<br>*Sources: https://benchmark-acme.internal/pricing, https://benchmark-acme.internal/solutions/enterprise-solution-2, https://benchmark-acme.internal/products/product-suite-3* |
| **Where is it located?** | `Not found` | `low` | No physical address or geographic location declared in JSON-LD or contact text. |
| **What does the product cost?** | `Conflicting` | `low` | Conflicting pricing found between visible content and structured data.<br>*Sources: https://benchmark-acme.internal/pricing, https://benchmark-acme.internal/products/product-suite-3* |
| **How can users contact it?** | `Weakly supported` | `medium` | Contact page detected at https://benchmark-acme.internal/contact (form or support portal).<br>*Sources: https://benchmark-acme.internal/contact* |

## Strengths

- **[Discoverability]** No noindex directives on any crawled page
- **[Discoverability]** Homepage returns HTTP 200
- **[Discoverability]** Consistent canonical tags across all crawled pages
- **[Discoverability]** All crawled pages return HTTP 200
- **[Discoverability]** All crawled pages have content without JS rendering
- **[Discoverability]** robots.txt present and permits crawling
- **[Discoverability]** Homepage has Organization/WebSite schema (Organization, WebSite)
- **[Discoverability]** All images have alt text across crawled pages
- **[Discoverability]** Brand name declared in Organization JSON-LD
- **[Discoverability]** About page present for entity context
- **[Discoverability]** Contact information accessible
- **[Discoverability]** sameAs links in Organization schema support entity corroboration
- **[Discoverability]** Entity identity strongly corroborated (High confidence: 100%)
- **[Discoverability]** Content appears fresh (recent modification dates on time-sensitive pages)
- **[Discoverability]** All crawled pages have date signals
- **[Engagement]** Homepage has a clear primary call-to-action
- **[Engagement]** Site navigation has descriptive text labels
- **[Engagement]** No dead-end pages found — all pages have onward navigation
- **[Discoverability]** All important pages have title and meta description for agent readability

## Proactive Opportunities

| ID | Title | Category | Priority | Rationale |
|:---:|---|:---:|:---:|---|
| `PRO-001` | Add HowTo structured data to guide and tutorial pages | `discoverability` | `medium` | 1 page(s) have headings suggesting step-by-step guides, but no HowTo JSON-LD was found. HowTo schema is among the highest-ROI types for 'how do I' AI assistant queries. |
| `PRO-002` | Add expertise fields to author Person JSON-LD (jobTitle, knowsAbout) | `discoverability` | `medium` | The site has 15 article/blog page(s) with author attribution, but no Person JSON-LD includes expertise fields (jobTitle, knowsAbout, alumniOf). AI agents use these to assess content authority and E-E-A-T signals. |

## Detailed Audit Findings

### `F-001`: Conflicting pricing information detected across 11 crawled pages

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `pricing, corroboration, contradiction`
- **Evidence**: Contradicting price figures discovered: https://benchmark-acme.internal/products/product-suite-3 declares $129.0 while https://benchmark-acme.internal/products/product-suite-6 declares $159.0 for 'Acme Product Suite 3'. Discrepancies in published pricing confuse AI assistants and undermine transactional trust.
- **Affected URLs** (5): https://benchmark-acme.internal/products/product-suite-3, https://benchmark-acme.internal/products/product-suite-30, https://benchmark-acme.internal/products/product-suite-21, https://benchmark-acme.internal/products/product-suite-42, https://benchmark-acme.internal/products/product-suite-33
- **Suggested Action**: Reconcile product pricing across product pages, pricing tables, and structured data. *(Priority: high, Effort: low)*

### `F-002`: No structured data on 3/29 product/service pages

- **Severity**: `HIGH` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `json-ld, schema-org, structured-data`
- **Evidence**: 3 of 29 product/service pages contain no JSON-LD. AI cannot extract product details, prices, or specs.
- **Affected URLs** (3): https://benchmark-acme.internal/products/product-suite-12, https://benchmark-acme.internal/products/product-suite-24, https://benchmark-acme.internal/products/product-suite-36
- **Suggested Action**: Add Product/Offer/Service JSON-LD to every product and service page. *(Priority: high, Effort: medium)*

### `F-003`: No sitemap signal detected — bulk agent discovery may be impaired

- **Severity**: `MEDIUM` | **Confidence**: `medium` | **Category**: `discoverability`
- **Tags**: `discoverability, crawlability, indexability, sitemap`
- **Evidence**: No sitemap.xml reference found in robots.txt, crawl metadata, or any of the 50 crawled pages. AI indexing systems rely on sitemaps for efficient bulk content discovery, especially for sites with many pages.
- **Affected URLs** (1): https://benchmark-acme.internal/
- **Suggested Action**: Consider publishing an XML sitemap at /sitemap.xml and referencing it in robots.txt (Sitemap: https://yourdomain.com/sitemap.xml). Include all important pages with <lastmod> dates. *(Priority: medium, Effort: low)*

### `F-004`: Article JSON-LD missing datePublished/dateModified on 1 page(s)

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `stale-content, schema-org`
- **Evidence**: 1 page(s) have Article/BlogPosting JSON-LD but no datePublished or dateModified. AI cannot assess content currency.
- **Affected URLs** (1): https://benchmark-acme.internal/docs
- **Suggested Action**: Add datePublished and dateModified to all Article JSON-LD blocks. *(Priority: medium, Effort: low)*

### `F-005`: Semantic contradiction between Schema.org and visible headings on 15 page(s)

- **Severity**: `MEDIUM` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `schema-org, trust, contradiction, structured-data`
- **Evidence**: Declared Schema.org entity name/headline contradicts visible page headings: Page https://benchmark-acme.internal/blog/ai-trends-article-1 declares schema entity 'Jane Doe' while visible heading is 'AI Trends and Best Practices Part 1'. Contradictory entity facts cause AI models to discount site reliability.
- **Affected URLs** (5): https://benchmark-acme.internal/blog/ai-trends-article-1, https://benchmark-acme.internal/blog/ai-trends-article-4, https://benchmark-acme.internal/blog/ai-trends-article-7, https://benchmark-acme.internal/blog/ai-trends-article-10, https://benchmark-acme.internal/blog/ai-trends-article-13
- **Suggested Action**: Ensure Schema.org entity names and headlines correspond to the actual on-page title and headings. *(Priority: medium, Effort: low)*

## Methodology & Limitations

- **Scope**: Evaluates technical AI discoverability, content extractability, structured data completeness, and citation readiness based on an observable crawl snapshot.
- **Scoring Principles**: All scoring formulas and journey deductions are 100% deterministic and rule-grounded, measuring concrete technical readiness rather than subjective or volatile LLM search rankings.
- **Execution Guarantee**: This audit operates purely in read-only analysis mode without modifying site infrastructure, publishing changes, or executing non-idempotent operations.
- **Known Boundaries & Constraints**:
  - Crawl depth is capped at 20 pages per run under standard execution parameters.
  - Dynamic Single-Page Application (SPA) content requires headless rendering with Playwright fallback when JavaScript rendering is enabled.
  - Content behind authentication, paywalls, or strict CAPTCHA barriers is outside audit scope.
