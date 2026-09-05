# Brand AI-Readiness Audit Marketplace

A specialized Agent Skill Marketplace built for the **Adobe University Hackathon 2026 (Round 3)**.

The marketplace audits any website to evaluate **AI Discoverability** (can autonomous AI agents and answer engines find, read, understand, and trust the brand?) and **On-Site Engagement** (do visitors who arrive understand the offering and take action?).

> **Core Philosophy:** This is **NOT** a traditional SEO checker.  
> It operates on the paradigm: **Crawl the website → Understand what an AI agent can reach, read, understand, and trust → Evaluate whether critical brand questions can be answered → Identify root causes → Prioritize high-ROI improvements → Provide actionable recommendations.**

---

## 1. Problem Statement

Search has fundamentally evolved from 10 blue links to **generative AI answer engines** (ChatGPT Search, Perplexity, Google Gemini, Claude) and **autonomous shopping / workflow agents**. 
When these agents inspect a website, traditional meta tags and keyword stuffing no longer suffice. Agents fail when:
- Content is trapped behind client-side JavaScript without server-side rendering.
- Machine-readable structured facts (`schema.org` JSON-LD) are missing, incomplete, or contradict visible copy.
- Brand identity is fractured across pages with inconsistent legal names, locations, and founding dates.
- Internal links lead to dead ends or redirect loops.
- Core brand queries ("What do you do?", "What does it cost?", "Where are you?") cannot be corroborated.

---

## 2. Key Novelty & Differentiators

Unlike generic SEO checkers that output hundreds of trivial warnings, this marketplace introduces:
1. **The AI Agent Journey Framework**: Evaluates 6 distinct pillars — **Reach, Read, Understand, Trust, Navigate, Act** — using evidence aggregated across specialized audit skills.
2. **Agent Answerability Matrix**: Directly queries the crawl snapshot to determine if an AI agent can answer the 5 critical brand questions (*What does this company do? What products/services does it offer? Where is it located? What does the product cost? How can users contact it?*), scoring each as *Supported, Weakly supported, Conflicting,* or *Not found*.
3. **Adaptive JavaScript Inspection**: Inspects raw HTML first; renders dynamically only when content depends on JS; compares raw HTML vs rendered DOM and flags JS-dependent content.
4. **Context-Aware Auditing & False-Positive Elimination**: 11-type page classification (*Homepage, About, Contact, Product, Service, Pricing, Blog/article, Documentation, Event, Careers, Other/unknown*) ensures contextual rules apply (e.g., documentation pages are not penalized for missing conversion CTAs or schema).
5. **Cross-Page Fact Consistency**: Cross-references visible prices against JSON-LD offers, and verifies entity names, locations, and founding years across pages.
6. **Multi-Factor Prioritization**: Prioritizes findings by **Impact × Reach × Confidence**, ensuring teams fix root-cause blockers first.

---

## 3. Architecture & Skill Marketplace

The marketplace is decomposed into 8 deterministic, sandboxed skills that collaborate via a single shared snapshot:

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 User / Agent Harness                   │
                  │   ("Check the Microsoft website and generate a report")│
                  └───────────────────────────┬────────────────────────────┘
                                              │
                                              ▼
                                ┌───────────────────────────┐
                                │ audit-orchestrator (Entry)│
                                └─────────────┬─────────────┘
                                              │ 1. Invokes crawl once
                                              ▼
                                ┌───────────────────────────┐
                                │        site-crawler       │
                                └─────────────┬─────────────┘
                                              │ Emits shared snapshot.json
                                              ▼
          ┌───────────────────────────────────┼───────────────────────────────────┐
          │                                   │                                   │
          ▼                                   ▼                                   ▼
