# Brand AI-Readiness Audit Report: books.toscrape.com

## Executive Summary

- **Target URL**: https://books.toscrape.com
- **Audited At**: 2026-09-08T19:02:51.663502Z
- **AI Readiness Score**: `75/100`
- **Overall Journey Score**: `96/100`
- **Findings Summary**: 1 total (1 critical, 0 high, 0 medium, 0 low)

## Agent Journey Scorecard

| Pillar | Score | Status | Description |
|---|:---:|:---:|---|
| **Reach** | `75/100` | Attention Needed | Crawlability, robots compliance, and indexability without barriers |
| **Read** | `100/100` | Optimal | Clean text and heading extractability without JavaScript traps |
| **Understand** | `100/100` | Optimal | Rich, valid Schema.org structured data and entity identity |
| **Trust** | `100/100` | Optimal | Freshness, provenance, and factual consistency across pages |
| **Navigate** | `100/100` | Optimal | Traversable internal link architecture without dead ends |
| **Act** | `100/100` | Optimal | Clear calls-to-action and machine-discoverable contact channels |
| **Overall Journey** | `96/100` | - | Unweighted average across all 6 pillars |

## Crawl Coverage Summary

- **Pages Discovered**: 1
- **Pages Crawled**: 0 / 20 cap
- **Pages Skipped**: 0
- **Crawl Duration**: 3.8s
- **Robots.txt Status**: `404`
- **JS Rendering**: `disabled`

## Top Priorities

| Rank | Finding ID | Title | Severity | Confidence | Affected Pages | Priority Score | Suggested Action |
|:---:|:---:|---|:---:|:---:|:---:|:---:|---|
| 1 | `F-001` | Homepage failed to load — no pages crawled | `critical` | `high` | 1 | `44.0` | Verify the site is accessible and the URL is correct. |

## Agent Answerability

| Question | Status | Confidence | Evidence & Citation |
|---|:---:|:---:|---|
| **What does this company do?** | `Not found` | `low` | No clear company summary or description found across crawled pages. |
| **What products/services does it offer?** | `Not found` | `low` | No dedicated Product or Service pages discovered in snapshot. |
| **Where is it located?** | `Not found` | `low` | No physical address or geographic location declared in JSON-LD or contact text. |
| **What does the product cost?** | `Not found` | `low` | No clear pricing, price tiers, or pricing model mentioned in crawled pages. |
| **How can users contact it?** | `Not found` | `low` | No email, telephone number, or dedicated contact page discovered. |

## Strengths

No explicit strength signals detected.

## Proactive Opportunities

No proactive recommendations recorded.

## Detailed Audit Findings

### `F-001`: Homepage failed to load — no pages crawled

- **Severity**: `CRITICAL` | **Confidence**: `high` | **Category**: `discoverability`
- **Tags**: `crawlability`
- **Evidence**: The crawler returned 0 pages. The start URL may be unreachable.
- **Affected URLs** (1): https://books.toscrape.com/
- **Suggested Action**: Verify the site is accessible and the URL is correct. *(Priority: critical, Effort: low)*

## Methodology & Limitations

- **Scope**: Evaluates technical AI discoverability, content extractability, structured data completeness, and citation readiness based on an observable crawl snapshot.
- **Scoring Principles**: All scoring formulas and journey deductions are 100% deterministic and rule-grounded, measuring concrete technical readiness rather than subjective or volatile LLM search rankings.
- **Execution Guarantee**: This audit operates purely in read-only analysis mode without modifying site infrastructure, publishing changes, or executing non-idempotent operations.
- **Known Boundaries & Constraints**:
  - Crawl depth is capped at 20 pages per run under standard execution parameters.
  - Dynamic Single-Page Application (SPA) content requires headless rendering with Playwright fallback when JavaScript rendering is enabled.
  - Content behind authentication, paywalls, or strict CAPTCHA barriers is outside audit scope.
