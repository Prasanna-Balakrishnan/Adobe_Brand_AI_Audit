# Schema.org Structured Data Checks

All checks use only data from `snapshot.json`. Check IDs use prefix `SDC` (1xx range).

---

## SDC-001 — No JSON-LD on any page (HIGH)

**Category:** discoverability
**Confidence:** high (deterministic: `json_ld` array is empty for all pages)

**Trigger:** 100% of crawled pages have `json_ld: []`.

**Evidence:** Total pages crawled; confirm 0/N contain JSON-LD.

**Suggested action:** Add schema.org JSON-LD markup starting with the most impactful
types for your site category (Organization, WebSite, Product, Article, FAQ).

---

## SDC-002 — No JSON-LD on product/service pages (HIGH)

**Category:** discoverability
**Confidence:** high

**Trigger:** Pages whose URL or title suggests a product/service page (keywords:
`/product`, `/service`, `/item`, `/shop`, `/store`, `/buy`, `/pricing`) have no JSON-LD.

**Evidence:** Count of product-like pages without JSON-LD / total product-like pages.
List up to 5 affected URLs.

**Suggested action:** Add `Product`, `Offer`, or `Service` JSON-LD to every product
and service page.

---

## SDC-003 — Missing Organization or WebSite schema on homepage (HIGH)

**Category:** discoverability
**Confidence:** high

**Trigger:** The homepage (start_url) has `json_ld: []` OR none of its JSON-LD blocks
contain `@type: Organization` or `@type: WebSite`.

**Evidence:** Confirm absence of these schema types on the homepage URL.

**Suggested action:** Add `Organization` and `WebSite` JSON-LD to the homepage.
`Organization` helps AI assistants identify and describe the brand correctly.

---

## SDC-004 — Invalid JSON-LD (missing @type or @context) (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** Any JSON-LD block is missing `@type` or `@context`.

**Evidence:** List pages with invalid blocks; show the malformed block excerpt.

**Suggested action:** Ensure every JSON-LD block includes both `@context:
"https://schema.org"` and a valid `@type`.

---

## SDC-005 — Missing H1 on homepage (HIGH)

**Category:** discoverability
**Confidence:** high

**Trigger:** The homepage page record has `h1: []` (empty array).

**Evidence:** Confirm no H1 tag found on the homepage URL.

**Suggested action:** Add a single descriptive H1 to the homepage that clearly states
the brand name and primary value proposition.

---

## SDC-006 — Multiple H1 tags on pages (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** >25% of pages have `len(h1) > 1`.

**Evidence:** Count of multi-H1 pages / total; list up to 5 with their H1 texts.

**Suggested action:** Use exactly one H1 per page as the primary topic identifier.
Additional headings should use H2–H6.

---

## SDC-007 — Heading hierarchy gaps (LOW)

**Category:** discoverability
**Confidence:** medium (heuristic: structural analysis)

**Trigger:** Any page skips heading levels (e.g. H1 → H3 with no H2).

**Evidence:** List pages with heading gaps; show the heading sequence.

**Suggested action:** Maintain a logical heading hierarchy (H1 → H2 → H3) to help
AI agents understand content structure.

---

## SDC-008 — No JSON-LD on article/blog pages (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** Pages with URL patterns `/blog`, `/article`, `/news`, `/post` have no JSON-LD
OR have JSON-LD without `@type: Article` or `@type: BlogPosting`.

**Evidence:** Count of blog-like pages without Article JSON-LD; list URLs.

**Suggested action:** Add `Article` or `BlogPosting` JSON-LD with `headline`, `author`,
`datePublished`, and `dateModified` fields.

---

## SDC-009 — Sub-optimal schema types in use (LOW)

**Category:** discoverability
**Confidence:** medium

**Trigger:** Any JSON-LD block uses an over-generic type (`Thing`, `CreativeWork`) when
a more specific type clearly applies (based on URL pattern and page content).

**Evidence:** List the generic types found and the pages they appear on.

**Suggested action:** Replace generic schema types with the most specific applicable
type from schema.org (e.g. `Product`, `Article`, `Event`, `LocalBusiness`).

---

## Preferred schema.org Types by Page Pattern

| URL pattern | Recommended @type |
|-------------|-------------------|
| Homepage | `Organization`, `WebSite` |
| `/product*`, `/item*`, `/shop*` | `Product`, `Offer` |
| `/service*`, `/pricing*` | `Service` |
| `/blog*`, `/article*`, `/post*` | `Article`, `BlogPosting` |
| `/event*` | `Event` |
| `/faq*`, `/help*` | `FAQPage` |
| `/about*` | `AboutPage`, `Organization` |
| `/contact*` | `ContactPage` |
| `/review*` | `Review`, `AggregateRating` |
