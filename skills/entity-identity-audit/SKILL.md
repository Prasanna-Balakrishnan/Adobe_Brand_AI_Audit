---
name: entity-identity-audit
description: >
  Audits whether the brand can be clearly identified and distinguished from
  lookalikes by AI assistants. Checks organisation name consistency across
  pages, presence of About/Contact/location information, author/org
  attribution, and ambiguous or colliding entity names.
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
2. Run all checks from `references/checks.md` against snapshot data.
3. Derive the candidate brand name from JSON-LD `Organization.name`, `<title>` tags,
   and H1 text — then test consistency across pages.
4. Write output JSON.

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
