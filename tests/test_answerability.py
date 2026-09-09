#!/usr/bin/env python3
"""
test_answerability.py — Comprehensive unit tests for AI Answerability evaluation.
Tests all 9 generic website categories, the 4 result states, cross-page evidence,
anti-false-positive guarantees, and recommendation integrity.
"""

import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "audit-orchestrator" / "scripts"))

import importlib.util
spec = importlib.util.spec_from_file_location("score", REPO_ROOT / "skills" / "audit-orchestrator" / "scripts" / "score.py")
score_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score_mod)


def make_test_page(url: str, title: str = "", meta_description: str = "",
                    page_type: str = "Other/unknown", json_ld: list = None,
                    headings: list = None, visible_text_sample: str = "",
                    h1: list = None, links: list = None) -> dict:
    return {
        "url": url,
        "title": title,
        "meta_description": meta_description,
        "page_type": page_type,
        "json_ld": json_ld or [],
        "headings": headings or [],
        "visible_text_sample": visible_text_sample,
        "h1": h1 or ([title] if title else []),
        "links": links or []
    }


def make_test_snapshot(pages: list, start_url: str = "https://example.com/") -> dict:
    return {
        "crawl_meta": {
            "start_url": start_url,
            "pages_crawled": len(pages),
            "pages_discovered": len(pages)
        },
        "pages": pages
    }


