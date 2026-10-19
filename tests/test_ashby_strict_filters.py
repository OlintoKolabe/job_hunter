"""Regression contracts: country and work mode must be verified, not inferred."""
import unittest
from unittest.mock import patch

from collectors import pull
from search_filters import classify, search_terms

TERMS = search_terms("Product Manager")


def verdict(location, description="", **extra):
    job = {"title": "Product Manager", "company": "Example", "location": location,
           "description": description, "published": ""}
    job.update(extra)
    return classify(job, TERMS, "BR", "remote", 0)


class EligibilityRegression(unittest.TestCase):
    def test_br_remote_eligible(self):
        self.assertEqual(verdict("Brazil - Remote")[0], "confirmed")

    def test_us_remote_excluded(self):
        self.assertEqual(verdict("United States - Remote")[0], "excluded")

    def test_benelux_remote_not_confirmed(self):
        self.assertNotEqual(verdict("Netherlands - Remote")[0], "confirmed")

    def test_unspecified_work_mode_not_confirmed(self):
        self.assertEqual(verdict("Brazil")[0], "review")

    def test_onsite_requirement_overrides_remote_label(self):
        self.assertNotEqual(
            verdict("Brazil - Remote", "The role is onsite only; must work from office.")[0],
            "confirmed")

    def test_regional_label_with_us_only_restriction_excluded(self):
        self.assertEqual(verdict(
            "LATAM - Remote", "Candidates must be based in the US.")[0], "excluded")

    def test_ashby_structured_metadata_is_kept(self):
        record = {"title": "Product Manager", "jobUrl": "https://jobs.ashbyhq.com/example/123",
                  "location": "Brazil", "isRemote": True,
                  "descriptionPlain": "Manage the product roadmap and product backlog."}
        with patch("collectors.fetch_json", return_value={"jobs": [record]}):
            details, jobs = pull("Ashby", "example")
        self.assertEqual(details["received"], 1)
        self.assertEqual(len(jobs), 1)
        self.assertTrue(jobs[0]["remote"])
        self.assertIn("product roadmap", jobs[0]["description"])


if __name__ == "__main__":
    unittest.main()
