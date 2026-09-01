# Entity Identity Audit — Check Definitions

All checks use only data from `snapshot.json`. Check IDs use prefix `ENT`.

The auditor derives the **candidate brand name** from this priority order:
1. `Organization.name` in JSON-LD on the homepage.
2. The most common H1 text across pages (stripped of common stop words).
3. The site domain name (apex, e.g. `example` from `example.com`).

---

## ENT-001 — Brand name not detectable (HIGH)

**Category:** discoverability
**Confidence:** medium

**Trigger:** None of the three derivation methods yields a candidate name (no JSON-LD
org name, no H1 on any page, domain name is a single letter or common word).

**Evidence:** Confirm absence of each derivation source.

**Suggested action:** Add an `Organization` JSON-LD with a `name` field to the
homepage. Ensure the H1 on the homepage states the brand name.

---

## ENT-002 — Inconsistent organisation name across pages (HIGH)

**Category:** discoverability
**Confidence:** medium (heuristic: string comparison)

**Trigger:** The candidate brand name appears in significantly different forms
across >50% of pages. "Different form" means the name differs by more than
case, punctuation, or common suffixes (Inc, LLC, Ltd, Corp).

**Evidence:** List the name variants found and the pages they appear on (up to 5 each).

**Suggested action:** Standardise the organisation name across all pages. Use the
same canonical form in all JSON-LD, titles, and body text.

---

## ENT-003 — No About page detected (HIGH)

**Category:** discoverability
**Confidence:** medium

**Trigger:** No crawled URL contains `/about`, `/who-we-are`, `/our-story`,
`/company`, or similar patterns AND no page title contains "About" or similar.

**Evidence:** Confirm no About-page URL pattern found in crawled pages.

**Suggested action:** Create a dedicated About page with the organisation name,
description, founding year, mission, and contact information. This is a primary
source for AI fact panels.

---

## ENT-004 — No Contact page or contact information detected (HIGH)

**Category:** discoverability
**Confidence:** medium

**Trigger:** No crawled URL matches `/contact`, `/reach-us`, `/get-in-touch` AND
no page contains a visible email, phone number, or physical address.

**Evidence:** Confirm no contact-page URL found and no contact info in visible text samples.

**Suggested action:** Add a Contact page with at minimum an email address or contact
form. Include the Organisation's address and phone if applicable.

---

## ENT-005 — No author attribution on blog/article pages (MEDIUM)

**Category:** discoverability
**Confidence:** medium

**Trigger:** Pages matching blog/article URL patterns have no `Article.author` in
JSON-LD AND no author name pattern in visible text (by name patterns or
"by Author" format).

**Evidence:** Count of article pages without author attribution; list URLs.

**Suggested action:** Add `author` to Article JSON-LD and include a visible
byline on all article pages.

---

## ENT-006 — Entity name ambiguity risk (MEDIUM)

**Category:** discoverability
**Confidence:** low (heuristic: short/generic name)

**Trigger:** The candidate brand name is fewer than 4 characters OR consists
entirely of common English words (checked against a small stop-word list)
without a disambiguating qualifier.

**Evidence:** State the detected name and why it may be ambiguous.

**Suggested action:** Add `disambiguatingDescription` and `sameAs` to Organisation
JSON-LD. Use the full legal name in structured data even if a shorter name is used
in marketing.

---

## ENT-007 — Missing sameAs links in Organisation JSON-LD (LOW)

**Category:** discoverability
**Confidence:** high

**Trigger:** Homepage has `Organization` JSON-LD but the block lacks a `sameAs`
property pointing to authoritative profiles (Wikipedia, Wikidata, LinkedIn, etc.).

**Evidence:** Show the Organisation JSON-LD block; confirm absence of `sameAs`.

**Suggested action:** Add `sameAs` URLs to the Organisation schema (LinkedIn,
Wikipedia, Wikidata, Crunchbase) to help AI agents corroborate entity identity.

---

## Strengths to Detect

| Condition | Strength title | Category |
|-----------|---------------|----------|
| Organization JSON-LD with name on homepage | "Brand name declared in Organization JSON-LD" | discoverability |
| About page found | "About page present for entity context" | discoverability |
| Contact page found | "Contact information accessible" | discoverability |
| sameAs present | "sameAs links in Organization schema support entity corroboration" | discoverability |
