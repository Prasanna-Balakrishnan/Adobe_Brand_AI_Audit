---
name: crawlability-render-audit
description: >
  Audits whether crawlers and AI agents can access and fully read a site's
  content. Checks robots.txt blocks, HTTP errors, redirect loops, noindex
  directives, missing/conflicting canonicals, JS-only content, and broken
  internal links. Returns standardised findings JSON for the orchestrator.
license: Apache-2.0
allowed-tools:
  - file_read
---

# crawlability-render-audit

## When to Use

After `site-crawler` has produced `snapshot.json`. Invoke once per audit run.
Do **not** invoke before the crawl snapshot is available.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_path` | string | `./snapshot.json` | Path to crawler snapshot |
| `output_path` | string | `./crawlability_findings.json` | Output path |

## Procedure

1. Load `snapshot.json` from `snapshot_path`.
2. Run all checks listed in `references/checks.md` against the snapshot data.
3. For each check, compute evidence from snapshot fields — **no live network calls**.
4. Collect findings as intermediate JSON objects (see `report-schema.md`).
5. Collect detected strengths.
6. Write output JSON to `output_path`.

Full check list, thresholds, and evidence requirements: `references/checks.md`.

## Output

```json
{
  "skill": "crawlability-render-audit",
  "findings": [ { "check_id": "CRA-001", ... } ],
  "strengths": [ { "title": "...", "category": "discoverability" } ]
}
```

## Execution

```bash
python skills/crawlability-render-audit/scripts/audit.py \
  --snapshot snapshot.json \
  --output crawlability_findings.json
```
