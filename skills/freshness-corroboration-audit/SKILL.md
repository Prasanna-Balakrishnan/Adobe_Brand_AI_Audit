---
name: freshness-corroboration-audit
description: >
  Audits whether a site's content is current, verifiable, and internally consistent.
  Checks for stale publication or modification dates on time-sensitive pages
  while respecting evergreen documentation; detects internally contradicting
  facts across pages; and evaluates date provenance signals.
  Returns standardized findings JSON for the orchestrator.
license: Apache-2.0
allowed-tools:
  - file_read
---

# freshness-corroboration-audit

## When to Use

After `site-crawler` has produced `snapshot.json`. Invoke once per audit run.
All checks operate strictly on snapshot data without making live network calls.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_path` | string | `./snapshot.json` | Path to crawler snapshot |
| `output_path` | string | `./freshness_findings.json` | Output path |
| `stale_threshold_days` | integer | 365 | Days since last-modified before a time-sensitive page is flagged as stale |

## Procedure

1. Load `snapshot.json`.
2. Run all checks from `references/checks.md` against snapshot data:
   - `FRS-001`: Missing publication or last-modified date signals on time-sensitive pages (pricing, announcements, job postings)
   - `FRS-002`: Stale dates (>365 days) on time-sensitive content, suppressing false positives on evergreen documentation
   - `FRS-003`: Internally contradicting dates or factual claims across crawled pages
3. Ground all findings in explicit page URLs and date string citations.
4. Record detected freshness strengths (e.g. recent modification timestamps across crawled pages).
5. Write output JSON to `output_path`.

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
