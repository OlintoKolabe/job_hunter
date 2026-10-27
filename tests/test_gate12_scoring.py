"""No-network regression checks for the scoped eligibility/JD/UI correction."""
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from block4_score import score_job
from search_filters import classify, search_terms


class Gate12Scoring(unittest.TestCase):
    def test_uninterpreted_mandatory_requirement_cannot_be_perfect_fit(self):
        jd = "\n".join([
            "Requirements",
            "Must have product roadmap experience.",
            "Must have backlog management experience.",
            "Must have stakeholder management experience.",
            "Must have Scrum experience.",
            "Must have familiarity with a proprietary high-frequency trading engine named Zephyr-42.",
            "About us: " + "Our team builds useful technology and values diverse experience. " * 7,
        ])
        result = score_job({"title": "Product Manager", "description": jd}, "Product Manager")
        self.assertGreater(result["uninterpreted_count"], 0)
        self.assertIsNone(result["score"])
        self.assertEqual(result["confidence"], "cobertura_insuficiente")

    def test_local_score_cannot_claim_perfection_without_required_requirements(self):
        jd = "\n".join([
            "Nice to have",
            "Preferred product roadmap experience.",
            "Preferred backlog management experience.",
            "Preferred stakeholder management experience.",
            "Preferred Scrum experience.",
            "About us: " + "Our team builds useful technology and values diverse experience. " * 7,
        ])
        result = score_job({"title": "Product Manager", "description": jd}, "Product Manager")
        self.assertIsNone(result["score"])

    def test_date_windows_keep_verified_recent_and_exclude_unknown(self):
        terms = search_terms("Product Manager")
        for days in (3, 7, 15, 30):
            recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            job = {"title":"Product Manager", "location":"Brazil - Remote", "published":recent}
            self.assertEqual(classify(job,terms,"BR","remote",days)[0],"confirmed")
            self.assertEqual(classify({**job,"published":""},terms,"BR","remote",days), ("review","data"))

    def test_himalayas_api_worldwide_is_brazil_remote(self):
        terms=search_terms("Product Manager")
        recent=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        job={"title":"Product Manager", "location":"Worldwide", "source":"himalayas", "published":recent}
        self.assertEqual(classify(job,terms,"BR","remote",7),("confirmed",""))
        # The same ambiguous location on a generic board stays unconfirmed.
        job["source"]="Greenhouse"
        self.assertEqual(classify(job,terms,"BR","remote",7)[0],"review")

    def test_remote_feed_does_not_override_explicit_onsite(self):
        terms=search_terms("Product Manager")
        job={"title":"Product Manager","location":"Brazil", "source":"remotive",
             "workplaceType":"Onsite"}
        self.assertEqual(classify(job,terms,"BR","remote",0)[0],"excluded")

    def test_jd_product_words_do_not_confirm_non_target_titles(self):
        terms=search_terms("Product Manager, Product Owner, Business Analyst")
        text=("Responsibilities include product roadmap, stakeholder management, "
              "product discovery, agile delivery and backlog prioritization. "*6)
        for title in ("Technical Lead (hands on)", "Estágio em Design",
                      "Frontend Manager Software Engineer (Hands-On) | Partners Acquisition",
                      "AI Native Engineer, Growth Marketing", "Talent Acquisition Analyst"):
            job={"title":title,"description":text,"location":"Brazil - Remote",
                 "published":(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}
            self.assertEqual(classify(job,terms,"BR","remote",7),("excluded","cargo"),title)

    def test_adjacent_program_management_title_remains_reviewable(self):
        terms=search_terms("Product Manager")
        job={"title":"Program Delivery Lead", "location":"Brazil - Remote"}
        self.assertEqual(classify(job,terms,"BR","remote",0),
                         ("review","cargo_a_confirmar"))

    def test_technical_product_manager_is_not_filtered_as_engineer(self):
        terms=search_terms("Product Manager")
        job={"title":"Technical Product Manager - Engineering", "location":"Brazil - Remote"}
        self.assertEqual(classify(job,terms,"BR","remote",0),("confirmed",""))

    def test_worldwide_header_does_not_override_emea_only_jd(self):
        terms=search_terms("Marketing")
        job={"title":"Head of Marketing","source":"himalayas","location":"Worldwide",
             "description":"Head of Marketing — Remote (EMEA). Applicants must be in the region."}
        self.assertEqual(classify(job,terms,"BR","remote",0),("excluded","pais"))

    def test_explicit_foreign_locations_fail_brazil_filter(self):
        terms=search_terms("Product Manager, Project Manager")
        for location in ("Germany", "Boston", "London", "India", "Australia", "France"):
            with self.subTest(location=location):
                self.assertEqual(classify({"title":"Product Manager", "location":location,
                    "source":"remoteok", "workplaceType":"remote"},terms,"BR","remote",0),
                    ("excluded","pais"))

    def test_unknown_location_remains_in_review_not_confirmed(self):
        terms=search_terms("Product Manager")
        self.assertEqual(classify({"title":"Product Manager", "location":"",
            "workplaceType":"remote"},terms,"BR","remote",0),
            ("review","pais"))

    def test_internship_requires_explicit_search_intent(self):
        job={"title":"Product Manager Internship","source":"himalayas","location":"Worldwide"}
        self.assertEqual(classify(job,search_terms("Product Manager"),"BR","remote",0),
                         ("excluded","cargo"))

    def test_ui_hides_scores_and_keeps_no_jd_cv_gate(self):
        ui = Path("src/Opportunities.jsx").read_text(encoding="utf-8")
        self.assertNotIn("Aderência local estimada", ui)
        self.assertNotIn("Nota inconclusiva", ui)
        self.assertNotIn("Avaliar esta vaga", ui)
        self.assertIn("(job.jd_available===true||manualOutsideFilters)&&<button",ui)


if __name__ == "__main__":
    unittest.main()
