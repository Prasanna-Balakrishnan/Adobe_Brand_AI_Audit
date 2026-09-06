# Orchestration Rules — audit-orchestrator

This document defines the deterministic invocation order, data-flow contracts, and
error-handling rules that `build_report.py` must follow.

---

## Invocation Order

```
URL
 │
 ▼
[1] site-crawler          → snapshot.json   (shared read-only input for all audits)
 │
 ├─▶ [2a] crawlability-render-audit      → crawlability_findings.json
 ├─▶ [2b] structured-data-content-audit → structured_data_findings.json
 ├─▶ [2c] entity-identity-audit         → entity_findings.json
 ├─▶ [2d] freshness-corroboration-audit → freshness_findings.json
 └─▶ [2e] engagement-audit              → engagement_findings.json
          (skills 2a–2e run independently; order within group is alphabetical)
 │
 ▼
[3] normalize_findings.py   → normalized_findings.json
     (assign F-NNN ids, enforce enums, attach source_skill)
 │
 ▼
[4] deduplicate_findings.py → deduplicated_findings.json
     (cluster near-duplicates into root_cause_groups)
 │
 ▼
[5] score.py                → summary, journey, answerability, top_priorities
     (counts, ai_readiness_score, by_category, 6-pillar agent journey, answerability matrix, multi-factor priorities)
 │
 ▼
[6] proactive-opportunities-audit → proactive_findings.json
     (runs AFTER findings are finalized; must not duplicate findings)
 │
 ▼
[7] build_report.py         → report.json & report.md
     (assemble all pieces into the final schema with methodology_and_limitations, companion markdown, terminal dashboard)
```

---

## Data-Flow Contracts

### snapshot.json (site-crawler output)

```json
{
  "crawl_meta": {
    "start_url": "https://example.com",
    "crawl_started_at": "2026-09-20T14:00:00Z",
    "crawl_ended_at": "2026-09-20T14:01:00Z",
    "pages_crawled": 18,
    "max_pages": 20,
    "robots_txt_respected": true,
    "robots_txt_url": "https://example.com/robots.txt",
    "disallowed_paths": ["/admin/", "/private/"]
  },
  "pages": [
    {
      "url": "https://example.com/",
      "status_code": 200,
      "final_url": "https://example.com/",
      "redirect_chain": [],
      "canonical": "https://example.com/",
      "meta_robots": "",
      "x_robots_tag": "",
      "title": "Example — The Best Product",
      "meta_description": "We make the best product for you.",
      "h1": ["Example"],
      "headings": [{"level": 1, "text": "Example"}, {"level": 2, "text": "Features"}],
      "json_ld": [],
      "open_graph": {},
      "twitter_card": {},
      "links": [
        {"href": "https://example.com/about", "text": "About", "is_internal": true}
      ],
      "images": [
        {"src": "https://example.com/logo.png", "alt": "Example logo", "width": 200, "height": 60}
      ],
      "visible_text_length": 842,
      "visible_text_sample": "We make the best product...",
      "last_modified": "2025-01-15",
      "crawled_with_js": false,
      "js_render_available": false,
      "raw_html_length": 12430
    }
  ]
}
```

All audit skills receive `snapshot.json` as their sole input. They must not re-crawl.

### Intermediate findings JSON (each audit skill output)

```json
{
  "skill": "<skill-name>",
  "findings": [ { "check_id": "...", ... } ],
  "strengths": [ { "title": "...", "category": "..." } ]
}
```

See `report-schema.md` for full field definitions.

---

## Error-Handling Rules

| Situation | Action |
|-----------|--------|
| site-crawler fails entirely | Abort audit; emit error JSON with `{"error": "crawl_failed", "reason": "..."}` |
| An audit skill raises an exception | Log warning; continue with other skills; note skipped skill in `run_info.skills_invoked` with `_SKIPPED` suffix |
| A finding is missing required fields | Drop it with a logged warning; never emit a partial finding |
| `affected_urls` contains a URL not in `snapshot.pages` | Drop the finding with a warning |
| `severity` or `category` is not in enum | Drop the finding with a warning |
| Duplicate `check_id` within same skill output | Keep first; drop subsequent with warning |

---

## Determinism Requirements

1. All skills read from the same frozen `snapshot.json` — no live network calls during audit.
2. Finding IDs (`F-NNN`) are assigned in this order: severity DESC (`critical` → `low`),
   then `source_skill` alphabetically, then `check_id` alphabetically within skill.
3. `root_cause_group` IDs (`RC-NNN`) are assigned in order of first-seen finding index.
4. The final JSON is serialized with `sort_keys=False`, `indent=2`, consistent field order
   matching the schema in `report-schema.md`.

---

## robots.txt Enforcement

The site-crawler must:
1. Fetch and parse `robots.txt` before crawling any page.
2. Skip any URL whose path is disallowed for `*` or `Googlebot` user-agent.
3. Record `disallowed_paths` in `crawl_meta`.
4. Never crawl a disallowed URL even if linked from an allowed page.
5. Set `robots_txt_respected: true` unconditionally (the system is read-only).

If `robots.txt` disallows ALL paths (`Disallow: /`), the crawl is considered
partially blocked — crawl only the homepage if it is not explicitly blocked, and
emit a `CRA-001` critical finding.
