# Final Report Schema — Brand AI-Readiness Audit

This document is the **authoritative contract** for the JSON object emitted by
`build_report.py`. All audit skills and orchestrator scripts must conform to this
schema. No field may be added or removed without updating this document first.

---

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `site` | string | ✅ | The normalized site/host audited (e.g. `"example.com"`) |
| `audited_at` | string (ISO-8601 UTC) | ✅ | Timestamp when audit completed |
| `run_info` | object | ✅ | Metadata about this audit run |
| `summary` | object | ✅ | Aggregated severity counts + score |
| `agent_journey_scores` | object | ✅ | AI Agent Journey readiness across 6 pillars |
| `agent_answerability` | array\<AnswerabilityQuestion\> | ✅ | Evaluation of 5 core brand questions |
| `top_priorities` | array\<PriorityItem\> | ✅ | Impact × Reach × Confidence prioritized actions |
| `findings` | array\<Finding\> | ✅ | All deduplicated audit findings |
| `proactive_recommendations` | array\<Recommendation\> | ✅ | Beyond-defect suggestions |
| `strengths` | array\<Strength\> | ✅ | Detected positive signals |
| `methodology_and_limitations` | object | ✅ | Audit scope, deterministic scoring principles, read-only guarantee, and limitations |

---

## `run_info` Object