┌──────────────────┐               ┌──────────────────┐                ┌──────────────────┐
│ crawlability-    │               │ structured-data- │                │ entity-identity- │
│ render-audit     │               │ content-audit    │                │ audit            │
└─────────┬────────┘               └─────────┬────────┘                └─────────┬────────┘
          │                                   │                                   │
          ├───────────────────────────────────┼───────────────────────────────────┤
          │                                   │                                   │
          ▼                                   ▼                                   │
┌──────────────────┐               ┌──────────────────┐                           │
│ freshness-       │               │ engagement-audit │                           │
│ corroboration    │               │                  │                           │
└─────────┬────────┘               └─────────┬────────┘                           │
          │                                   │                                   │
          └───────────────────────────────────┼───────────────────────────────────┘
                                              │ Intermediate findings
                                              ▼
                                ┌───────────────────────────┐
                                │ Normalize & Deduplicate   │
                                └─────────────┬─────────────┘
                                              │ Clean deduplicated defects
                                              ▼
                                ┌───────────────────────────┐
                                │ proactive-opportunities-  │
                                │ audit                     │
                                └─────────────┬─────────────┘
                                              │ Proactive suggestions (non-duplicate)
                                              ▼
                                ┌───────────────────────────┐
                                │ Score & Assemble Report   │
                                │ (Journey, Answerability)  │
                                └─────────────┬─────────────┘
                                              │
                                              ▼
                                         report.json
```

### Skill Catalog:
1. **`audit-orchestrator`** (Entrypoint): Coordinates pipeline execution, handles natural-language URL extraction, isolates skill failures, normalizes and deduplicates findings, computes Journey and Answerability scores, and outputs `report.json`.
2. **`site-crawler`**: Crawls the target domain once, respects `robots.txt`, detects redirect loops and canonical disparities, detects page types, applies adaptive JS rendering, and writes `snapshot.json`.
3. **`crawlability-render-audit`**: Checks robots exclusions, HTTP errors, redirect loops, canonical conflicts, and content hidden behind JavaScript.
4. **`structured-data-content-audit`**: Audits JSON-LD completeness, verifies schema relevance to page types, and detects visible vs structured data pricing conflicts.
5. **`entity-identity-audit`**: Cross-references organization name across `<title>`, `<h1>`, JSON-LD, About, and Contact pages; flags identity drift and conflicting founding dates.
6. **`freshness-corroboration-audit`**: Differentiates time-sensitive content (Pricing, Products) from evergreen documentation; detects stale dates and temporal contradictions.
7. **`engagement-audit`**: Audits visitor orientation, navigation labels, call-to-actions, and detects genuine dead-end pages while suppressing false positives on terminal doc pages.
8. **`proactive-opportunities-audit`**: Runs last to suggest high-ROI enhancements (e.g., FAQ schema, Event schema, BreadcrumbList) without duplicating existing defects.

---

## 4. Ingestion & Crawling Engine

The crawler (`skills/site-crawler/scripts/crawl.py`) guarantees safe, fast, and representative site exploration:
- **Input Flexibility**: Accepts standard URLs (`https://example.com`), naked domains (`example.com`), and natural-language prompts (`Check the Microsoft website and generate a report`).
- **Single Shared Snapshot**: All 6 downstream audit skills read from one authoritative `snapshot.json`. No skill performs redundant network requests.
- **Adaptive JS Handling**: First inspects raw HTML. Only executes Playwright rendering if visible text is low (<1000 chars) and an SPA root or missing headings indicate JS dependency. Reports `js_dependent_content` and content disparity metrics.
- **Page-Type Classification**: Heuristically classifies pages into 11 categories: *Homepage, About, Contact, Product, Service, Pricing, Blog/article, Documentation, Event, Careers, Other/unknown*.
- **Bounded Crawl Limits**: Caps representative pages per category (max 3 pages per type) to guarantee the entire crawl finishes in under 3 minutes.
- **Protocol Safety**: Strictly respects `robots.txt`, detects redirect loops (status 310 or >5 hops), identifies conflicting canonical tags, and tracks 4xx/5xx HTTP errors.

