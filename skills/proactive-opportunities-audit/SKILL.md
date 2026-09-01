---
name: proactive-opportunities-audit
description: >
  Runs LAST in the audit pipeline, after all findings are finalised. Given
  the deduplicated findings and detected strengths, suggests improvements
  beyond current defects — e.g. missing but valuable schema types, FAQ
  content opportunities, structured data enhancements. Recommendations are
  clearly tagged and must not duplicate already-reported findings.
license: Apache-2.0
allowed-tools:
  - file_read
---

# proactive-opportunities-audit

## When to Use

After `audit-orchestrator` has run `deduplicate_findings.py` and `score.py`.
This skill is the **last** step before `build_report.py`.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_path` | string | `./snapshot.json` | Path to crawler snapshot |
| `findings_path` | string | `./deduplicated_findings.json` | Deduplicated findings from orchestrator |
| `output_path` | string | `./proactive_findings.json` | Output recommendations |

## Procedure

1. Load `snapshot.json` and `deduplicated_findings.json`.
2. Build a set of already-reported `(category, topic)` pairs to avoid duplication.
3. Run all opportunity patterns from `references/opportunity-patterns.md`.
4. Emit only recommendations that do NOT duplicate an existing finding.
5. Detect strengths that the proactive audit uniquely identifies.
6. Write output JSON.

## Output

```json
{
  "skill": "proactive-opportunities-audit",
  "recommendations": [
    {
      "id": "PRO-001",
      "title": "...",
      "category": "discoverability",
      "rationale": "...",
      "priority": "medium"
    }
  ]
}
```

## Execution

```bash
python skills/proactive-opportunities-audit/scripts/audit.py \
  --snapshot snapshot.json \
  --findings deduplicated_findings.json \
  --output proactive_findings.json
```
