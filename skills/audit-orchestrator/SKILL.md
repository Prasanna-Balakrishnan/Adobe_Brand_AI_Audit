---
name: audit-orchestrator
description: >
  Master entrypoint skill for the Brand AI-Readiness Audit marketplace. Accepts
  a website URL or natural-language query, invokes site-crawler to produce a shared
  snapshot, fans out to all supporting audit skills, normalises and deduplicates
  findings, computes the AI readiness score, 6-pillar Agent Journey scores, 5-question
  Answerability matrix, multi-factor top priorities, executes proactive opportunities
  audit, and emits the final structured report.json and companion report.md.
license: Apache-2.0
allowed-tools:
  - file_read
  - file_write
  - subprocess
---

# audit-orchestrator

## When to Use

This is the **only skill the outside world calls**. Invoke it with a URL (or natural-language query) and
receive a complete audit report. It coordinates all other skills internally.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | — | Fully-qualified URL or natural-language query of the site to audit (required unless `--snapshot` is provided) |
| `max_pages` | integer | 20 | Maximum pages to crawl |
| `output` | string | `./report.json` | Final JSON report output path (companion `.md` generated alongside) |
| `work_dir` | string | `./audit_work/` | Temp dir for intermediate files |
| `use_js_render` | boolean | false | Enable Playwright JS rendering |
| `stale_threshold_days` | integer | 365 | Days before dates are flagged as stale |
| `snapshot` | string | None | Optional path to pre-built `snapshot.json` (replaces crawler step for offline execution) |

## Procedure

1. **Crawl** — invoke `site-crawler` → `{work_dir}/snapshot.json` (or load pre-existing `--snapshot`).
2. **Fan-out** — invoke each audit skill against the shared snapshot:
   - `crawlability-render-audit` → `crawlability_findings.json`
   - `structured-data-content-audit` → `structured_data_findings.json`
   - `entity-identity-audit` → `entity_findings.json`
   - `freshness-corroboration-audit` → `freshness_findings.json`
   - `engagement-audit` → `engagement_findings.json`
3. **Normalize** — `scripts/normalize_findings.py` assigns `F-NNN` IDs and enforces taxonomy enums.
4. **Deduplicate** — `scripts/deduplicate_findings.py` clusters near-duplicates into `root_cause_group`s (`RC-NNN`).
5. **Score & Evaluate** — `scripts/score.py` computes:
   - `ai_readiness_score` (deterministic formula: `max(0, 100 - (critical*25) - (high*10) - (medium*4) - (low*1))`)
   - `agent_journey_scores` across 6 pillars: Reach, Read, Understand, Trust, Navigate, Act + Overall Journey
   - `agent_answerability` matrix across 5 core brand questions with evidence-calibrated confidence
   - `top_priorities` ordered deterministically by `(-priority_score, severity_rank, -affected_pages_count, id)`
6. **Proactive** — invoke `proactive-opportunities-audit` with snapshot + deduped findings to identify non-duplicate enhancements.
7. **Assemble Reports** — `scripts/build_report.py`:
   - Emits authoritative structured `report.json` with `methodology_and_limitations`.
   - Generates human-readable companion `report.md`.
   - Prints scan-friendly summary dashboard to terminal `sys.stderr`.

See `references/orchestration-rules.md` for full data-flow diagram and error handling.

## Outputs

- `report.json` — the authoritative structured audit report matching `references/report-schema.md`.
- `report.md` — companion human-readable Markdown report with executive summaries and prioritized action tables.

## Execution

```bash
# Standard live audit
python skills/audit-orchestrator/scripts/build_report.py \
  --url https://example.com \
  --max-pages 20 \
  --output report.json

# Offline snapshot audit
python skills/audit-orchestrator/scripts/build_report.py \
  --snapshot snapshot.json \
  --output report.json
```