class TestGenericWebsiteAnswerability(unittest.TestCase):
    """
    Tests answerability across the 9 minimum generic website categories:
    1. E-commerce/product website
    2. Service business
    3. Restaurant
    4. Healthcare website
    5. University/education website
    6. SaaS/software website
    7. Documentation website
    8. Event website
    9. Simple informational website
    """

    def test_1_ecommerce_product_website(self):
        pages = [
            make_test_page(
                url="https://shop.example.com/",
                title="Apex Outdoors Gear Store",
                meta_description="High-performance outdoor camping gear and waterproof apparel.",
                page_type="Homepage",
                json_ld=[{
                    "@type": "Store",
                    "name": "Apex Outdoors",
                    "address": {"streetAddress": "120 Pine St", "addressLocality": "Boulder", "addressCountry": "US"},
                    "contactPoint": {"telephone": "+1-303-555-0144", "email": "orders@apexoutdoors.com"}
                }]
            ),
            make_test_page(
                url="https://shop.example.com/products/all-weather-tent",
                title="All-Weather 4-Person Tent",
                page_type="Product",
                json_ld=[{
                    "@type": "Product",
                    "name": "All-Weather 4-Person Tent",
                    "offers": {"@type": "Offer", "price": "199.99", "priceCurrency": "USD"}
                }],
                visible_text_sample="Durable 4-person camping tent. In stock for $199.99 with free ground shipping."
            )
        ]
        snap = make_test_snapshot(pages, "https://shop.example.com/")
        res = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        by_cat = {item["category"]: item for item in res}

        self.assertEqual(by_cat["identity"]["status"], "Supported")
        self.assertEqual(by_cat["offerings"]["status"], "Supported")
        self.assertEqual(by_cat["pricing"]["status"], "Supported")
        self.assertIn("199.99", by_cat["pricing"]["evidence"])
        self.assertEqual(by_cat["contact"]["status"], "Supported")

    def test_2_service_business_website(self):
        pages = [
            make_test_page(
                url="https://consulting.example.com/",
                title="Stratagem Advisory Partners",
                meta_description="Management consulting firm advising Fortune 500 executives on supply chain resilience.",
                page_type="Homepage",
                json_ld=[{
                    "@type": "ProfessionalService",
                    "name": "Stratagem Advisory",
                    "address": {"streetAddress": "400 North Michigan Ave", "addressLocality": "Chicago", "addressCountry": "US"},
                    "contactPoint": {"telephone": "+1-312-555-0188", "email": "info@stratagem.com"}
                }]
            ),
            make_test_page(
                url="https://consulting.example.com/services",
                title="Our Advisory Services",
                page_type="Service",
                json_ld=[{
                    "@type": "Service",
                    "name": "Supply Chain Transformation & Strategy Consulting"
                }],
                visible_text_sample="Comprehensive supply chain audit and operational advisory services."
            )
        ]
        snap = make_test_snapshot(pages, "https://consulting.example.com/")
        res = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        by_cat = {item["category"]: item for item in res}

        self.assertEqual(by_cat["identity"]["status"], "Supported")
        self.assertEqual(by_cat["offerings"]["status"], "Supported")
        self.assertEqual(by_cat["location"]["status"], "Supported")
        self.assertEqual(by_cat["contact"]["status"], "Supported")

    def test_3_restaurant_website(self):
        pages = [
            make_test_page(
                url="https://bistro.example.com/",
                title="Trattoria Bella Napoli",
                meta_description="Authentic Neapolitan wood-fired pizza and handmade pasta.",
                page_type="Homepage",
                json_ld=[{
                    "@type": "Restaurant",
                    "name": "Trattoria Bella Napoli",
                    "servesCuisine": "Italian",
                    "priceRange": "$$",
                    "openingHours": "Mo-Su 11:30-22:00",
                    "address": {"streetAddress": "18 Via Roma", "addressLocality": "Boston", "addressCountry": "US"},
                    "contactPoint": {"telephone": "+1-617-555-0177", "email": "reservations@bellanapoli.com"}
                }]
            )
        ]
        snap = make_test_snapshot(pages, "https://bistro.example.com/")
        res = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        by_cat = {item["category"]: item for item in res}

        self.assertEqual(by_cat["identity"]["status"], "Supported")
        self.assertEqual(by_cat["pricing"]["status"], "Supported")
        self.assertIn("$$", by_cat["pricing"]["evidence"])
        self.assertIn("hours", by_cat)
        self.assertEqual(by_cat["hours"]["status"], "Supported")
        self.assertIn("11:30-22:00", by_cat["hours"]["evidence"])

    def test_4_healthcare_website(self):
        pages = [
            make_test_page(
                url="https://clinic.example.com/",
                title="Metropolitan Health Clinic",
                meta_description="Comprehensive family healthcare, primary care, and pediatric medicine.",
                page_type="Homepage",
                json_ld=[{
                    "@type": "MedicalClinic",
                    "name": "Metropolitan Health Clinic",
                    "address": {"streetAddress": "750 Medical Center Dr", "addressLocality": "Atlanta", "addressCountry": "US"},
                    "contactPoint": {"telephone": "+1-404-555-0199", "email": "appointments@metrohealth.org"}
                }]
            ),
            make_test_page(
                url="https://clinic.example.com/treatments/cardiology",
                title="Preventative Cardiology & Heart Screening",
                page_type="Service",
                json_ld=[{
                    "@type": "MedicalProcedure",
                    "name": "Echocardiogram and Cardiovascular Health Screening"
                }]
            )
        ]
        snap = make_test_snapshot(pages, "https://clinic.example.com/")
        res = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        by_cat = {item["category"]: item for item in res}

        self.assertEqual(by_cat["identity"]["status"], "Supported")
        self.assertEqual(by_cat["offerings"]["status"], "Supported")
        self.assertEqual(by_cat["location"]["status"], "Supported")

    def test_5_university_education_website(self):
        pages = [
            make_test_page(
                url="https://university.example.edu/",
                title="St. Jude Polytechnic University",
                meta_description="Accredited degree programs in computer science, mechanical engineering, and robotics.",
                page_type="Homepage",
                json_ld=[{
                    "@type": "CollegeOrUniversity",
                    "name": "St. Jude Polytechnic",
                    "address": {"streetAddress": "1000 University Parkway", "addressLocality": "Pittsburgh", "addressCountry": "US"},
                    "contactPoint": {"telephone": "+1-412-555-0122", "email": "admissions@stjude.edu"}
                }]
            ),
            make_test_page(
                url="https://university.example.edu/programs/cs-bs",
                title="Bachelor of Science in Computer Science",
                page_type="Service",
                json_ld=[{
                    "@type": "Course",
                    "name": "Computer Systems & Artificial Intelligence Program"
                }]
            )
        ]
        snap = make_test_snapshot(pages, "https://university.example.edu/")
        res = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        by_cat = {item["category"]: item for item in res}

        self.assertEqual(by_cat["identity"]["status"], "Supported")
        self.assertEqual(by_cat["offerings"]["status"], "Supported")
        self.assertEqual(by_cat["location"]["status"], "Supported")

    def test_6_saas_software_website(self):
        pages = [
            make_test_page(
                url="https://cloudapp.example.com/",
                title="DataSync - Automated Database Replication",
                meta_description="Real-time zero-downtime database synchronization for PostgreSQL and MySQL.",
                page_type="Homepage",
                json_ld=[{
                    "@type": "SoftwareApplication",
                    "name": "DataSync",
                    "applicationCategory": "DeveloperApplication",
                    "offers": {"@type": "AggregateOffer", "lowPrice": 49, "highPrice": 299, "priceCurrency": "USD"}
                }]
            ),
            make_test_page(
                url="https://cloudapp.example.com/pricing",
                title="Pricing Plans",
                page_type="Pricing",
                visible_text_sample="Starter plan is $49/mo. Pro plan is $149/mo. Enterprise custom quote."
            )
        ]
        snap = make_test_snapshot(pages, "https://cloudapp.example.com/")
        res = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        by_cat = {item["category"]: item for item in res}

        self.assertEqual(by_cat["identity"]["status"], "Supported")
        self.assertEqual(by_cat["pricing"]["status"], "Supported")
        self.assertIn("49", by_cat["pricing"]["evidence"])

    def test_7_documentation_website(self):
        pages = [
            make_test_page(
                url="https://docs.api.example.com/",
                title="HyperNet SDK & REST API Reference",
                meta_description="Official developer documentation, SDK libraries, and endpoints reference for HyperNet.",
                page_type="Documentation",
                h1=["HyperNet REST API Reference", "Quickstart Guide"]
            )
        ]
        snap = make_test_snapshot(pages, "https://docs.api.example.com/")
        res = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        by_cat = {item["category"]: item for item in res}

        self.assertEqual(by_cat["identity"]["status"], "Supported")
        self.assertIn("documentation", by_cat)
        self.assertEqual(by_cat["documentation"]["status"], "Supported")

    def test_8_event_website(self):
        pages = [
            make_test_page(
                url="https://conference.example.com/",
                title="Global AI Systems Summit 2026",
                meta_description="Premier international gathering of machine learning researchers and systems engineers.",
                page_type="Event",
                json_ld=[{
                    "@type": "Event",
                    "name": "Global AI Systems Summit",
                    "startDate": "2026-10-15T09:00:00Z",
                    "location": "Moscone Convention Center, San Francisco"
                }]
            )
        ]
        snap = make_test_snapshot(pages, "https://conference.example.com/")
        res = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        by_cat = {item["category"]: item for item in res}

        self.assertEqual(by_cat["identity"]["status"], "Supported")
        self.assertIn("events", by_cat)
        self.assertEqual(by_cat["events"]["status"], "Supported")
        self.assertIn("2026-10-15", by_cat["events"]["evidence"])

    def test_9_simple_informational_website(self):
        pages = [
            make_test_page(
                url="https://info.example.org/",
                title="The Heritage Preservation Trust",
                meta_description="Non-profit preservation society protecting historical architectural landmarks.",
                page_type="Homepage",
                visible_text_sample="Welcome to the Heritage Trust. Learn more about our preservation work."
            )
        ]
        snap = make_test_snapshot(pages, "https://info.example.org/")
        res = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        by_cat = {item["category"]: item for item in res}

        # Identity is supported
        self.assertEqual(by_cat["identity"]["status"], "Supported")
        # Pricing is NOT present, must strictly be Not found, not fabricated
        self.assertEqual(by_cat["pricing"]["status"], "Not found")
        self.assertEqual(by_cat["pricing"]["confidence"], "low")
        self.assertEqual(by_cat["pricing"]["sources"], [])


