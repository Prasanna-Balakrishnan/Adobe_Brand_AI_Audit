---
name: structured-data-content-audit
description: >
  Audits whether a site's content is machine-extractable by AI agents and
  answer engines. Validates Schema.org JSON-LD presence, syntax, and relevance
  across diverse organization and business subtypes; checks plain-text fact
  extractability (prices, specs, contact details); and detects semantic
  contradictions between structured data and visible headings or content.
  Returns standardized findings JSON for the orchestrator.
license: Apache-2.0
allowed-tools:
  - file_read
---

# structured-data-content-audit

## When to Use

After `site-crawler` has produced `snapshot.json`. Invoke once per audit run.
Do **not** make live network calls — all analysis uses the snapshot only.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_path` | string | `./snapshot.json` | Path to crawler snapshot |
| `output_path` | string | `./structured_data_findings.json` | Output path |

## Procedure

1. Load `snapshot.json`.
2. Run all schema checks (`references/schema-checks.md`):
   - `SDC-001` to `SDC-003`: JSON-LD syntax, presence on key pages, and valid organization/local business types (supports `Organization`, `LocalBusiness`, `Hospital`, `Restaurant`, `Store`, etc.)
   - `SDC-004` to `SDC-006`: BreadcrumbList schema, Article/BlogPosting schema, and Course/Event/JobPosting schemas
   - `SDC-007` to `SDC-008`: Incomplete schema records and duplicate conflicting schema types
3. Run all extractability & consistency checks (`references/extractability-checks.md`):
   - `SDC-009`: Disparity between visible on-page price and JSON-LD `Offer.price`
   - `SDC-201` to `SDC-204`: Missing H1, multiple H1 tags, skipped heading levels, and empty heading text
   - `SDC-205` to `SDC-207`: Text trapped in images without alt text, thin content pages, and unextractable specs
   - `SDC-209`: Semantic contradiction between Schema.org `@type`/name and visible page headings
4. Aggregate findings and detected strengths.
5. Write output JSON.

## Output

```json
{
  "skill": "structured-data-content-audit",
  "findings": [ { "check_id": "SDC-001", ... } ],
  "strengths": [ { "title": "...", "category": "discoverability" } ]
}
```

## Execution

```bash
python skills/structured-data-content-audit/scripts/audit.py \
  --snapshot snapshot.json \
  --output structured_data_findings.json
```
