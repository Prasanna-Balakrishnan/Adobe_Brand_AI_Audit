# Expected Finding Categories — Test Fixtures

This file documents which finding **categories** each fixture is expected to trigger.
Tests assert on categories, not exact wording, to support generalization.

---

## js-heavy-spa

| Expected Category | Expected Check ID | Rationale |
|-------------------|-------------------|-----------|
| `discoverability` | `CRA-008` | JS-only content — no visible text without render |
| `discoverability` | `SDC-001` | No JSON-LD on any page |
| `discoverability` | `CRA-006` | No canonical tags |
| `discoverability` | `SDC-003` | Missing Organization/WebSite schema |
| `discoverability` | `SDC-005` | Missing H1 |

**NOT expected:**
- `engagement` findings (too few pages to trigger engagement checks meaningfully)
- `critical` findings (robots.txt not blocked; homepage technically reachable)

---

## static-well-structured

| Expected Category | Notes |
|-------------------|-------|
| Zero `critical` findings | Site is well-configured |
| AI readiness score ≥ 70 | Good JSON-LD, canonical, About, Contact |
| `discoverability` source: `json-ld` | Brand name derivable from JSON-LD |

**May still trigger (not failures):**
- MEDIUM discoverability findings (e.g. missing blog schema if no blog detected)
- LOW findings (e.g. sameAs depth, minor heading gaps)

---

## ambiguous-entity

| Expected Category | Expected Check ID | Rationale |
|-------------------|-------------------|-----------|
| `discoverability` | `ENT-003` | No About page |
| `discoverability` | `ENT-004` | No contact information |
| `discoverability` | `FRS-003` | Contradicting founding years (2018 vs 2015) |
| `discoverability` | `SDC-001` | No JSON-LD |
| `discoverability` | `CRA-006` | No canonical |

**Brand name derivation:** Should fall back to `h1` source since no JSON-LD org present.

---

## stale-content

| Expected Category | Expected Check ID | Rationale |
|-------------------|-------------------|-----------|
| `discoverability` | `FRS-002` | last_modified = 2019-01-15, threshold 365 days |
| `discoverability` | `SDC-001` or no finding | JSON-LD is present on this fixture |

**Note:** `FRS-001` should NOT fire here (last_modified IS present).

---

## good-discoverability-bad-engagement

| Expected Category | Expected Check ID | Rationale |
|-------------------|-------------------|-----------|
| `engagement` | `ENG-001` | No CTA links on homepage |
| `engagement` | `ENG-004` | features page is a dead end (no outbound links) |
| `discoverability` | (few or none) | JSON-LD + canonical + sameAs all present |

**Score expectation:** Should have higher `by_category.discoverability` score
than `by_category.engagement` (more engagement findings than discoverability).