class TestAnswerabilityResultStates(unittest.TestCase):
    """Verifies strict adherence to the 4 result states: Supported, Weakly supported, Conflicting, Not found."""

    def test_supported_state(self):
        snap = make_test_snapshot([
            make_test_page(
                url="https://example.com/",
                meta_description="Enterprise cloud backup platform.",
                visible_text_sample="Enterprise backup. Contact us: support@example.com."
            )
        ])
        res = score_mod.evaluate_agent_answerability(snap)
        q_ident = next(q for q in res if q["question"] == "What does this company do?")
        self.assertEqual(q_ident["status"], "Supported")
        self.assertEqual(q_ident["confidence"], "high")
        self.assertTrue(len(q_ident["sources"]) >= 1)

    def test_weakly_supported_state(self):
        # Pricing page exists, but numeric prices are gated behind a quote form
        snap = make_test_snapshot([
            make_test_page(
                url="https://example.com/pricing",
                page_type="Pricing",
                visible_text_sample="Enterprise pricing is customized based on volume. Contact sales for a bespoke quote."
            )
        ])
        res = score_mod.evaluate_agent_answerability(snap)
        q_price = next(q for q in res if q["question"] == "What does the product cost?")
        self.assertEqual(q_price["status"], "Weakly supported")
        self.assertEqual(q_price["confidence"], "medium")
        self.assertIsNotNone(q_price.get("recommendation"))

    def test_conflicting_state(self):
        # Incompatible locations across pages (Seattle, WA vs Miami, FL)
        snap = make_test_snapshot([
            make_test_page(
                url="https://example.com/",
                json_ld=[{"@type": "Organization", "address": {"streetAddress": "100 Pike St", "addressLocality": "Seattle", "addressCountry": "US"}}]
            ),
            make_test_page(
                url="https://example.com/contact",
                page_type="Contact",
                visible_text_sample="Visit our single office at 200 Biscayne Blvd, Miami, FL 33132."
            )
        ])
        res = score_mod.evaluate_agent_answerability(snap)
        q_loc = next(q for q in res if q["question"] == "Where is it located?")
        self.assertEqual(q_loc["status"], "Conflicting")
        self.assertEqual(q_loc["confidence"], "low")
        self.assertTrue(len(q_loc["sources"]) >= 2)
        self.assertIn("Seattle", q_loc["evidence"])
        self.assertIn("200 Biscayne Blvd", q_loc["evidence"])

    def test_not_found_state(self):
        snap = make_test_snapshot([
            make_test_page(url="https://empty.example.com/", visible_text_sample="Hello world.")
        ])
        res = score_mod.evaluate_agent_answerability(snap)
        q_cost = next(q for q in res if q["question"] == "What does the product cost?")
        self.assertEqual(q_cost["status"], "Not found")
        self.assertEqual(q_cost["confidence"], "low")
        self.assertEqual(q_cost["sources"], [])


