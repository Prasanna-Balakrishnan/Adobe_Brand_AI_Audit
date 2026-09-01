---
name: site-crawler
description: >
  Shared web crawl engine for the Brand AI-Readiness Audit marketplace.
  Fetches up to max_pages pages from a target site, optionally renders
  JavaScript, checks robots.txt compliance, and serialises a single
  snapshot.json consumed by every downstream audit skill.
license: Apache-2.0
allowed-tools:
  - http_get
  - file_write
---

# site-crawler

## When to Use

Invoke **once per audit run**, before any audit skill.  All audit skills read
from the shared `snapshot.json`; none of them re-crawl the live site.
This skill is *not* an audit skill — it produces no findings itself.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_url` | string | — | Fully-qualified URL of the site to audit (required) |
| `max_pages` | integer | 20 | Hard cap on pages crawled |
| `timeout_seconds` | integer | 240 | Wall-clock crawl budget in seconds |
| `use_js_render` | boolean | false | If true, attempt headless render via Playwright |
| `output_path` | string | `./snapshot.json` | Where to write the snapshot |

## Procedure

1. **robots.txt** — fetch `{scheme}://{host}/robots.txt`; parse disallowed paths for
   `*` and `Googlebot` agents.  Record `disallowed_paths` and `crawl_policy_url`.
   If `robots.txt` returns 4xx/5xx, treat as no restrictions but log a warning.
2. **Seed queue** — add `start_url` to the BFS frontier (if not disallowed).
3. **Crawl loop** — while `len(visited) < max_pages` and elapsed < `timeout_seconds`:
   a. Dequeue next URL; skip if already visited or disallowed.
   b. HTTP GET with `User-Agent: BrandAuditBot/1.0 (+https://github.com/adobe-hackathon/brand-ai-readiness-audit)`.
   c. Follow up to 5 redirects; record full redirect chain.
   d. If `use_js_render=true` and JS detection heuristics fire, call `render_dom.py`.
   e. Parse HTML via `crawl.py`: extract title, meta, headings, JSON-LD, OG, links,
      images, visible text, last-modified.
   f. Enqueue all same-origin internal `<a href>` links (excluding disallowed paths,
      fragment-only, mailto:, tel:).
   g. Append page record to `pages[]` list.
4. **Serialise** — write `snapshot.json` according to the schema in
   `references/crawl-policy.md` and `orchestration-rules.md`.
5. **Return** — print path to `snapshot.json` on stdout.

## Output

`snapshot.json` — see `references/crawl-policy.md` for full field reference.
The orchestrator reads this file; no other output is produced by this skill.

## Execution

```bash
python skills/site-crawler/scripts/crawl.py \
  --url https://example.com \
  --max-pages 20 \
  --output snapshot.json
```
