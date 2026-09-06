---
name: crawlability-render-audit
description: >
  Audits whether crawlers and AI agents can access and fully read a site's
  content. Checks robots.txt blocks, AI bot restrictions, HTTP status codes,
  redirect chains and loops, noindex directives, canonical consistency,
  URL hygiene and tracking pollution, raw vs rendered DOM disparities,
  and broken internal links. Returns standardized findings JSON for the orchestrator.
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
2. Run all checks listed in `references/checks.md` against snapshot data (no live network calls):
   - `CRA-001` to `CRA-005`: robots.txt blocks, AI crawler exclusions (GPTBot/ClaudeBot), HTTP errors
   - `CRA-006` to `CRA-007`: Redirect loops and long redirect chains (>5 hops)
   - `CRA-008` & `CRA-019`: JS-only content and raw vs rendered DOM content disparities
   - `CRA-009` to `CRA-012`: Broken links, missing/empty title tags, meta description absence
   - `CRA-013` to `CRA-015`: High-value page reachability, canonical conflicts, noindex directives
   - `CRA-016` to `CRA-018`: Canonical targets 4xx/5xx, duplicate URLs, query parameter pollution
   - `CRA-020`: Sitemap absence with material discoverability impact
3. For each check, ground evidence strictly in observable snapshot fields.
4. Collect findings as intermediate JSON objects (see `report-schema.md`).
5. Collect detected strengths.
6. Write output JSON to `output_path`.

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
