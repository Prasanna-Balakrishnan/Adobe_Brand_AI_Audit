# Proactive Opportunity Patterns

Opportunity patterns fire when the site is NOT already penalised for a defect
in the same area — these are *beyond-defect* suggestions. Each pattern checks
that no existing finding covers the same ground before emitting a recommendation.

Opportunity IDs use prefix `PRO`. All recommendations use the `recommendations[]`
output array (NOT `findings[]`).

---

## PRO-001 — FAQ/Q&A Content Opportunity

**Category:** discoverability
**Priority:** medium

**Fires when:**
- No existing finding about missing JSON-LD covers FAQPage schema.
- No URL matches `/faq`, `/help`, `/questions`, `/q-and-a`.
- The site has product or service pages (URLs with product/service patterns).

**Rationale:** AI assistants frequently quote FAQ-style content verbatim when
answering user questions. Adding Q&A content significantly increases the chance
of being cited. This is an *opportunity*, not a defect — the existing content
is fine, but Q&A would extend reach.

**Title:** "Add FAQ-style Q&A content to top landing pages"

---

## PRO-002 — BreadcrumbList Schema Enhancement

**Category:** discoverability
**Priority:** low

**Fires when:**
- No existing finding about missing structured data on all pages.
- The site has a URL depth > 2 on any crawled page (suggesting hierarchy).
- No crawled page has JSON-LD with `@type: BreadcrumbList`.

**Rationale:** BreadcrumbList helps AI agents and search engines understand
site hierarchy and navigate context. It's often missing even on sites that
otherwise have good structured data.

**Title:** "Add BreadcrumbList structured data to reflect site hierarchy"

---

## PRO-003 — SiteLinksSearchBox / SearchAction Schema

**Category:** discoverability
**Priority:** low

**Fires when:**
- Site has >5 pages crawled (suggesting real content depth).
- No `SearchAction` or `SiteLinksSearchBox` detected in any JSON-LD.
- No existing high-severity finding about missing JSON-LD entirely.

**Rationale:** If the site has substantial content, enabling the search box
in AI and search results panels helps users navigate directly to relevant content.

**Title:** "Add SearchAction to WebSite schema for sitelinks search box"

---

## PRO-004 — Video/Media Schema Opportunity

**Category:** discoverability
**Priority:** medium

**Fires when:**
- Any page's visible text sample or title contains "video", "watch", "demo",
  "tutorial", "webinar", or "recording".
- No `VideoObject` JSON-LD detected on any page.

**Rationale:** Video content is frequently overlooked for structured data.
VideoObject JSON-LD with transcript or description dramatically increases
AI discoverability of multimedia content.

**Title:** "Add VideoObject JSON-LD to pages featuring video content"

---

## PRO-005 — HowTo / Step-by-Step Content

**Category:** discoverability
**Priority:** medium

**Fires when:**
- Any page heading contains "how to", "steps", "guide", or "tutorial".
- No `HowTo` JSON-LD detected on those pages.

**Rationale:** HowTo schema dramatically increases the chance of appearing
in AI assistant responses for "how do I" queries — a major discovery vector.

**Title:** "Add HowTo structured data to guide and tutorial pages"

---

## PRO-006 — Review/Rating Schema

**Category:** discoverability
**Priority:** medium

**Fires when:**
- Any page URL or heading mentions "review", "rating", "testimonial", or "case study".
- No `Review` or `AggregateRating` JSON-LD found.
- No existing finding about missing JSON-LD on all pages.

**Rationale:** Social proof in structured form is a powerful trust signal for AI.
If you have reviews or testimonials, marking them up enables AI assistants to cite
specific ratings and quotes.

**Title:** "Mark up reviews and testimonials with Review/AggregateRating schema"

---

## PRO-007 — Author Expertise Content (E-E-A-T signals)

**Category:** discoverability
**Priority:** medium

**Fires when:**
- Blog or article pages exist.
- Author attribution exists (no ENT-005 finding fired).
- No `Person` JSON-LD with `jobTitle`, `alumniOf`, or `knowsAbout` detected.

**Rationale:** AI agents use expertise signals (credentials, affiliations) to
assess content authority. Author schema with expertise fields enhances AI trust.

**Title:** "Add expertise fields to author Person JSON-LD (jobTitle, knowsAbout)"

---

## PRO-008 — Multilingual / hreflang Opportunity

**Category:** discoverability
**Priority:** low

**Fires when:**
- The site has >3 pages with different language indicators in URL
  (`/en/`, `/fr/`, `/de/`, `/es/`) or HTML `lang` attribute variations.
- No `hreflang` alternate link tags detected.

**Rationale:** Without hreflang, AI assistants may cite the wrong language
version of content or confuse pages as duplicates.

**Title:** "Add hreflang alternate links for multilingual content"

---

## PRO-009 — Event Schema for Upcoming Events

**Category:** discoverability
**Priority:** high

**Fires when:**
- Any page URL/heading mentions "event", "conference", "webinar", "summit", "meetup".
- No `Event` JSON-LD found on those pages.

**Rationale:** Event schema is one of the highest-ROI structured data types —
AI assistants specifically surface upcoming events in response to "what's happening
with [brand]" queries.

**Title:** "Add Event structured data to event and webinar pages"

---

## PRO-010 — OpenGraph / Social Sharing Enhancement

**Category:** engagement
**Priority:** low

**Fires when:**
- >25% of pages are missing `og:title`, `og:description`, or `og:image`.
- No existing finding covers this specifically.

**Rationale:** Even if structured data and on-page content are strong,
missing OpenGraph tags mean poor previews when content is shared — reducing
referral traffic and social proof.

**Title:** "Complete OpenGraph tags for richer social sharing previews"
