# Final Report Schema — Brand AI-Readiness Audit

This document is the **authoritative contract** for the JSON object emitted by
`build_report.py`. All audit skills and orchestrator scripts must conform to this
schema. No field may be added or removed without updating this document first.

---

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `site` | string | ✅ | The apex domain audited (e.g. `"example.com"`) |
| `audited_at` | string (ISO-8601 UTC) | ✅ | Timestamp when audit completed |
| `run_info` | object | ✅ | Metadata about this audit run |
| `summary` | object | ✅ | Aggregated severity counts + score |
| `findings` | array\<Finding\> | ✅ | All deduplicated audit findings |
| `proactive_recommendations` | array\<Recommendation\> | ✅ | Beyond-defect suggestions |
| `strengths` | array\<Strength\> | ✅ | Detected positive signals |

---

## `run_info` Object

```json
{
  "marketplace_version": "1.0.0",
  "skills_invoked": ["crawlability-render-audit", "..."],
  "pages_crawled": 18,
  "max_pages": 20,
  "crawl_duration_seconds": 47,
  "robots_txt_respected": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `marketplace_version` | string | Semver of this marketplace release |
| `skills_invoked` | array\<string\> | Skill names called, in invocation order |
| `pages_crawled` | integer | Number of pages actually crawled |
| `max_pages` | integer | The cap configured for this run |
| `crawl_duration_seconds` | number | Wall-clock seconds for the crawl phase |
| `robots_txt_respected` | boolean | Always `true`; crawl aborts if false |

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
| `affected_urls` | array\<string\> | — | At least one URL; must be from crawled pages |
| `evidence` | string | — | Specific, quantified evidence (counts, URLs, quotes) |
| `root_cause_group` | string | `"RC-NNN"` or `null` | Groups near-duplicate findings; null if unique |
| `suggested_action.summary` | string | — | Concrete, actionable fix |
| `suggested_action.priority` | string | `"critical"`, `"high"`, `"medium"`, `"low"` | Fix priority |
| `suggested_action.effort` | string | `"low"`, `"medium"`, `"high"` | Implementation effort |

### Confidence Rules
- `"high"` — deterministic/mechanical check: parsed data absent, HTTP code != 200, regex match
- `"medium"` — heuristic text-based check: heading quality, navigation structure
- `"low"` — inference/estimation: freshness signals, entity disambiguation

---

## `Recommendation` Object (proactive_recommendations[])

```json
{
  "id": "P-001",
  "title": "Add FAQ-style Q&A content to top landing pages",
  "category": "discoverability",
  "rationale": "Accurate product info exists but no explicit Q&A text for assistants to quote.",
  "priority": "medium"
}
```

| Field | Type | Allowed Values | Description |
|-------|------|----------------|-------------|
| `id` | string | `"P-NNN"` | Sequential ID |
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

## Intermediate Skill Output Schema

Each audit skill (skills 3–8) must return this JSON structure before the orchestrator normalizes it:

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
