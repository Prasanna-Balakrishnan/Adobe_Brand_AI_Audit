---
name: freshness-corroboration-audit
description: >
  Audits whether the site's content is current and internally consistent.
  Checks stale or missing publication/modification dates, internally
  contradicting facts, and (bounded, optional) cross-web corroboration
  signals. Runtime is bounded to prevent unbounded web crawling.
license: Apache-2.0
allowed-tools:
  - file_read
---

# freshness-corroboration-audit

## When to Use

After `site-crawler` has produced `snapshot.json`. Invoke once per audit run.
Cross-web checks are bounded and optional — they must not trigger unbounded crawling.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_path` | string | `./snapshot.json` | Path to crawler snapshot |
| `output_path` | string | `./freshness_findings.json` | Output path |
| `stale_threshold_days` | integer | 365 | Days since last-modified before "stale" |

## Procedure

1. Load `snapshot.json`.
2. Run all checks from `references/checks.md` (freshness + corroboration).
3. Write output JSON.

## Output

```json
{
  "skill": "freshness-corroboration-audit",
  "findings": [ { "check_id": "FRS-001", ... } ],
  "strengths": [ { "title": "...", "category": "discoverability" } ]
}
```

## Execution

```bash
python skills/freshness-corroboration-audit/scripts/audit.py \
  --snapshot snapshot.json \
  --output freshness_findings.json \
  --stale-threshold-days 365
```