---

## 5. The AI Agent Journey Framework

Rather than reporting isolated SEO errors, findings are grouped into the **6 Pillars of the AI Agent Journey**:

| Pillar | What It Measures | Example Finding |
|---|---|---|
| **Reach** | Can crawlers access and fetch the URLs without restriction? | `CRA-001`: robots.txt disallows all crawling |
| **Read** | Can an AI model extract clean text, headings, and metadata? | `CRA-008`: Critical content trapped in client-side JS |
| **Understand** | Can an AI engine parse machine-readable Schema.org facts? | `SDC-002`: Missing Product schema on catalog pages |
| **Trust** | Can an AI assistant verify authenticity, provenance, and freshness? | `ENT-009`: Conflicting founding years across pages |
| **Navigate** | Can an autonomous agent traverse links to complete tasks? | `ENG-004`: Dead-end pages with no onward internal links |
| **Act** | Can an agent or human execute conversion actions and transactions? | `ENG-001`: Missing primary call-to-action on landing page |

Each pillar receives a score from 0 to 100, providing website owners with a clear visual breakdown of their AI accessibility bottleneck.

---

## 6. Agent Answerability Matrix

The report includes an **Agent Answerability** evaluation that audits whether 5 core questions can be answered from the crawled content:

1. **What does this company do?** (Checks meta descriptions, homepage value propositions, and Organization descriptions)
2. **What products/services does it offer?** (Checks Product/Service page types, catalog items, and service headings)
3. **Where is it located?** (Checks postal address in Schema.org and contact/about page address patterns)
4. **What does the product cost?** (Checks pricing pages, visible currency patterns, and JSON-LD Offer prices)
5. **How can users contact it?** (Checks contact pages, email regex, phone regex, and ContactPoint schema)

Each query is assigned:
- **Status**: `Supported` | `Weakly supported` | `Conflicting` | `Not found`
- **Confidence**: `high` | `medium` | `low`
- **Evidence**: Specific text excerpt or schema extract demonstrating the answer
- **Sources**: Exact URLs providing the grounding data

---

## 7. Evidence, Prioritization & Root Causes

- **Quantitative Evidence**: Findings avoid vague statements. Every finding explains what was found, where it was found, how widespread it is, and why it matters to an AI agent (e.g., *"0 of 14 product pages contain Product JSON-LD. AI cannot extract prices or specs"*).
- **Multi-Factor Prioritization**: Action items are ranked by `Impact × Reach × Confidence`, highlighting high-ROI items first rather than inflating minor missing tags to high severity.
- **Root-Cause Grouping**: If multiple findings share the same root cause (e.g. `entity_identity_drift` or `crawl_access_blocked`), they are grouped to prevent report fatigue.
- **Strengths Identification**: The report explicitly highlights what the website already does well (e.g., *"JSON-LD structured data present on all crawled pages"*, *"All crawled pages return HTTP 200"*).

---

## 8. Safety & Compliance Guarantees

- **Read-Only / Non-Destructive**: The marketplace only crawls and audits. It **never modifies the target website** or applies automated live fixes.
- **Zero Database Requirement**: Operates statelessly via filesystem JSON files. No database setup or persistent servers required.
- **Strict <5 Minute Runtime Bound**: Enforced page throttling, timeout limits (15s per request, 240s total crawl bound), and deterministic scripts guarantee the full audit finishes in < 5 minutes.
- **Graceful Fault Tolerance**: If any individual audit skill encounters an unhandled exception, the orchestrator catches it, records the failure in `run_info["failed_skills"]`, and successfully produces the final report with the remaining skills.

---

## 9. Installation & Running

### Requirements
- Python 3.10+
- Dependencies listed in `requirements.txt`

```bash
# Clone the repository
git clone https://github.com/Nitharshan369/brand-ai-auditor.git
cd brand-ai-auditor

# Install dependencies
pip install -r requirements.txt

# (Optional) Install Playwright for headless JS rendering
pip install playwright && playwright install chromium
```

