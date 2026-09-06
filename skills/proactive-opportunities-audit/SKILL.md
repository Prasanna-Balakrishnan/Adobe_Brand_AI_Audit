---
name: proactive-opportunities-audit
description: >
  Runs last in the audit pipeline, after all defect findings are finalized. Given
  the deduplicated findings and crawl snapshot, identifies high-ROI enhancement
  opportunities beyond existing defects (e.g., FAQ schema, BreadcrumbList, Event
  markup, sameAs social corroboration) without duplicating reported findings.
  Returns standardized recommendations JSON for the orchestrator.
license: Apache-2.0
allowed-tools:
  - file_read
---

# proactive-opportunities-audit

## When to Use

After `audit-orchestrator` has run `deduplicate_findings.py` and `score.py`.
This skill is the **last** step before `build_report.py`.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_path` | string | `./snapshot.json` | Path to crawler snapshot |
| `findings_path` | string | `./deduplicated_findings.json` | Deduplicated findings from orchestrator |
| `output_path` | string | `./proactive_findings.json` | Output recommendations |

## Procedure

1. Load `snapshot.json` and `deduplicated_findings.json`.
2. Build a set of already-reported `(category, topic)` pairs to prevent duplicating defects.
3. Run all opportunity patterns from `references/opportunity-patterns.md`:
   - `PRO-001`: Add FAQ-style Q&A content and FAQPage schema to key landing pages
   - `PRO-002`: Add BreadcrumbList markup to multi-level navigation paths
   - `PRO-003`: Add sameAs social media and authoritative entity reference links
   - `PRO-004`: Add Event schema for upcoming brand gatherings, webinars, or launches
   - `PRO-005`: Add SearchAction potentialAction schema on homepage WebSite entities
4. Emit only recommendations that do NOT duplicate an existing finding.
5. Record proactive strengths detected during analysis.
6. Write output JSON to `output_path`.

## Output

```json
{
  "skill": "proactive-opportunities-audit",
  "recommendations": [
    {
      "id": "PRO-001",
      "title": "Add FAQ-style Q&A content to top landing pages",
      "category": "discoverability",
      "rationale": "Accurate product info exists but no explicit Q&A text for assistants to quote.",
      "priority": "medium"
    }
  ]
}
```

## Execution

```bash
python skills/proactive-opportunities-audit/scripts/audit.py \
  --snapshot snapshot.json \
  --findings deduplicated_findings.json \
  --output proactive_findings.json
```
