---
name: engagement-audit
description: >
  Audits whether visitors who arrive at the site understand the offering and are
  guided to take action. Checks value proposition clarity, visitor orientation,
  navigation structure, call-to-action presence, and dead-end pages while
  accounting for page context (e.g. terminal documentation pages).
  Returns standardized findings JSON for the orchestrator.
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
2. Run all checks from `references/checks.md` against snapshot data:
   - `ENG-001`: Missing primary call-to-action (CTA) on homepage or key landing pages
   - `ENG-002`: Missing or generic navigation anchor text labels
   - `ENG-003`: Missing concise value proposition in visible heading/content above the fold
   - `ENG-004`: Dead-end pages with no onward internal links (suppresses false positives on terminal doc pages)
   - `ENG-005`: Deep page architecture (>4 click depth from root)
   - `ENG-010`: Core orientation pages present in crawl but not meaningfully reachable from homepage/primary navigation
3. Collect findings with `engagement` category and record detected strengths.
4. Write output JSON to `output_path`.

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