### Running an Audit

Accepts direct URLs or natural language queries:

```bash
# Direct URL
python skills/audit-orchestrator/scripts/build_report.py \
    --url https://example.com \
    --max-pages 20 \
    --output report.json

# Natural Language Prompt
python skills/audit-orchestrator/scripts/build_report.py \
    --url "Check the Microsoft website and generate a report" \
    --output report.json
```

---

## 10. Automated Testing

The marketplace contains an offline, deterministic integration test suite covering **47 unit tests** across all 14 recommendation scenarios:

```bash
python -m unittest discover tests
```

### Test Coverage Highlights:
- **Clean Site Assertion (`TestCleanSite`)**: Asserts that a well-structured website receives 0 critical and 0 high-severity findings, achieving an AI readiness score ≥ 90.
- **14 Specific Scenarios (`TestFourteenFixtureScenarios`)**: Tests JS-heavy SPAs, clean sites, conflicting canonicals, redirect loops, broken links, robots restrictions, image-only data, entity inconsistencies, visible vs schema price conflicts, raw vs rendered DOM disparities, product/blog/doc page contexts, and limited crawl coverage.
- **Agent Journey & Answerability (`TestAgentJourneyAndAnswerability`)**: Validates journey scoring, 5-question answerability evaluation, and priority ranking.
- **Natural Language Parsing & Resiliency (`TestNaturalLanguageParsingAndResilience`)**: Validates domain extraction from prompts and fault-tolerant execution.
- **Marketplace Manifest Schema (`TestMarketplaceManifest`)**: Validates 100% compliance with Round 3 schema requirements.

---

## 11. Report Schema Reference (`report.json`)

```json
{
  "site": "example.com",
  "audited_at": "2026-09-01T12:00:00Z",
  "run_info": {
    "marketplace_version": "1.0.0",
    "query_input": "https://example.com",
    "target_url": "https://example.com",
    "skills_invoked": ["crawlability-render-audit", "structured-data-content-audit", "..."],
    "failed_skills": [],
    "pages_crawled": 12,
    "max_pages": 20,
    "crawl_duration_seconds": 8.4,
    "robots_txt_respected": true,
    "crawl_coverage": {
      "pages_discovered": 18,
      "pages_crawled": 12,
      "pages_skipped": 6,
      "failed_pages": [],
      "crawl_duration_seconds": 8.4,
      "robots_status": 200,
      "js_rendering_status": "not_needed"
    }
  },
  "summary": {
    "total_findings": 4,
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 1,
    "ai_readiness_score": 81,
    "by_category": {
      "discoverability": 3,
      "engagement": 1
    },
    "agent_journey_scores": {
      "reach": 100,
      "read": 95,
      "understand": 80,
      "trust": 85,
      "navigate": 90,
      "act": 80,
      "overall_journey_score": 88
    }
  },
  "agent_journey_scores": {
    "reach": 100,
    "read": 95,
    "understand": 80,
    "trust": 85,
    "navigate": 90,
    "act": 80,
    "overall_journey_score": 88
  },
  "agent_answerability": [
    {
      "question": "What does this company do?",
      "status": "Supported",
      "confidence": "high",
      "evidence": "Declared purpose: 'Cloud monitoring and compliance software...'",
      "sources": ["https://example.com/"]
    }
  ],
  "top_priorities": [
    {
      "id": "F-001",
      "title": "No structured data on product pages",
      "category": "discoverability",
      "severity": "high",
      "confidence": "high",
      "affected_pages_count": 3,
      "suggested_action": "Add Product/Offer JSON-LD to every product page.",
      "priority_score": 32.5,
      "priority_rank": 1
    }
  ],
  "findings": [ ... ],
  "proactive_recommendations": [ ... ],
  "strengths": [ ... ]
}
```
