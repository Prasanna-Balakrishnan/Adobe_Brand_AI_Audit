# Brand AI-Readiness Audit Marketplace

This is a complete Agent Skill Marketplace built for the Adobe University Hackathon 2026, Round 3. It audits any website URL for:

1. **AI Discoverability** — Can AI assistants find, read, and correctly represent the brand?
2. **On-Site Engagement** — Do human visitors who arrive understand the offering and take action?

## Architecture & Skills

The marketplace is decomposed into 8 distinct skills that run in a deterministic pipeline without modifying the live site:

1. **`audit-orchestrator`** (Entrypoint)
   The single entrypoint for the marketplace. It coordinates the entire pipeline, normalizes and deduplicates findings, scores the site, and assembles the final JSON report.
2. **`site-crawler`** (Shared Engine)
   Produces a single read-only `snapshot.json` to prevent redundant live crawling. Respects `robots.txt` and caps execution time and depth.
3. **`crawlability-render-audit`**
   Audits robots directives, HTTP errors, redirect loops, and JS-only content barriers.
4. **`structured-data-content-audit`**
   Audits schema.org JSON-LD validity, missing entity properties, and ensures key facts aren't locked in images.
5. **`entity-identity-audit`**
   Audits brand name consistency, disambiguation risks, and presence of About/Contact orientation pages.
6. **`freshness-corroboration-audit`**
   Detects stale dates and internally contradicting facts across the site.
7. **`engagement-audit`**
   Audits visitor orientation, clear CTAs, navigation structures, and dead-end pages.
8. **`proactive-opportunities-audit`**
   Runs *after* all findings are deduplicated. Suggests high-ROI improvements (e.g., FAQ schema, Video schema) that go beyond fixing defects without duplicating existing findings.

## Output

The orchestrator emits a final JSON report containing:
- `summary`: Computed AI-readiness score and severity counts.
- `findings`: Array of deduplicated `F-NNN` defects with severity, category, evidence, and actionable fixes.
- `proactive_recommendations`: Array of `P-NNN` opportunities.
- `strengths`: Detected positive signals.

## Running the Audit

Install dependencies:
```bash
pip install -r requirements.txt
# (Optional) For JS-rendering support:
# pip install playwright && playwright install chromium
```

Run the orchestrator:
```bash
python skills/audit-orchestrator/scripts/build_report.py --url https://example.com --max-pages 20
```

## Running Tests

Integration tests run entirely offline using HTML fixtures to ensure deterministic schema validation and expected finding categories.

```bash
pytest tests/test_audit.py -v
```