class TestEvidenceSourcesAndCrossPage(unittest.TestCase):
    """Verifies multiple pages can corroborate answers and provide joint evidence."""

    def test_cross_page_identity_corroboration(self):
        snap = make_test_snapshot([
            make_test_page(
                url="https://example.com/",
                meta_description="Leading provider of industrial automated robotics.",
                page_type="Homepage"
            ),
            make_test_page(
                url="https://example.com/about",
                page_type="About",
                visible_text_sample="About Us: Leading provider of industrial automated robotics founded in 2012."
            )
        ])
        res = score_mod.evaluate_agent_answerability(snap)
        q_ident = next(q for q in res if q["question"] == "What does this company do?")
        self.assertEqual(q_ident["status"], "Supported")
        self.assertIn("https://example.com/", q_ident["sources"])
        self.assertIn("https://example.com/about", q_ident["sources"])
        self.assertIn("Corroborated across Homepage and About page", q_ident["evidence"])

    def test_cross_page_contact_corroboration(self):
        snap = make_test_snapshot([
            make_test_page(
                url="https://example.com/",
                visible_text_sample="Email corporate headquarters at contact@example.com."
            ),
            make_test_page(
                url="https://example.com/contact",
                page_type="Contact",
                visible_text_sample="Call customer support directly at +1-800-555-0155."
            )
        ])
        res = score_mod.evaluate_agent_answerability(snap)
        q_contact = next(q for q in res if q["question"] == "How can users contact it?")
        self.assertEqual(q_contact["status"], "Supported")
        self.assertIn("contact@example.com", q_contact["evidence"])
        self.assertIn("555-0155", q_contact["evidence"])
        self.assertEqual(len(q_contact["sources"]), 2)


