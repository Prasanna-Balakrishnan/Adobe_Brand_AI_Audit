---
name: audit-orchestrator
description: >
  Entrypoint skill for the Brand AI-Readiness Audit marketplace. Accepts a
  website URL, invokes site-crawler to produce a shared snapshot, fans out
  to all six audit skills, normalises and deduplicates findings, computes
  the AI readiness score, runs the proactive-opportunities audit, and emits
  the final structured JSON report.
license: Apache-2.0
allowed-tools:
  - file_read
  - file_write
  - subprocess
---

# audit-orchestrator

## When to Use

This is the **only skill the outside world calls**. Invoke it with a URL and
receive a complete audit report. It coordinates all other skills internally.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | — | Fully-qualified URL of the site to audit (required) |
| `max_pages` | integer | 20 | Maximum pages to crawl |
| `output` | string | `./report.json` | Final report output path |
| `work_dir` | string | `./audit_work/` | Temp dir for intermediate files |
| `use_js_render` | boolean | false | Enable Playwright JS rendering |

## Procedure

1. **Crawl** — invoke `site-crawler` → `{work_dir}/snapshot.json`.
2. **Fan-out** — invoke each audit skill in parallel (or sequential fallback)
   against the shared snapshot:
   - `crawlability-render-audit` → `crawlability_findings.json`
   - `structured-data-content-audit` → `structured_data_findings.json`
   - `entity-identity-audit` → `entity_findings.json`
   - `freshness-corroboration-audit` → `freshness_findings.json`
   - `engagement-audit` → `engagement_findings.json`
3. **Normalize** — `scripts/normalize_findings.py` assigns `F-NNN` IDs, enforces enums.
4. **Deduplicate** — `scripts/deduplicate_findings.py` clusters near-duplicates into `root_cause_group`s.
5. **Score** — `scripts/score.py` computes `ai_readiness_score` and summary counts.
6. **Proactive** — invoke `proactive-opportunities-audit` with snapshot + deduped findings.
7. **Build** — `scripts/build_report.py` assembles the final JSON report.

See `references/orchestration-rules.md` for full data-flow diagram and error handling.

## Output

`report.json` — the final audit report matching the schema in `references/report-schema.md`.

## Execution

```bash
python skills/audit-orchestrator/scripts/build_report.py \
  --url https://example.com \
  --max-pages 20 \
  --output report.json
```