```json
{
  "marketplace_version": "1.0.0",
  "query_input": "https://example.com",
  "target_url": "https://example.com",
  "skills_invoked": ["crawlability-render-audit", "structured-data-content-audit", "..."],
  "failed_skills": [],
  "pages_crawled": 18,
  "max_pages": 20,
  "crawl_duration_seconds": 47.2,
  "robots_txt_respected": true,
  "crawl_coverage": {
    "pages_discovered": 24,
    "pages_crawled": 18,
    "pages_skipped": 6,
    "failed_pages": [],
    "crawl_duration_seconds": 47.2,
    "robots_status": "allowed",
    "js_rendering_status": "disabled"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `marketplace_version` | string | Semver of this marketplace release |
| `query_input` | string | Original user query or prompt string |
| `target_url` | string | Resolved and normalized audit target URL |
| `skills_invoked` | array\<string\> | Skill names called, in invocation order |
| `failed_skills` | array\<object\> | Any skills that failed, with error message (empty on success) |
| `pages_crawled` | integer | Number of pages actually crawled |
| `max_pages` | integer | The cap configured for this run |
| `crawl_duration_seconds` | number | Wall-clock seconds for the crawl phase |
| `robots_txt_respected` | boolean | Always `true`; crawl aborts if false |
| `crawl_coverage` | object | Detailed crawl coverage metrics and status |

---

## `summary` Object

```json
{
  "total_findings": 9,
  "critical": 1,
  "high": 3,
  "medium": 4,
  "low": 1,
  "ai_readiness_score": 62,
  "by_category": {
    "discoverability": 6,
    "engagement": 3
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total_findings` | integer | `len(findings)` |
| `critical` | integer | Findings with severity `"critical"` |
| `high` | integer | Findings with severity `"high"` |
| `medium` | integer | Findings with severity `"medium"` |
| `low` | integer | Findings with severity `"low"` |
| `ai_readiness_score` | integer | 0–100, see `severity-rules.md` for formula |
| `by_category.discoverability` | integer | Count of discoverability findings |
| `by_category.engagement` | integer | Count of engagement findings |

---

## `agent_journey_scores` Object

```json
{
  "reach": 100,
  "read": 95,
  "understand": 80,
  "trust": 85,
  "navigate": 90,
  "act": 80,
  "overall_journey_score": 88
}
```

| Pillar | Description |
|--------|-------------|
| `reach` | Can AI crawlers access the site without robots/HTTP/redirect barriers? (0–100) |
| `read` | Can AI extract clean text and headings without JS rendering traps? (0–100) |
| `understand` | Can AI parse rich, valid Schema.org structured data? (0–100) |
| `trust` | Can AI verify fresh dates, provenance, and fact consistency? (0–100) |
| `navigate` | Can AI traverse internal links without dead ends? (0–100) |
| `act` | Can users and agents take action via clear CTAs and value propositions? (0–100) |
| `overall_journey_score` | Unweighted average across all 6 journey pillars (0–100) |

---

## `agent_answerability` Object (agent_answerability[])

```json
{
  "question": "What does this company do?",
  "status": "Supported",
  "confidence": "high",
  "evidence": "Declared purpose: 'Cloud monitoring and compliance software...'",
  "sources": ["https://example.com/"]
}
```

| Field | Type | Allowed Values | Description |
|-------|------|----------------|-------------|
| `question` | string | Core brand question | One of the 5 canonical brand questions |
| `status` | string | `"Supported"`, `"Weakly supported"`, `"Conflicting"`, `"Not found"` | Evaluation status |
| `confidence` | string | `"high"`, `"medium"`, `"low"` | Confidence level |
| `evidence` | string | — | Direct citation from crawl snapshot |
| `sources` | array\<string\> | — | Crawled page URLs supporting the finding |

---

## `top_priorities` Array (top_priorities[])

```json
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
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Corresponding Finding ID |
| `title` | string | Short finding title |
| `category` | string | `"discoverability"` or `"engagement"` |
| `severity` | string | Severity level |
| `confidence` | string | Confidence level |
| `affected_pages_count` | integer | Number of affected URLs |
| `suggested_action` | string | Actionable remediation summary |
| `priority_score` | number | Calculated Impact × Reach × Confidence score |
| `priority_rank` | integer | 1-based rank order |

---

## `Finding` Object

```json
{
  "id": "F-001",
  "title": "No JSON-LD structured data on product pages",
  "category": "discoverability",
  "severity": "high",
  "confidence": "high",
  "source_skill": "structured-data-content-audit",
  "tags": ["structured-data", "json-ld", "product-schema"],
  "affected_urls": ["https://example.com/products/a"],
  "evidence": "Crawled 12 product pages; 0/12 contain schema.org markup.",
  "root_cause_group": "RC-01",
  "suggested_action": {
    "summary": "Add Product/Offer JSON-LD to every product page.",
    "priority": "high",
    "effort": "low"
  }
}
```

| Field | Type | Allowed Values | Description |
|-------|------|----------------|-------------|
| `id` | string | `"F-NNN"` | Sequential 3-digit ID assigned by orchestrator |
| `title` | string | — | Short, factual title |
| `category` | string | `"discoverability"`, `"engagement"` | Must use taxonomy enum |
| `severity` | string | `"critical"`, `"high"`, `"medium"`, `"low"` | See severity-rules.md |
| `confidence` | string | `"high"`, `"medium"`, `"low"` | Evidence quality |
| `source_skill` | string | — | The skill that emitted this finding |
| `tags` | array\<string\> | — | Freeform lowercase kebab-case tags |
| `affected_urls` | array\<string\> | — | At least one URL; includes relevant discovered, attempted, or crawled pages |
| `evidence` | string | — | Specific, quantified evidence (counts, URLs, quotes) |
| `root_cause_group` | string | `"RC-NNN"` or `null` | Groups near-duplicate findings; null if unique |
| `suggested_action.summary` | string | — | Concrete, actionable fix |
| `suggested_action.priority` | string | `"critical"`, `"high"`, `"medium"`, `"low"` | Fix priority |
| `suggested_action.effort` | string | `"low"`, `"medium"`, `"high"` | Implementation effort |

### Confidence Rules
- `"high"` — Direct, unambiguous evidence (e.g., deterministic DOM/header checks, exact HTTP error codes, direct parser failure, or explicit schema validation errors).
- `"medium"` — Corroborated or high-signal heuristic evidence (e.g., text pattern analysis across key sections, navigation structural evaluations, or multiple consistent indicators).
- `"low"` — Inferred or probabilistic evidence (e.g., cross-page semantic inference, weak date signals, or entity disambiguation based on partial context).

---

## `Recommendation` Object (proactive_recommendations[])

```json
{
  "id": "PRO-001",
  "title": "Add FAQ-style Q&A content to top landing pages",
  "category": "discoverability",
  "rationale": "Accurate product info exists but no explicit Q&A text for assistants to quote.",
  "priority": "medium"
}
```

| Field | Type | Allowed Values | Description |
|-------|------|----------------|-------------|
| `id` | string | `"PRO-NNN"` | Sequential recommendation ID |
| `title` | string | — | Short opportunity title |
| `category` | string | `"discoverability"`, `"engagement"` | Taxonomy enum |
| `rationale` | string | — | Why this matters; based on findings context |
| `priority` | string | `"high"`, `"medium"`, `"low"` | Suggested priority |

---

## `Strength` Object (strengths[])

```json
{
  "title": "Consistent canonical tags across all crawled pages",
  "category": "discoverability"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Description of the detected positive signal |
| `category` | string | `"discoverability"` or `"engagement"` |

---

## `methodology_and_limitations` Object

```json
{
  "audit_scope": "Evaluates technical AI discoverability, content extractability, structured data completeness, and citation readiness based on an observable crawl snapshot.",
  "deterministic_scoring": "All scoring formulas and journey deductions are 100% deterministic and rule-grounded, measuring concrete technical readiness rather than subjective or volatile LLM search rankings.",
  "read_only_guarantee": "This audit operates purely in read-only analysis mode without modifying site infrastructure, publishing changes, or executing non-idempotent operations.",
  "limitations": [
    "Crawl depth is capped at 20 pages per run under standard execution parameters.",
    "Dynamic Single-Page Application (SPA) content requires headless rendering with Playwright fallback when JavaScript rendering is enabled.",
    "Content behind authentication, paywalls, or strict CAPTCHA barriers is outside audit scope."
  ]
}
```

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `audit_scope` | string | ✅ | Definition of technical AI discoverability scope |
| `deterministic_scoring` | string | ✅ | Explanation of rule-grounded readiness scoring |
| `read_only_guarantee` | string | ✅ | Confirmation of non-destructive execution |
| `limitations` | array\<string\> | ✅ | Technical boundaries and crawler constraints |

---

## Intermediate Skill Output Schema

Each supporting audit skill that emits findings must return this JSON structure before the orchestrator normalizes it (`site-crawler` produces the shared `snapshot.json` rather than direct findings):

```json
{
  "skill": "engagement-audit",
  "findings": [
    {
      "check_id": "ENG-003",
      "title": "Homepage lacks a clear value proposition",
      "category": "engagement",
      "severity": "high",
      "confidence": "medium",
      "affected_urls": ["https://example.com"],
      "evidence": "No clear description of the product or service found in main content.",
      "tags": ["value-proposition", "homepage"],
      "suggested_action": {
        "summary": "Add a concise headline and sub-headline above the fold.",
        "priority": "high",
        "effort": "low"
      }
    }
  ],
  "strengths": [
    { "title": "Clear primary CTA on homepage", "category": "engagement" }
  ]
}
```

### Rules
1. `check_id` must be unique within a skill and use the skill's prefix (see category-taxonomy.md).
2. `evidence` must contain a specific URL, count, or extracted value — never a generic statement.
3. `strengths` is optional but encouraged; an empty array is valid.
4. Skills must not emit `id`, `source_skill`, or `root_cause_group` — these are assigned by the orchestrator.
