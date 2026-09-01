# Freshness & Corroboration Audit — Check Definitions

All checks use only data from `snapshot.json` (static analysis). Cross-web
corroboration is bounded and read-only. Check IDs use prefix `FRS`.

---

## FRS-001 — No date signals on any page (HIGH)

**Category:** discoverability
**Confidence:** high

**Trigger:** `last_modified` is null or empty for ALL crawled pages AND no JSON-LD
block contains `datePublished` or `dateModified` on any page.

**Evidence:** Confirm absence of `last_modified` values across all pages. Confirm
absence of date properties in all JSON-LD blocks.

**Suggested action:** Add `Last-Modified` HTTP headers and `datePublished`/`dateModified`
to JSON-LD on all content pages. AI assistants use dates to assess fact currency.

---

## FRS-002 — Stale content (>12 months) on majority of pages (HIGH)

**Category:** discoverability
**Confidence:** medium (heuristic: date parsing)

**Trigger:** >30% of pages with a parseable `last_modified` date are more than
`stale_threshold_days` (default: 365) days old relative to audit time.

**Evidence:** Count of stale pages / total pages with dates; list the oldest pages
with their dates.

**Suggested action:** Update high-priority pages and refresh their `dateModified`
in JSON-LD. Establish a content review cycle so key pages are updated regularly.

---

## FRS-003 — Internally contradicting facts (MEDIUM)

**Category:** discoverability
**Confidence:** low (heuristic: visible text comparison)

**Trigger:** Two or more pages make specific numeric claims that contradict each other
— e.g., "Founded in 2010" on one page and "Founded in 2015" on another. Detected
by regex patterns for years, prices, and employee counts.

**Evidence:** List the contradicting pages and the conflicting values found.

**Suggested action:** Audit and reconcile contradicting facts across pages. Use
JSON-LD structured data to establish a single authoritative source.

---

## FRS-004 — Missing datePublished/dateModified in Article JSON-LD (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** Pages with `Article` or `BlogPosting` JSON-LD lack `datePublished`
or `dateModified` properties.

**Evidence:** Count and list affected pages.

**Suggested action:** Add `datePublished` and `dateModified` to all Article JSON-LD
blocks. These are required fields for AI assistants to assess content currency.

---

## FRS-005 — Inconsistent publication date signals (LOW)

**Category:** discoverability
**Confidence:** medium

**Trigger:** A page has both a `Last-Modified` header date and a `dateModified` in
JSON-LD, and they differ by more than 30 days.

**Evidence:** List pages where HTTP header date and JSON-LD date diverge significantly.

**Suggested action:** Synchronise `Last-Modified` headers with `dateModified` in
JSON-LD to give consistent freshness signals.

---

## Strengths to Detect

| Condition | Strength title | Category |
|-----------|---------------|----------|
| All pages have `last_modified` | "All crawled pages have date signals" | discoverability |
| All dates are < stale_threshold_days | "Content appears fresh (recent modification dates)" | discoverability |
| All Article JSON-LD has datePublished | "Article pages have datePublished in JSON-LD" | discoverability |
