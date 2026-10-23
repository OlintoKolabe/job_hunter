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
            self.assertEqual(classify({**job,"published":""},terms,"BR","remote",days), ("excluded","data"))

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

    def test_ui_separates_score_from_eligibility_and_keeps_no_jd_gate(self):
        ui = Path("src/Opportunities.jsx").read_text(encoding="utf-8")
        self.assertIn("'Aderência local estimada'", ui)
        self.assertIn("Elegibilidade a confirmar:", ui)
        self.assertIn("'Nota inconclusiva'", ui)
        self.assertIn("job.jd_available===true&&<button",ui)
        self.assertIn("if(v.jd_available===false)return 'no_jd'",ui)


if __name__ == "__main__":
    unittest.main()
