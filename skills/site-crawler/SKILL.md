---
name: site-crawler
description: >
  Shared web crawl engine for the Brand AI-Readiness Audit marketplace.
  Fetches up to max_pages pages from a target site, classifies page types,
  tracks redirects and canonicals, optionally renders JavaScript, checks
  robots.txt compliance, and serialises a single snapshot.json consumed
  by every downstream audit skill.
license: Apache-2.0
allowed-tools:
  - http_get
  - file_write
---

# site-crawler

## When to Use

Invoke **once per audit run**, before any audit skill. All audit skills read
from the shared `snapshot.json`; none of them re-crawl the live site.
This skill is *not* an audit skill — it produces no findings itself.

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_url` / `--url` | string | — | Fully-qualified URL or natural-language query to audit (required) |
| `max_pages` | integer | 20 | Hard cap on pages crawled (up to 3 per category) |
| `timeout_seconds` | integer | 240 | Hard wall-clock crawl budget in seconds |
| `use_js_render` | boolean | false | If true, attempt headless render via Playwright for JS-dependent pages |
| `output_path` / `--output` | string | `./snapshot.json` | Where to write the snapshot |

## Procedure

1. **robots.txt Compliance** — fetch `{scheme}://{host}/robots.txt`; parse disallowed paths for
   `*` and `Googlebot` agents. Record `disallowed_paths` and `robots_status`.
   If `robots.txt` returns 4xx/5xx, treat as allowed but log status.
2. **Seed queue** — add normalized `start_url` to the BFS frontier (if not disallowed).
3. **Crawl loop** — while `len(visited) < max_pages` and elapsed < `timeout_seconds`:
   a. Dequeue next URL; skip if already visited or disallowed.
   b. HTTP GET with `User-Agent: BrandAuditBot/1.0 (+https://github.com/adobe-hackathon/brand-ai-readiness-audit)`.
   c. Follow up to 5 redirects; record full redirect chain, canonical tags, and status codes.
   d. If `use_js_render=true` and JS detection heuristics fire, call `render_dom.py`.
   e. Parse HTML via `crawl.py`: extract title, meta, headings, JSON-LD, Open Graph, Twitter card,
      links, images with alt text, visible text, raw HTML, and last-modified.
   f. Classify page into 11 types: Homepage, About, Contact, Product, Service, Pricing,
      Blog/article, Documentation, Event, Careers, Other/unknown.
   g. Enqueue all same-origin internal `<a href>` links (excluding disallowed paths,
      fragment-only, mailto:, tel:).
   h. Append page record to `pages[]` list.
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
