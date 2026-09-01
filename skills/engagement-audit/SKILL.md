---
name: engagement-audit
description: >
  Audits whether visitors who arrive at the site understand it and are
  guided to take action. Checks value proposition clarity, navigation
  structure, call-to-action presence, dead-end pages, and context
  retention across the site. Returns standardised findings JSON.
license: Apache-2.0
allowed-tools:
  - file_read
---

# engagement-audit

## When to Use

After `site-crawler` has produced `snapshot.json`. Invoke once per audit run.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_path` | string | `./snapshot.json` | Path to crawler snapshot |
| `output_path` | string | `./engagement_findings.json` | Output path |

## Procedure

1. Load `snapshot.json`.
2. Run all checks from `references/checks.md` against snapshot data.
3. Write output JSON.

Check details, thresholds, and evidence requirements: `references/checks.md`.

## Output

```json
{
  "skill": "engagement-audit",
  "findings": [ { "check_id": "ENG-001", ... } ],
  "strengths": [ { "title": "...", "category": "engagement" } ]
}
```

## Execution

```bash
python skills/engagement-audit/scripts/audit.py \
  --snapshot snapshot.json \
  --output engagement_findings.json
```