class TestAntiFalsePositiveAndNegativeCases(unittest.TestCase):
    """Anti-overfitting negative testing: guarantees zero hallucination of absent data."""

    def test_no_pricing_does_not_invent_numbers(self):
        snap = make_test_snapshot([
            make_test_page(
                url="https://nonprofit.org/",
                meta_description="Public botanical garden and educational arboretum.",
                visible_text_sample="Explore botanical displays, plant conservation, and walking paths."
            )
        ])
        res = score_mod.evaluate_agent_answerability(snap)
        q_cost = next(q for q in res if q["question"] == "What does the product cost?")
        self.assertEqual(q_cost["status"], "Not found")
        self.assertEqual(q_cost["confidence"], "low")
        self.assertEqual(q_cost["sources"], [])
        self.assertNotIn("$", q_cost["evidence"])
        self.assertNotIn("Price: $", q_cost["evidence"])

    def test_empty_snapshot_graceful(self):
        empty_snap = {"pages": [], "crawl_meta": {}}
        res = score_mod.evaluate_agent_answerability(empty_snap)
        self.assertEqual(len(res), 5)
        for item in res:
            self.assertEqual(item["status"], "Not found")
            self.assertEqual(item["confidence"], "low")
            self.assertEqual(item["sources"], [])

    def test_multilingual_non_english_content(self):
        # German site with rich mission and contact details
        snap = make_test_snapshot([
            make_test_page(
                url="https://gmbh.example.de/",
                title="Müller Industrietechnik GmbH",
                meta_description="Präzisionsmaschinenbau und Industrieautomation für mittelständische Unternehmen.",
                visible_text_sample="Willkommen bei Müller Industrietechnik. Telefon: +49 89 555 0122, E-Mail: info@mueller-technik.de."
            )
        ])
        res = score_mod.evaluate_agent_answerability(snap)
        q_ident = next(q for q in res if q["question"] == "What does this company do?")
        self.assertEqual(q_ident["status"], "Supported")
        q_contact = next(q for q in res if q["question"] == "How can users contact it?")
        self.assertEqual(q_contact["status"], "Supported")
        self.assertIn("info@mueller-technik.de", q_contact["evidence"])


class TestRecommendationsIntegrity(unittest.TestCase):
    """Verifies that all recommendations are purely advisory and never imperative site edits."""

    def test_recommendations_are_advisory(self):
        snap = make_test_snapshot([
            make_test_page(url="https://minimal.example.com/", title="Minimal")
        ])
        res = score_mod.evaluate_agent_answerability(snap)
        for item in res:
            rec = item.get("recommendation")
            if rec:
                self.assertTrue(
                    rec.startswith("Consider ") or rec.startswith("Review "),
                    f"Recommendation must be advisory, but found: {rec}"
                )
                self.assertNotIn("Change page", rec)
                self.assertNotIn("Must change", rec)


if __name__ == "__main__":
    unittest.main()
