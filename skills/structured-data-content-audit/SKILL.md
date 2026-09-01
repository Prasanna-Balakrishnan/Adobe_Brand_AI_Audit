---
name: structured-data-content-audit
description: >
  Audits whether a site's content is machine-extractable by AI agents and
  search crawlers. Checks JSON-LD presence and validity against schema.org
  types, whether key facts (prices, specs, names) are stated as explicit
  plain text vs. buried in images, and meaningful heading structure.
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
2. Run all checks from `references/schema-checks.md` (JSON-LD structural checks).
3. Run all checks from `references/extractability-checks.md` (plain-text fact checks).
4. Aggregate findings and detected strengths.
5. Write output JSON.

Check details, thresholds, and schema.org type list: see the references directory.

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
