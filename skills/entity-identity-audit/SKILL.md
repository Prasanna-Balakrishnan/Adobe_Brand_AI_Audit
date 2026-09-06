---
name: entity-identity-audit
description: >
  Audits whether the brand can be clearly identified and distinguished from
  lookalikes by AI assistants. Checks organization name consistency across
  pages, presence of About/Contact/location information, author/org
  attribution, sameAs social links, and ambiguous or colliding entity names.
  Returns standardized findings JSON for the orchestrator.
license: Apache-2.0
allowed-tools:
  - file_read
---

# entity-identity-audit

## When to Use

After `site-crawler` has produced `snapshot.json`. Invoke once per audit run.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_path` | string | `./snapshot.json` | Path to crawler snapshot |
| `output_path` | string | `./entity_findings.json` | Output path |

## Procedure

1. Load `snapshot.json`.
2. Run all checks from `references/checks.md` against snapshot data:
   - `ENT-001`: Missing Organization / LocalBusiness JSON-LD on homepage
   - `ENT-002`: Inconsistent organization identity across key page elements (`<title>`, `<h1>`, JSON-LD)
   - `ENT-003` & `ENT-004`: Missing dedicated About and Contact pages
   - `ENT-005`: Missing physical postal address and direct communication channels
   - `ENT-006`: Missing author attribution on article/blog pages
   - `ENT-007` & `ENT-008`: Missing sameAs links and colliding entity names
   - `ENT-009`: Conflicting entity facts (e.g. founding year or headquarters location across pages)
3. Derive candidate brand name from schema `name`, `<title>`, and `<h1>` elements.
4. Collect findings as intermediate JSON objects and record detected strengths.
5. Write output JSON to `output_path`.

## Output

```json
{
  "skill": "entity-identity-audit",
  "findings": [ { "check_id": "ENT-001", ... } ],
  "strengths": [ { "title": "...", "category": "discoverability" } ]
}
```

## Execution

```bash
python skills/entity-identity-audit/scripts/audit.py \
  --snapshot snapshot.json \
  --output entity_findings.json
```
